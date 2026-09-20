"""Create a reviewable model from the same deterministic catalogs as the wizard."""
from __future__ import annotations

from backend.knowledge.semantic_vocabulary import engineering_phrase_match

import json
import hashlib
from difflib import SequenceMatcher
from pathlib import Path
import shutil
import subprocess
import re
from copy import deepcopy

from . import model, proposal_service
from .wizard_commands import effective_wizard_prompt
from .. import proposals as proposal_store
from ..device_classification import DeviceClassificationRegistry
from ..generation_rule_manager import resolve_generation_policy
from ...communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY
from ..workflow.service import WorkflowStatusService
from ..project_context import current_project_id
from ..physical_ports import materialize_physical_ports
from ..naming import concise_name
from ..bus_settings import limits_from_prompt, branch_capacity, with_project_limits
from ..message_bindings import message_hardware_interface_ids
from ..spatial_zoning import installation_zone, driving_side_from_prompt, LOCAL_BUSES, VERSION as ZONING_VERSION
from ..spatial_architecture import architecture_from, location_decision, zone_label, with_spatial_architecture
from ..routing.generation import RoutingGenerationService, routing_candidate_batch
from ..routing.validation import PROTOCOL_CAPACITY
from ..capacity.service import CapacityTimingService
from ..intelligence.resource_policy import planning_policy, planning_inventory, resource_decision, decision_summary
from ..intelligence.network_planning import (
    communication_system_inventory,
    plan_network_distribution,
    split_topology_by_distribution,
)
from backend.app.simulation_service import SimulationService


_TOPOLOGY_BUS_BY_PROTOCOL = {
    'CAN': 'can',
    'CAN_FD': 'can_fd',
    'CAN_XL': 'can_xl',
    'LIN': 'lin',
    'FLEXRAY': 'flexray',
    'ETHERNET': 'automotive_ethernet',
    'SOME_IP': 'automotive_ethernet',
    'SOMEIP': 'automotive_ethernet',
}

MODEL_GENERATOR_VERSION = 'wizard-model-v22-generation-rules'
ROUTING_GENERATOR_VERSION = 'wizard-routing-v10-preserve-local-technology'

_CONTROLLER_DEVICE_TYPES = {
    'ECU', 'PLC', 'RobotController', 'EmbeddedController', 'IndustrialPC',
    'FlightComputer', 'BatteryManagementSystem', 'EnergyController', 'BuildingController',
}


def _is_local_main_controller(chain: dict, specification: dict) -> bool:
    return (
        specification.get('networkArchitecture') == 'sensor_ecu_actuator'
        and chain.get('device_type') in _CONTROLLER_DEVICE_TYPES
        and not any(item.get('device_type') == 'Gateway' for item in specification.get('chains') or [])
    )


def _canonical_wizard_prompt(prompt: str) -> str:
    # Compatibility for persisted v1 requests: the entire appended continuation
    # is control text, not a new engineering requirement.
    return re.split(r'\nFortsetzung des bestätigten Wizard-Auftrags:', str(prompt), maxsplit=1)[0].strip()


def _declared_function_names(prompt: str) -> list[str]:
    """Preserve explicit function lists, without deriving functions from device names."""
    sources = [prompt]
    match = re.search(r'^- Fachliche-Anforderungen:\s*(\[[^\r\n]*\])\s*$', prompt, re.M)
    if match:
        values = json.loads(match[1])
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            raise ValueError('Ungültige fachliche Anforderungen.')
        sources.extend(values)
    names = {}
    for source in sources:
        active = False
        for line in source.splitlines():
            text = line.strip()
            if re.fullmatch(r'(?:Funktionen|Functions):', text, re.I):
                active = True
                continue
            if not active:
                continue
            text = re.sub(r'^[-*]\s+', '', text)
            if not re.fullmatch(r'[\w][\w .()/+-]{0,119}', text) or not text:
                active = False
                continue
            names.setdefault(text.casefold(), text)
    return list(names.values())


def _declared_function_hosts(specification: dict, function_refs: dict[str, str | None]) -> list[str]:
    """Return controllers that may host explicitly named domain functions.

    Gateways have their own generated communication function, but that must not
    make them an alternative host for application functions when the project
    contains one unambiguous controller.
    """
    device_types = {
        str(chain.get('hardware_name') or '').casefold(): chain.get('device_type')
        for chain in specification.get('chains') or []
    }
    return [
        key for key, reference in function_refs.items()
        if reference and device_types.get(key) in _CONTROLLER_DEVICE_TYPES
    ]


def _confirmed_actuator_commands(prompt: str) -> dict:
    # The questionnaire wraps its free-form notes in "Weitere Hinweise".
    # Accept that wrapper without changing any user-specified encoding.
    command_raw = re.search(r'^- (?:Weitere Hinweise:\s*-\s*)?Aktor-Befehle:\s*(\{[^\r\n]*\})\s*$', prompt, re.M)
    return json.loads(command_raw.group(1)) if command_raw else {}


def _check_existing_amendment_semantics(prompt: str, specification: dict, existing: dict, state: dict) -> None:
    """Do not mistake an unsupported edit/deletion for an additive delta.

    Compare the user's previous and current specifications, not generated
    defaults against an enriched canonical model. Existing encodings, message
    identifiers and manually reviewed parameter values remain authoritative.
    """
    marker = '\n\nBestaetigte Ergaenzung des Nutzers:\n'
    if marker not in prompt:
        return
    previous_prompt = effective_wizard_prompt(prompt.rsplit(marker, 1)[0])
    current_prompt = effective_wizard_prompt(prompt)
    previous_prompt = with_spatial_architecture(previous_prompt, state.get('parameters'))
    if not re.search(r'^- Bus-Teilnehmergrenzen:', previous_prompt, re.M):
        previous_prompt = with_project_limits(previous_prompt, state.get('context') or {})
    previous = extract_specification(previous_prompt)
    existing_names = {row['name'].casefold() for row in existing['HardwareNode']}
    key = lambda chain: (str(chain['hardware_name']).casefold(), str(chain['signal_name']).casefold())
    current_chains = {key(chain): chain for chain in specification['chains']}
    fields = ('device_type', 'function_name', 'interface_type', 'interface_name', 'transport_network_ref', 'message_name',
              'direction', 'cycle_ms', 'dlc', 'start_bit', 'length_bits', 'byte_order', 'data_type',
              'factor', 'offset_value', 'unit', 'min_value', 'max_value', 'semantic', 'data')
    for old in previous['chains']:
        if str(old['hardware_name']).casefold() not in existing_names:
            continue
        new = current_chains.get(key(old))
        if new is None:
            raise ValueError(f"Die Ergänzung entfernt oder benennt das bestehende Signal {old['signal_name']} "
                f"von {old['hardware_name']} um. Dafür ist eine explizit geprüfte Änderung einschließlich Referenzen erforderlich.")
        for field in fields:
            if old.get(field) != new.get(field):
                raise ValueError(f"Bestehendes Signal {old['hardware_name']} / {old['signal_name']}: "
                    f"{field} wurde von {old.get(field)!r} auf {new.get(field)!r} geändert. "
                    "Diese Änderung benötigt einen geprüften Update-Vorschlag; sie wird nicht als neue Anlage oder unveränderter Stand übernommen.")
    old_commands = _confirmed_actuator_commands(previous_prompt)
    for name, command in _confirmed_actuator_commands(current_prompt).items():
        if name.casefold() in existing_names and command != old_commands.get(name):
            raise ValueError(f'Aktor {name}: geänderte Befehlskodierung benötigt eine explizit geprüfte Änderung der bestehenden Nachricht und Signale.')
    def clusters(text):
        raw = re.search(r'^- Systemcluster-Graph:\s*(\[[^\r\n]*\])\s*$', text, re.M)
        return json.loads(raw[1]) if raw else []
    old_clusters = {item.get('bus_name'): item for item in clusters(previous_prompt)}
    supported = {'cluster_id', 'label', 'network_id', 'network_label', 'bus_name', 'controllers',
                 'unassigned', 'hmi_routes', 'warnings'}
    for cluster in clusters(current_prompt):
        old = old_clusters.get(cluster.get('bus_name'), {})
        for field, value in cluster.items():
            if field not in supported and old.get(field) != value:
                raise ValueError(f"Netzwerk {cluster.get('bus_name')}: Parameter {field} = {value!r} "
                    "wird durch die Modellanlage nicht geändert. Dafür ist ein explizit geprüfter Netzwerkparameter-Vorschlag erforderlich.")
        if old and old.get('hmi_routes', []) != cluster.get('hmi_routes', []):
            raise ValueError(f"Netzwerk {cluster.get('bus_name')}: geänderte HMI-Empfänger oder Signalauswahl benötigen "
                "einen explizit geprüften Kommunikations- und Routingvorschlag für die bestehenden Nachrichten.")


def _proposal_identity(step: str, prompt: str, source: dict, state: dict, generator_version: str) -> dict:
    """Content-address a request and its complete relevant canonical input.

    Worker heartbeats, UI text, validation timestamps and operation IDs are not
    engineering inputs. Logical interfaces, functions and signals are inputs,
    including when only those objects changed since a failed proposal.
    """
    canonical_prompt = _canonical_wizard_prompt(prompt)
    stored = (state.get('context') or {}).get('wizard_request') or {}
    same_request = _canonical_wizard_prompt(stored.get('prompt') or '') == canonical_prompt
    run_match = re.search(r'^- Lauf-ID:\s*([^\r\n]+)', canonical_prompt, re.M)
    request = {'prompt': canonical_prompt,
               'run_id': stored.get('run_id') if same_request else run_match.group(1).strip() if run_match else None,
               'revision': stored.get('revision') if same_request else None,
               'target': stored.get('target') if same_request else None}
    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str, allow_nan=False).encode('utf-8')).hexdigest()
    # A successor family survives canonical edits and generator upgrades, while
    # the fingerprint changes and prevents stale validation reuse.
    operation_key = digest({'project_id': current_project_id(), 'step': step,
                            'request_family': request['run_id'] or canonical_prompt})
    ordered_source = {kind: sorted(rows, key=lambda row: str(row.get('id') or row.get('name') or ''))
                      if isinstance(rows, list) and all(isinstance(row, dict) for row in rows) else rows
                      for kind, rows in source.items()}
    fingerprint = digest({'operation_key': operation_key, 'request': request, 'generator_version': generator_version,
                          'source': ordered_source, 'parameters': state.get('parameters') or {},
                          'topology': state.get('topology') or {},
                          'wizard_settings': (state.get('context') or {}).get('engineering_wizard_settings') or {}})
    return {'prompt_sha256': fingerprint, 'operation_key': operation_key,
            'generator_version': generator_version, 'request_revision': request['revision'], 'run_id': request['run_id']}


def _reusable_proposal(proposal_type, identity, rows):
    for row in rows:
        if row['proposal_type'] != proposal_type:
            continue
        contract = row.get('engineering_contract') or {}
        if contract.get('replacement_proposal_id') or contract.get('status') in {'REJECTED', 'SUPERSEDED'}:
            continue
        if any(item.get('prompt_sha256') == identity['prompt_sha256'] for item in row.get('evidence') or []):
            # An unchanged invalid proposal is returned with its findings; retry
            # does not disguise the error by generating an identical second one.
            return proposal_service.envelope(row)
    return None


def _supersede_previous(proposal_type, identity, rows, replacement):
    for row in rows:
        contract = row.get('engineering_contract') or {}
        if row['proposal_type'] != proposal_type or contract.get('status') in {'APPLIED', 'REJECTED', 'SUPERSEDED'}:
            continue
        if contract.get('replacement_proposal_id') or str(row['proposal_id']) == str(replacement['proposal_id']):
            continue
        if any(item.get('operation_key') == identity['operation_key'] for item in row.get('evidence') or []):
            proposal_service.set_replacement(str(row['proposal_id']), str(replacement['proposal_id']))
    return replacement


def _technology_contract(interface_type: str) -> dict:
    """Resolve wizard vocabulary through the central registry without protocol switches."""
    technology_id = DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(interface_type)
    profile = DEFAULT_TECHNOLOGY_REGISTRY.profile(technology_id)
    stack = tuple(profile.get('default_stack') or (technology_id,))
    resolved = DEFAULT_TECHNOLOGY_REGISTRY.resolve_stack(stack)
    return {
        'technology_id': technology_id,
        'stack': list(stack),
        'layer': profile['layer'],
        'transport_unit_type': profile['transport_unit'],
        'hardware_interface': profile['hardware_interface'],
        'implementation_status': profile['implementation_status'],
        'capabilities': profile['capabilities'],
        'binding': type(resolved['binding']).__name__,
        'generator': type(resolved['generator']).__name__,
        'validator_chain': [type(item).__name__ for item in resolved['validators']],
        'timing_model': type(resolved['timing_model']).__name__,
        'load_calculator': type(resolved['load_calculator']).__name__,
    }


def _bind_generated_gateway_status(changes, existing):
    """Publish a new gateway's own status on its recipient's actual channel.

    A gateway-originated status is native output, not an incoming frame that
    needs a fictitious intermediate gateway. Preserve its approved recipients,
    function, complete payload and encoding; existing messages are untouched.
    """
    graph = {kind: {str(row['id']): row for row in existing.get(kind, [])}
             for kind in ('HardwareNode', 'Function', 'Interface', 'HardwareNetworkInterface')}
    for change in changes:
        if change['object_type'] in graph:
            graph[change['object_type']][str(change.get('object_id') or '$' + change['local_ref'])] = change['data']
    ports = graph['HardwareNetworkInterface']
    for change in changes:
        if change['object_type'] != 'Message' or change.get('action', 'CREATE') != 'CREATE':
            continue
        message = change['data']
        config = message.get('configuration') or {}
        contract = config.get('communication_contract') or {}
        owner = str(contract.get('producer_ref') or '')
        targets = set(map(str, contract.get('consumer_refs') or []))
        if contract.get('role') != 'DEVICE_STATUS' or graph['HardwareNode'].get(owner, {}).get('device_type') != 'Gateway' or not targets:
            continue
        candidates = [(key, port) for key, port in ports.items() if str(port.get('hardware_node_id')) == owner
                      and port.get('network_ref') and all(any(
                          str(peer.get('hardware_node_id')) == target and peer.get('network_ref') == port['network_ref']
                          and peer.get('technology') == port['technology'] for peer in ports.values()) for target in targets)]
        if len(candidates) != 1:
            continue  # Parallel or different recipient networks need explicit choices.
        port_ref, port = candidates[0]
        original = graph['Interface'].get(str(message.get('interface_id')), {})
        logical = [(key, item) for key, item in graph['Interface'].items()
                   if item.get('interface_type') == port['technology'] and
                   (item.get('function_id') == original.get('function_id') if original.get('function_id')
                    else str(item.get('hardware_node_id')) == owner)]
        if len(logical) != 1:
            continue
        message.update(interface_id=logical[0][0], hardware_interface_id=port_ref)
        technology = _technology_contract(port['technology'])
        config['technology_binding'] = technology
        config['transport_unit']['transport_unit_type'] = technology['transport_unit_type']
        config['channel_selection'] = {'source': 'confirmed-recipient-network', 'network_id': port['network_ref']}
        for signal in changes:
            if signal['object_type'] == 'Signal' and signal['data'].get('message_id') == '$' + change['local_ref']:
                for binding in signal['data'].get('protocol_bindings') or []:
                    binding['technology_binding_ref'] = technology['technology_id']


def _network_protocol(interface_type: str) -> str:
    """Translate model-facing interface labels to canonical network protocols."""
    key = re.sub(r'[^A-Z0-9]+', '_', str(interface_type or '').upper()).strip('_')
    aliases = {
        'CANFD': 'CAN_FD',
        'FLEXRAY': 'FLEXRAY',
        'AUTOMOTIVE_ETHERNET': 'ETHERNET',
        'SOMEIP': 'SOME_IP',
        'PROFINET': 'PROFINET',
        'ETHERCAT': 'ETHERCAT',
        'MODBUSTCP': 'modbus_tcp',
        'MODBUS_TCP': 'modbus_tcp',
        'MODBUSRTU': 'modbus_rtu',
        'MODBUS_RTU': 'modbus_rtu',
        'OPCUA': 'OPC_UA',
        'ROS2': 'ROS_2',
    }
    protocol = aliases.get(key, key)
    return protocol if protocol in PROTOCOL_CAPACITY else _topology_bus(interface_type)


def _next_generated_can_identifier(existing_messages: list[dict], pending_changes: list[dict]) -> str:
    """Return the first free standard CAN identifier across persisted and pending messages."""
    used: set[int] = set()
    candidates = [
        *existing_messages,
        *(change.get('data') or {} for change in pending_changes if change.get('object_type') == 'Message'),
    ]
    for message in candidates:
        value = str(message.get('message_id_hex') or '').strip()
        if not value:
            continue
        try:
            used.add(int(value, 16))
        except ValueError:
            continue
    identifier = next((value for value in range(0x100, 0x800) if value not in used), None)
    if identifier is None:
        raise ValueError('Für die lokale Aktor-Nachricht ist kein freier Standard-CAN-Identifier verfügbar.')
    return f'0x{identifier:03X}'


def _generation_policy_for_specification(prompt: str, specification: dict) -> dict:
    bus_types = list(dict.fromkeys(
        str(chain.get('interface_type') or '')
        for chain in specification.get('chains') or []
        if chain.get('interface_type')
    ))
    return resolve_generation_policy(
        prompt,
        industry=specification.get('modelType') or specification.get('domain'),
        bus_types=bus_types,
    )


def extract_specification(prompt: str) -> dict:
    node = shutil.which('node')
    if not node:
        raise ValueError('Node.js wird für den vorhandenen Wizard-Generator benötigt.')
    script = Path(__file__).resolve().parents[3] / 'frontend' / 'scripts' / 'extract-wizard-specification.mjs'
    result = subprocess.run(
        [node, '--experimental-strip-types', str(script)],
        input=json.dumps({'prompt': prompt}), text=True, encoding='utf-8',
        capture_output=True, timeout=60, check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
    )
    if result.returncode:
        raise ValueError('Die Wizard-Spezifikation konnte nicht abgeleitet werden: ' + result.stderr[-1000:])
    specification = json.loads(result.stdout)
    specification['generationPolicy'] = _generation_policy_for_specification(prompt, specification)
    return specification


def _wizard_parameter_technology_ids(prompt: str) -> list[str]:
    """Return confirmed technologies in stable wizard order."""
    raw = re.search(r'^- Netzwerktechnologien:\s*(.+)$', prompt, re.M)
    candidates = re.findall(r'\(([a-zA-Z0-9_.:-]+)\)', raw.group(1)) if raw else []
    if not candidates:
        graph = re.search(r'^- Systemcluster-Graph:\s*(\[[^\r\n]*\])\s*$', prompt, re.M)
        if graph:
            candidates = [str(item.get('network_id') or '') for item in json.loads(graph.group(1))]
    resolved: list[str] = []
    for candidate in candidates:
        if candidate.startswith('detected:'):
            candidate = candidate.split(':', 1)[1]
        try:
            technology_id = DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(candidate)
            DEFAULT_TECHNOLOGY_REGISTRY.profile(technology_id)
        except (KeyError, ValueError):
            continue
        if technology_id not in resolved:
            resolved.append(technology_id)
    return resolved


def _parameter_defaults(technology_id: str) -> dict:
    profile = DEFAULT_TECHNOLOGY_REGISTRY.profile(technology_id)
    return {
        field['key']: field.get('default')
        for field in SimulationService._parameter_schema(technology_id, profile)
        if 'default' in field
    }


def generate_parameters(arguments: dict) -> dict:
    """Persist confirmed registry defaults without delegating tool choice to an LLM."""
    prompt = effective_wizard_prompt(arguments['prompt'])
    workflow = WorkflowStatusService(current_project_id())
    state = workflow.get()
    technology_ids = _wizard_parameter_technology_ids(prompt)
    if not technology_ids:
        for route in model.routes():
            protocol = str((route.get('source') or {}).get('protocol') or '')
            try:
                technology_id = DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(protocol)
                DEFAULT_TECHNOLOGY_REGISTRY.profile(technology_id)
            except (KeyError, ValueError):
                continue
            if technology_id not in technology_ids:
                technology_ids.append(technology_id)
    if not technology_ids:
        raise ValueError('Keine registrierte Netzwerktechnologie für die Parameter-Defaults gefunden.')

    domain_match = re.search(r'^- Projekt-Modelltyp:\s*([^\r\n]+)', prompt, re.M)
    industry = (domain_match.group(1).strip() if domain_match else '') or str(
        (state.get('parameters') or {}).get('industry') or 'generic_networking'
    )
    primary = technology_ids[0]
    primary_defaults = _parameter_defaults(primary)
    existing = state.get('parameters') or {}
    parameters = {
        **primary_defaults,
        **existing,
        'industry': industry,
        'technology': primary,
        'formats': list(existing.get('formats') or ['universal-jsonl', 'universal-csv']),
        'technology_defaults': {
            technology_id: _parameter_defaults(technology_id)
            for technology_id in technology_ids
        },
        'defaults_source': 'technology-registry',
        'spatial_architecture': architecture_from(existing, prompt),
    }
    if 'duration_s' not in existing and 'duration_s' in primary_defaults:
        parameters['parameter_provenance'] = {
            **(existing.get('parameter_provenance') or {}),
            'duration_s': {'source': 'TECHNOLOGY_DEFAULT', 'value': primary_defaults['duration_s']},
        }

    saved = workflow.save_parameters(
        parameters, actor=str(arguments.get('_actor') or 'engineering-agent')
    )
    artifact_check = saved['artifact_checks']['parameters']
    if not artifact_check['complete']:
        raise ValueError(f'Parameter-Defaults bleiben unvollständig: {artifact_check["required"]}')
    if not parameters.get('spatial_zoning'):
        from ..zoning_service import SpatialZoningService
        zoning = SpatialZoningService(current_project_id())
        zone_plan = zoning.plan(driving_side_from_prompt(prompt))
        zoning.apply(zone_plan['token'], driving_side_from_prompt(prompt),
                     actor=str(arguments.get('_actor') or 'engineering-agent'), approve_valid=True)
        saved = workflow.get()
        parameters = saved['parameters']
    # Parameter generation follows physical routing. Dimension the complete bus
    # traffic here, before capacity/network splitting, using the same service as
    # the workbench. Explicit user/import timing remains locked.
    from ..capacity.sizing_service import CommunicationSizingService
    from ..capacity.dimensioning import policy_for
    sizing = None
    if policy_for(parameters)["enabled"]:
        sizing_service = CommunicationSizingService(current_project_id())
        sizing = sizing_service.preview()
        if sizing["changes"]:
            sizing_service.apply(sizing["source_token"], actor=str(arguments.get('_actor') or 'engineering-agent'), approve_valid=True)
            saved = workflow.get()
    return {
        'status': saved['statuses']['parameters'],
        'parameters': saved['parameters'],
        'artifact_check': artifact_check,
        'technology_ids': technology_ids,
        'source': 'technology-registry',
        'communication_dimensioning': sizing,
    }


def generate(arguments: dict, *, source_evidence: list[dict] | None = None) -> dict:
    state = WorkflowStatusService(current_project_id()).get()
    prompt = _canonical_wizard_prompt(arguments['prompt'])
    draft_marker = re.search(r'^- Projektentwurf: ([A-Za-z0-9._-]+) Revision (\d+)\s*$', prompt, re.M)
    wizard_context = (state.get('context') or {}).get('agent_wizard_status') or {}
    structured_ref = wizard_context.get('structured_draft_ref')
    saved_prompt = (state.get('context') or {}).get('wizard_request', {}).get('prompt', '')
    if structured_ref and _canonical_wizard_prompt(saved_prompt) == prompt:
        from .project_draft import inspect as inspect_draft
        from ..db import ConcurrentUpdateError
        draft = inspect_draft()
        current_ref = wizard_context.get('engineering_draft_ref') or structured_ref
        if not draft or draft['draft_id'] != current_ref['draft_id'] or draft['revision'] != current_ref['revision']:
            raise ConcurrentUpdateError('Der gemeinsame Projektentwurf wurde geändert. Aktuelle Revision im Auftrag übernehmen.')
        source_evidence = [*(source_evidence or []), {'source': 'engineering_draft',
            'draft_id': draft['draft_id'], 'revision': draft['revision'], 'adapter_version': 2}]
    if draft_marker:
        from .project_draft import inspect as inspect_draft
        from ..db import ConcurrentUpdateError
        draft = inspect_draft()
        if not draft or draft['draft_id'] != draft_marker[1] or draft['revision'] != int(draft_marker[2]):
            raise ConcurrentUpdateError('Der Projektentwurf wurde nach der Auftragsvorbereitung geändert.')
        source_evidence = [*(source_evidence or [])]
        if not any(item.get('source') == 'engineering_draft' for item in source_evidence):
            source_evidence.append({'source': 'engineering_draft', 'draft_id': draft['draft_id'],
                                   'revision': draft['revision'], 'requirement': draft['original_requirement'], 'adapter_version': 1})
    kinds = ('HardwareNode', 'Function', 'HardwareNetworkInterface', 'Interface', 'Message', 'Signal')
    existing = {kind: model.objects(kind) for kind in kinds}
    proposal_identity = _proposal_identity('engineering_model', prompt, existing, state, MODEL_GENERATOR_VERSION)
    proposals = proposal_store.list_proposals(limit=100)
    reusable = _reusable_proposal('WIZARD_ENGINEERING_MODEL', proposal_identity, proposals)
    if reusable:
        return reusable
    arguments = {**arguments, 'prompt': with_spatial_architecture(effective_wizard_prompt(prompt), state.get('parameters'))}
    if not re.search(r"^- Bus-Teilnehmergrenzen:", arguments["prompt"], re.M):
        context = state.get("context") or {}
        arguments = {**arguments, "prompt": with_project_limits(arguments["prompt"], context)}
    spec = extract_specification(arguments['prompt'])
    spec.setdefault('generationPolicy', _generation_policy_for_specification(arguments['prompt'], spec))
    confirmed_spec = deepcopy(spec) if '\n\nBestaetigte Ergaenzung des Nutzers:\n' in prompt else spec
    # Gateway status uses a real controller backbone, not an unconnected
    # catalogue-default transport. Resolve this before creating messages.
    # Commit the approved physical partition at model creation, before any
    # message binding or route is created. Later topology must not invent a
    # competing set of network IDs for the same canonical hardware ports.
    architecture = architecture_from(prompt=arguments['prompt'])
    segment_memberships = _confirmed_segment_memberships(arguments['prompt'])
    local_memberships = _confirmed_local_io_memberships(arguments['prompt'], {str(c['hardware_name']).casefold(): _topology_bus(c['interface_type']) for c in spec['chains']})
    for chain in spec['chains']:
        name = str(chain['hardware_name']).casefold()
        hardware = {'name': chain['hardware_name'], 'device_type': chain['device_type']}
        bus = _topology_bus(chain['interface_type'])
        if name in local_memberships:
            owner = local_memberships[name][0]
            network = _local_io_physical_network(bus, local_memberships, hardware, {'name': owner})
        else:
            network = _segmented_physical_network(bus, segment_memberships, hardware)
        if network:
            chain['transport_network_ref'] = network[0]
            chain['transport_network_name'] = network[1]
    graph_match = re.search(r'^- Systemcluster-Graph:\s*(\[[^\r\n]*\])', arguments['prompt'], re.M)
    if graph_match:
        controller_names = {str(c.get('ecu', '')).casefold() for cluster in json.loads(graph_match.group(1))
                            for c in cluster.get('controllers') or []}
        backbones = sorted({(c['interface_type'], c['transport_network_ref']) for c in spec['chains']
                            if c['hardware_name'].casefold() in controller_names and c.get('transport_network_ref')})
        for chain in spec['chains']:
            if chain['device_type'] == 'Gateway' and backbones:
                technology, network = next((pair for pair in backbones if pair[0] == chain['interface_type']), backbones[0])
                chain.update(interface_type=technology, transport_network_ref=network)
    changes, refs = [], {}

    def hardware_interface_identity(data):
        return (
            str(data.get('hardware_node_id') or ''),
            _network_protocol(str(data.get('technology') or '')),
            str(data.get('network_ref') or '').casefold(),
        )

    def ensure(kind, name, data, parent=None):
        if kind == 'HardwareNetworkInterface' and is_ethernet(data.get('technology')):
            row = named_networks.get(data.get('network_ref'))
            if row:
                name = row['name']
                data = {**data, 'capabilities': {**(data.get('capabilities') or {}), 'name_source': 'network', 'name_network_id': row['id']}}
        name = concise_name(kind, name)
        signature = ((kind, *hardware_interface_identity(data))
                     if kind == 'HardwareNetworkInterface'
                     else (kind, name.casefold(), data.get(parent) if parent else None))
        if signature in refs:
            # One logical local-I/O interface can terminate several explicitly
            # generated channels, including receive-only sensor segments.
            if kind == 'Interface':
                created = next((item for item in changes if '$' + item.get('local_ref', '') == refs[signature]), None)
                if created:
                    configuration = created['data'].setdefault('configuration', {})
                    configuration['physical_interface_ids'] = list(dict.fromkeys([
                        *(configuration.get('physical_interface_ids') or []),
                        *((data.get('configuration') or {}).get('physical_interface_ids') or []),
                    ]))
            return refs[signature]
        if kind == 'HardwareNetworkInterface':
            matches = [row for row in existing[kind]
                       if hardware_interface_identity(row) == hardware_interface_identity(data)]
        else:
            matches = [row for row in existing[kind] if row['name'].casefold() == name.casefold()
                       and (not parent or str(row.get(parent)) == str(data[parent]))]
        if len(matches) > 1:
            raise ValueError(f'Mehrdeutige vorhandene Zuordnung: {kind} {name}')
        if matches:
            if kind == 'HardwareNode' and matches[0].get('device_type') != data['device_type']:
                raise ValueError(f'Gerätetyp des vorhandenen Systems {name} passt nicht zum Auftrag.')
            ref = str(matches[0]['id'])
        else:
            local_ref = f'object-{len(changes)}'
            changes.append({'object_type': kind, 'local_ref': local_ref, 'data': {'name': name, **data}})
            ref = '$' + local_ref
        refs[signature] = ref
        return ref

    declared_networks: dict[str, str] = {}
    hardware_refs: dict[str, str] = {}
    function_refs: dict[str, str | None] = {}
    # Additional calculated functions share their controller's hardware. They
    # must not replace its original controller function or local-I/O ownership.
    chain_by_name = {}
    for item in spec['chains']:
        chain_by_name.setdefault(str(item.get('hardware_name') or '').casefold(), item)
    for chain in spec['chains']:
        network_ref = str(chain.get('transport_network_ref') or '').strip()
        if not network_ref:
            continue
        protocol = _network_protocol(chain['interface_type'])
        previous = declared_networks.get(network_ref)
        if previous and previous != protocol:
            raise ValueError(f'Netzwerk {network_ref} wurde mit widersprüchlichen Technologien bestätigt.')
        declared_networks[network_ref] = protocol
    from ..naming import ethernet_names, is_ethernet
    network_rows = [{'id': ref, 'name': next((c['transport_network_name'] for c in spec['chains']
        if c.get('transport_network_ref') == ref and c.get('transport_network_name')), ref),
        'technology': protocol, **({'name_source': 'generated'} if is_ethernet(protocol) else {})}
        for ref, protocol in sorted(declared_networks.items())]
    naming_topology = {'nodes': [{'id': c['hardware_name'].casefold(), 'engineeringId': c['hardware_name'].casefold(),
        'name': c['hardware_name'], 'kind': 'gateway' if c['device_type'] == 'Gateway' else 'ecu' if c['device_type'] not in {'SensorController', 'ActuatorController'} else 'sensor',
        'systemOwnerId': local_memberships.get(c['hardware_name'].casefold(), [None])[0],
        'ports': [{'physicalNetworkId': c.get('transport_network_ref')}] } for c in spec['chains']]}
    existing_networks = {str(row['id']): row for row in model.networks()}
    for row in network_rows:
        current = existing_networks.get(row['id'])
        if current and _network_protocol(current.get('technology')) != row['technology']:
            raise ValueError(f"Netzwerk {row['id']}: bestehende Technologie {current.get('technology')} "
                f"weicht von der bestätigten Ergänzung {row['technology']} ab. "
                "Der Technologiewechsel benötigt eine explizite Änderung der betroffenen Anschlüsse und Nachrichten.")
    reserved_networks = [{**n, 'name_source': 'user'} for n in existing_networks.values() if n['id'] not in declared_networks]
    named_all = ethernet_names([*reserved_networks, *network_rows], topology=naming_topology)
    named_networks = {row['id']: existing_networks.get(row['id'], named_all[row['id']]) for row in network_rows}
    for row in named_networks.values():
        if row['id'] not in existing_networks:
            changes.append({'object_type': 'Network', 'local_ref': f'network-{len(changes)}', 'data': row})
    _check_existing_amendment_semantics(prompt, confirmed_spec, existing, state)
    for chain in spec['chains']:
        row = named_networks.get(chain.get('transport_network_ref'))
        if row and is_ethernet(row['technology']):
            chain['transport_network_name'] = row['name']


    for chain in spec['chains']:
        technology_contract = _technology_contract(chain['interface_type'])
        local_main_controller = _is_local_main_controller(chain, spec)
        profile = DeviceClassificationRegistry().resolve_profile(
            name=chain['hardware_name'], device_type=chain['device_type'],
            device_class=chain.get('device_class'),
            device_typing='Main Controller' if local_main_controller else chain.get('device_typing'))
        hw = ensure('HardwareNode', chain['hardware_name'], {
            'device_type': chain['device_type'], 'device_class': profile.device_class,
            'device_typing': profile.device_typing, 'data_complexity': profile.data_complexity,
            'identity': {**({'actuator_command_template': chain['configuration']['actuator_command_template']} if (chain.get('configuration') or {}).get('actuator_command_template') else {}),
                         **({'system_role': 'MAIN_CONTROLLER'} if local_main_controller else {}),
                         'installation_zone': installation_zone(chain['hardware_name'], driving_side=driving_side_from_prompt(arguments['prompt']), architecture=architecture),
                         'installation_zone_source': ZONING_VERSION, 'installation_reference_frame': architecture['reference_frame'],
                         'spatial_decision': location_decision(chain['hardware_name'], driving_side=driving_side_from_prompt(arguments['prompt']), architecture=architecture)},
            'description': chain['hardware_description']})
        hardware_refs[str(chain['hardware_name']).casefold()] = hw
        fn = None
        if profile.requires_function_model:
            fn = ensure('Function', concise_name('Function', chain['function_name']), {
                'hardware_node_id': hw, 'domain': spec['domain'], 'description': chain['function_description']}, 'hardware_node_id')
        function_refs.setdefault(str(chain['hardware_name']).casefold(), fn)
        port = ensure('HardwareNetworkInterface', chain['interface_name'], {
            'hardware_node_id': hw, 'technology': chain['interface_type'], 'channel_index': 1,
            'network_ref': chain.get('transport_network_ref'),
            'capabilities': {
                'hardware_interface': technology_contract['hardware_interface'],
                'technology_stack': technology_contract['stack'],
                **technology_contract['capabilities'],
            }}, 'hardware_node_id')
        interface = ensure('Interface', concise_name('Interface', chain['interface_name']), {
            **({'function_id': fn} if fn else {'hardware_node_id': hw}),
            'configuration': {'physical_interface_ids': [port],
                **({'endpoint_role': 'SYSTEM_CONTROLLER'} if fn and chain is chain_by_name[str(chain['hardware_name']).casefold()] else {})},
            'interface_type': chain['interface_type']}, 'function_id' if fn else 'hardware_node_id')
        message = ensure('Message', concise_name('Message', chain['message_name']), {
            'interface_id': interface, 'hardware_interface_id': port,
            **{key: chain[key] for key in ('message_id_hex', 'direction', 'cycle_ms', 'dlc')},
            'configuration': {
                'model_type': 'TransportUnit',
                'technology_binding': technology_contract,
                'transport_unit': {
                    'transport_unit_type': technology_contract['transport_unit_type'],
                    'producer_ref': hw,
                    'consumer_refs': [],
                    'payload_size': chain.get('dlc'),
                    'timing': {'cycle_ms': chain.get('cycle_ms')},
                    'status': 'PROPOSED',
                    'provenance': {'source': 'wizard', 'generator': technology_contract['generator']},
                },
            }}, 'interface_id')
        ensure('Signal', chain['signal_name'], {
            'message_id': message,
            **{key: chain[key] for key in ('start_bit', 'length_bits', 'byte_order', 'data_type',
                'factor', 'offset_value', 'unit', 'min_value', 'max_value', 'configuration',
                'semantic', 'data', 'communication', 'quality') if key in chain},
            'protocol_bindings': [{
                'model_type': 'PayloadElement',
                'element_type': 'SIGNAL',
                'semantic_ref': chain.get('signal_name'),
                'data_type': chain.get('data_type'),
                'size': chain.get('length_bits'),
                'unit': chain.get('unit'),
                'encoding': {
                    'byte_order': chain.get('byte_order'),
                    'factor': chain.get('factor'),
                    'offset': chain.get('offset_value'),
                },
                'source_ref': hw,
                'technology_binding_ref': technology_contract['technology_id'],
            }]}, 'message_id')

    # A named functional requirement must not disappear behind the generic
    # controller status function. A sole function host is unambiguous; with
    # several hosts an explicit mapping is needed instead of choosing one.
    declared_functions = _declared_function_names(arguments['prompt'])
    existing_function_names = {row['name'].casefold() for row in existing['Function']}
    existing_function_names.update(change['data']['name'].casefold() for change in changes
                                   if change['object_type'] == 'Function')
    missing_functions = [name for name in declared_functions if name.casefold() not in existing_function_names]
    function_hosts = _declared_function_hosts(spec, function_refs)
    if missing_functions:
        if len(function_hosts) != 1:
            raise ValueError('Funktionszuordnung fehlt für: ' + ', '.join(missing_functions)
                             + '. Bitte den ausführenden Controller je Funktion festlegen.')
        for name in missing_functions:
            ensure('Function', name, {'hardware_node_id': hardware_refs[function_hosts[0]],
                'domain': spec['domain'],
                'description': 'Explizit benannte Nutzerfunktion; Ausführung auf dem einzigen Funktionscontroller. '
                               'Ein-/Ausgangszuordnung und funktionale Anforderungen separat prüfen.'}, 'hardware_node_id')

    # The selected cluster technology is the ECU/Gateway backbone. Controllers
    # also need a matching local interface for every endpoint technology they
    # own; otherwise a LIN sensor connected to a CAN-FD ECU is incorrectly
    # translated through the central gateway by the route generator.
    graph_raw = re.search(r'^- Systemcluster-Graph:\s*(\[[^\r\n]*\])\s*$', arguments['prompt'], re.M)
    if graph_raw:
        # A single central gateway must terminate the confirmed controller
        # backbones before routing can validate them. Local sensor/actuator
        # buses belong to their controller and are deliberately excluded.
        gateways = {hardware_refs[str(chain['hardware_name']).casefold()]
                    for chain in spec['chains'] if chain['device_type'] == 'Gateway'}
        if len(gateways) == 1:
            gateway_ref = next(iter(gateways))
            backbones = sorted({
                (chain['interface_type'], chain['transport_network_ref'])
                for cluster in json.loads(graph_raw.group(1))
                for controller in cluster.get('controllers') or []
                for chain in [chain_by_name.get(str(controller.get('ecu') or '').casefold())]
                if chain and chain.get('transport_network_ref')
            })
            for channel_index, (technology, network_ref) in enumerate(backbones, start=1):
                gateway_name = next(chain['hardware_name'] for chain in spec['chains'] if chain['device_type'] == 'Gateway')
                gateway_function = function_refs.get(gateway_name.casefold())
                primary_type = next(chain['interface_type'] for chain in spec['chains'] if chain['device_type'] == 'Gateway')
                if technology != primary_type:
                    ensure('Interface', f'{gateway_name} {technology}', {
                        **({'function_id': gateway_function} if gateway_function else {'hardware_node_id': gateway_ref}),
                        'interface_type': technology,
                    }, 'function_id' if gateway_function else 'hardware_node_id')
                ports = [change['data'] for change in changes
                         if change['object_type'] == 'HardwareNetworkInterface'
                         and change['data'].get('hardware_node_id') == gateway_ref
                         and change['data'].get('technology') == technology]
                if any(port.get('network_ref') == network_ref for port in ports):
                    continue
                unbound = next((port for port in ports if not port.get('network_ref')), None)
                if unbound is not None:
                    unbound.update(network_ref=network_ref, name=named_networks[network_ref]['name'] if is_ethernet(technology) else network_ref)
                    if is_ethernet(technology):
                        unbound.setdefault('capabilities', {}).update(name_source='network', name_network_id=network_ref)
                else:
                    ensure('HardwareNetworkInterface', network_ref, {
                        'hardware_node_id': gateway_ref, 'technology': technology,
                        'channel_index': channel_index, 'network_ref': network_ref,
                    }, 'hardware_node_id')
        for cluster in json.loads(graph_raw.group(1)):
            for controller in cluster.get('controllers') or []:
                if not isinstance(controller, dict):
                    continue
                controller_name = str(controller.get('ecu') or '').strip()
                controller_key = controller_name.casefold()
                hw = hardware_refs.get(controller_key)
                if not hw:
                    continue
                fn = function_refs.get(controller_key)
                endpoint_names = [*(controller.get('sensors') or []), *(controller.get('actuators') or [])]
                local_bindings = {
                    (str(chain.get('interface_type') or ''), str(chain.get('transport_network_ref') or ''))
                    for endpoint_name in endpoint_names
                    for chain in [chain_by_name.get(str(endpoint_name or '').casefold())]
                    if chain and chain.get('interface_type') and chain.get('transport_network_ref')
                }
                for channel_index, (interface_type, network_ref) in enumerate(sorted(local_bindings), start=2):
                    technology_contract = _technology_contract(interface_type)
                    interface_name = f'{controller_name}_{interface_type}_IO'
                    port = ensure('HardwareNetworkInterface', network_ref, {
                        'hardware_node_id': hw,
                        'technology': interface_type,
                        'channel_index': channel_index,
                        'network_ref': network_ref,
                        'capabilities': {
                            'hardware_interface': technology_contract['hardware_interface'],
                            'technology_stack': technology_contract['stack'],
                            **technology_contract['capabilities'],
                        },
                    }, 'hardware_node_id')
                    interface = ensure('Interface', interface_name, {
                        **({'function_id': fn} if fn else {'hardware_node_id': hw}),
                        'configuration': {'physical_interface_ids': [port]},
                        'interface_type': interface_type,
                    }, 'function_id' if fn else 'hardware_node_id')
                    actuator_chains = [
                        chain_by_name.get(str(actuator_name or '').casefold())
                        for actuator_name in controller.get('actuators') or []
                    ]
                    actuator_chains = [
                        chain for chain in actuator_chains
                        if chain
                        and str(chain.get('interface_type') or '') == interface_type
                        and str(chain.get('transport_network_ref') or '') == network_ref
                    ]
                    if actuator_chains:
                        actuator_refs = [
                            hardware_refs[str(chain['hardware_name']).casefold()]
                            for chain in actuator_chains
                            if str(chain.get('hardware_name') or '').casefold() in hardware_refs
                        ]
                        cycle_ms = min(float(chain.get('cycle_ms') or 10) for chain in actuator_chains)
                        dlc = max(int(chain.get('dlc') or 8) for chain in actuator_chains)
                        message_id = (
                            _next_generated_can_identifier(existing['Message'], changes)
                            if _network_protocol(interface_type) in {'CAN', 'CAN_FD', 'CAN_XL'}
                            else None
                        )
                        command_ref = ensure('Message', f'{interface_name}_Command', {
                            'interface_id': interface,
                            'hardware_interface_id': port,
                            **({'message_id_hex': message_id} if message_id else {}),
                            'direction': 'tx',
                            'cycle_ms': cycle_ms,
                            'dlc': dlc,
                            'configuration': {
                                'model_type': 'TransportUnit',
                                'technology_binding': technology_contract,
                                'transport_unit': {
                                    'transport_unit_type': technology_contract['transport_unit_type'],
                                    'producer_ref': hw,
                                    'consumer_refs': actuator_refs,
                                    'payload_size': dlc,
                                    'timing': {'cycle_ms': cycle_ms},
                                    'status': 'PROPOSED',
                                    'provenance': {
                                        'source': 'wizard',
                                        'generator': 'wizard-local-actuator-command',
                                    },
                                },
                            },
                        }, 'interface_id')
                        command_change = next((item for item in changes if '$' + item.get('local_ref', '') == command_ref), None)
                        if command_change:
                            config = command_change['data']['configuration']
                            transport = config['transport_unit']
                            transport['consumer_refs'] = list(dict.fromkeys([*transport['consumer_refs'], *actuator_refs]))
                            bindings = config.setdefault('physical_transmit_bindings', [])
                            if not any(binding['hardware_interface_id'] == port for binding in bindings):
                                bindings.append({'hardware_interface_id': port, 'network_id': network_ref})
    from ..device_communication import complete_new_actuator_messages
    command_definitions = _confirmed_actuator_commands(arguments['prompt'])
    complete_new_actuator_messages(changes, existing, command_definitions)
    # Persist the confirmed graph as identity references, independently of the
    # physical routing derived later. Never replace an explicit existing edit.
    hardware_changes = {"$" + change["local_ref"]: change for change in changes if change["object_type"] == "HardwareNode"}
    existing_hardware = {str(item["id"]): item for item in existing["HardwareNode"]}
    for endpoint, (owner, *_membership) in _confirmed_local_io_memberships(arguments["prompt"]).items():
        endpoint_ref, owner_ref = hardware_refs.get(endpoint), hardware_refs.get(owner)
        if not endpoint_ref or not owner_ref:
            raise ValueError(f"Bestätigte Systemzuordnung fehlt im Modell: {endpoint} → {owner}")
        new_change = hardware_changes.get(endpoint_ref)
        current = new_change["data"] if new_change else existing_hardware[endpoint_ref]
        identity = current.get("identity") or {}
        current_owner = identity.get("system_owner_id") or identity.get("systemOwnerId")
        if current_owner and str(current_owner) != str(owner_ref):
            raise ValueError(f"Bestehende Systemzuordnung von {endpoint} unterscheidet sich vom bestätigten Controller {owner}. "
                "Die Zuordnung und ihre bestehenden Kommunikationspfade benötigen einen explizit geprüften Update-Vorschlag.")
        if current_owner:
            continue
        identity = {**identity, "system_owner_id": owner_ref, "system_owner_source": "wizard-confirmed",
                    "system_owner_evidence": {"source": "confirmed-systemcluster-graph", "endpoint_name": endpoint, "controller_name": owner}}
        if new_change:
            new_change["data"]["identity"] = identity
        else:
            changes.append({"object_type": "HardwareNode", "action": "UPDATE", "object_id": endpoint_ref,
                            "local_ref": f"ownership-{len(changes)}", "data": {"identity": identity}})
    from ..wizard_communication import attach_new_message_contracts
    attach_new_message_contracts(arguments['prompt'], changes, existing)
    _bind_generated_gateway_status(changes, existing)
    # Owners precede their endpoints so nested local references resolve on apply.
    new_hardware = [change for change in changes if change["object_type"] == "HardwareNode" and change.get("action", "CREATE") == "CREATE"]
    new_hardware.sort(key=lambda change: bool((change["data"].get("identity") or {}).get("system_owner_id")))
    changes = new_hardware + [change for change in changes if change not in new_hardware]
    if not changes:
        if not (state.get('artifact_checks', {}).get('engineering_model') or {}).get('complete'):
            raise ValueError('Aus der Ergänzung wurden keine Modelländerungen abgeleitet. '
                'Der vorhandene Modellstand ist noch nicht gültig; die konkreten Modellbefunde müssen zuerst behoben werden.')
        return {'status': 'MODEL_CONFIRMATION_REQUIRED', 'model_revision': model.model_revision(),
                'request_revision': proposal_identity['request_revision'], 'run_id': proposal_identity['run_id'],
                'rationale': 'Aus der Ergänzung wurde keine Modelländerung abgeleitet. '
                    'Bestehenden gültigen Modellstand ausdrücklich bestätigen oder die fachlichen Vorgaben präzisieren.',
                'findings': [{'code': 'AMENDMENT_WITHOUT_MODEL_DELTA', 'object_ref': current_project_id(),
                    'message': 'Es wurde keine Modelländerung vorgeschlagen oder übernommen. '
                        'Die Ergänzung ist noch nicht als Modelländerung bestätigt.'}]}
    proposal = proposal_service.create('WIZARD_ENGINEERING_MODEL', changes,
        f"Engineering-Modell aus bestätigten Wizard-Vorgaben: {len(changes)} vorgeschlagene Änderungen. "
        "Noch keine Änderungen am kanonischen Modell; Freigabe und Übernahme sind erforderlich.",
        assumptions=['Technische Defaults und ergänzte Geräte stammen aus den Wizard-Branchenkatalogen und müssen geprüft werden.',
                     'Lokale Messwerte und Stellbefehle erhalten ihre bestätigten Empfänger. Im lokalen Regelkreis bleibt Controllerstatus ohne ausdrücklich gewählte Ausgabe intern und wird nicht gesendet. Andere Architekturvarianten verwenden Diagnose, Gateway oder einen anderen Controller als Status-Empfänger; diese Simulationsvorgabe ist Bestandteil der Modellfreigabe.',
                     'Schaltausgang und Stellglied sind generische Simulationsvorlagen mit Sollwert und separater Ausführungsmeldung. Reale Aktoren benötigen ihre gerätespezifische Spezifikation.',
                     'Für unbekannte Aktoren müssen Befehl, Bitlänge, Codierung und Wertebereich vor Modellfreigabe bestätigt werden (Aktor-Befehle).',
                     'Dieses Paket umfasst das Engineering-Modell. Routing, Topologie und Simulation folgen nach der Modellfreigabe.'],
        evidence=[*(source_evidence or []), {'source': 'wizard-specification-generator', **proposal_identity, 'target_counts': spec['targetCounts'],
                   'communication_system_counts': spec['communicationSystemCounts'],
                   'model_type': spec.get('modelType') or spec.get('domain'),
                   'generation_policy': spec['generationPolicy'],
                   'architecture': 'HardwareNode -> HardwareInterface -> FunctionalInterface -> TechnologyBinding -> TransportUnit -> PayloadElement'}])
    return _supersede_previous('WIZARD_ENGINEERING_MODEL', proposal_identity, proposals, proposal)


def generate_communication_contract(arguments: dict) -> dict:
    from ..wizard_communication import communication_plan, KINDS
    graph = {kind: {str(row['id']): row for row in model.objects(kind)} for kind in KINDS}
    plan = communication_plan(effective_wizard_prompt(arguments['prompt']), graph)
    changes = [{'object_type': 'Message', 'action': 'UPDATE', 'object_id': identifier,
        'data': {'configuration': config, 'expected_version': graph['Message'][identifier]['version']}}
        for identifier, config in plan.items() if config != graph['Message'][identifier].get('configuration')]
    if not changes:
        return {'status': 'UNCHANGED'}
    fingerprint = hashlib.sha256(json.dumps(changes, sort_keys=True).encode('utf-8')).hexdigest()
    for row in proposal_store.list_proposals(limit=100):
        contract = row.get('engineering_contract') or {}
        if (row['proposal_type'] == 'WIZARD_ENGINEERING_MODEL'
                and contract.get('status') in {'PROPOSED', 'VALIDATED', 'APPROVED'}
                and any(item.get('source') == 'wizard-communication-contract'
                        and item.get('plan_sha256') == fingerprint for item in row.get('evidence') or [])):
            return proposal_service.envelope(row)
    return proposal_service.create('WIZARD_ENGINEERING_MODEL', changes,
        f'Kommunikationsplan vervollständigen: {len(changes)} Nachrichten erhalten explizite Empfänger und einen Kommunikationszweck.',
        assumptions=['Gerätestatus wird von Diagnose, sonst Gateway bzw. einem anderen Controller überwacht. Bestehende explizite Empfänger bleiben erhalten.'],
        evidence=[{'source': 'wizard-communication-contract', 'version': 1, 'plan_sha256': fingerprint}])


def generate_routing(arguments: dict) -> dict:
    """Turn the confirmed cluster ownership graph into one reviewable route proposal.

    This continuation is deliberately deterministic. A completed mass-created
    model must not depend on a language model deciding whether to call hundreds
    of route tools.
    """
    prompt = _canonical_wizard_prompt(arguments['prompt'])
    state = WorkflowStatusService(current_project_id()).get()
    nodes = model.objects('HardwareNode')
    interfaces = model.objects('Interface')
    functions = model.objects('Function')
    signals = model.objects('Signal')
    hardware_interfaces = model.objects('HardwareNetworkInterface')
    messages = model.objects('Message')
    existing_routes = model.routes()
    identity = _proposal_identity('routing', prompt, {
        'HardwareNode': nodes, 'Interface': interfaces, 'Function': functions, 'Signal': signals,
        'HardwareNetworkInterface': hardware_interfaces, 'Message': messages, 'RoutingEntry': existing_routes,
    }, state, ROUTING_GENERATOR_VERSION)
    proposals = proposal_store.list_proposals(limit=100)
    reusable = _reusable_proposal('WIZARD_ROUTING', identity, proposals)
    if reusable:
        return reusable
    prompt = effective_wizard_prompt(prompt)
    raw = re.search(r'^- Systemcluster-Graph:\s*(\[[^\r\n]*\])\s*$', prompt, re.M)
    if not raw:
        raise ValueError('Der bestätigte Systemcluster-Graph fehlt; Routing kann nicht reproduzierbar erzeugt werden.')
    graph = json.loads(raw.group(1))
    from ..wizard_communication import hmi_message_choices
    hmi_choices = hmi_message_choices(graph, {
        'HardwareNode': {str(item['id']): item for item in nodes},
        'Interface': {str(item['id']): item for item in interfaces},
        'Function': {str(item['id']): item for item in functions},
        'Message': {str(item['id']): item for item in messages},
        'Signal': {str(item['id']): item for item in signals},
    }) if any('excluded_signals' in route for cluster in graph for route in cluster.get('hmi_routes') or []) else {}
    nodes_by_name = {str(item.get('name', '')).casefold(): item for item in nodes}
    interfaces_by_node: dict[str, list[dict]] = {}
    for item in interfaces:
        node_id = str(item.get('hardware_node_id') or '')
        if node_id:
            interfaces_by_node.setdefault(node_id, []).append(item)
    messages_by_interface: dict[str, list[dict]] = {}
    for item in messages:
        messages_by_interface.setdefault(str(item.get('interface_id') or ''), []).append(item)
    hardware_interfaces_by_node: dict[str, list[dict]] = {}
    for item in hardware_interfaces:
        node_id = str(item.get('hardware_node_id') or '')
        if node_id:
            hardware_interfaces_by_node.setdefault(node_id, []).append(item)

    def node(name):
        return nodes_by_name.get(str(name or '').casefold())

    referenced_names = set()
    for cluster in graph:
        for controller in cluster.get('controllers') or []:
            referenced_names.add(controller.get('ecu'))
            referenced_names.update(controller.get('sensors') or [])
            referenced_names.update(controller.get('actuators') or [])
        for hmi in cluster.get('hmi_routes') or []:
            if 'excluded_signals' not in hmi or hmi.get('signals'):
                referenced_names.update((hmi.get('source'), hmi.get('target')))
    missing = sorted(str(name or '<ohne Namen>') for name in referenced_names if not node(name))
    if missing:
        raise ValueError('Bestätigte Routing-Teilnehmer fehlen im kanonischen Modell: ' + ', '.join(missing[:30]))

    def tx_messages(node_id: str, destination_id: str):
        return [message for interface in interfaces_by_node.get(node_id, [])
                for message in messages_by_interface.get(str(interface['id']), [])
                if str(message.get('direction') or 'tx').casefold() in {'tx', 'bidirectional'}
                and (not consumers(message) or destination_id in consumers(message))]

    def consumers(message: dict) -> set[str]:
        return {str(ref) for ref in ((message.get('configuration') or {}).get('transport_unit') or {}).get('consumer_refs') or []}

    def local_tx_message(source_id: str, destination_id: str):
        source_ports = hardware_interfaces_by_node.get(source_id, [])
        destination_ports = hardware_interfaces_by_node.get(destination_id, [])
        shared_source_port_ids = {
            str(source_port['id'])
            for source_port in source_ports
            if source_port.get('network_ref')
            and any(
                source_port.get('network_ref') == destination_port.get('network_ref')
                and source_port.get('technology') == destination_port.get('technology')
                for destination_port in destination_ports
            )
        }
        candidates = [
            message
            for interface in interfaces_by_node.get(source_id, [])
            for message in messages_by_interface.get(str(interface['id']), [])
            if message_hardware_interface_ids(message) & shared_source_port_ids
            and str(message.get('direction') or '').casefold() == 'tx'
        ]
        targeted = [
            message for message in candidates
            if destination_id in {
                str(ref) for ref in (
                    ((message.get('configuration') or {}).get('transport_unit') or {}).get('consumer_refs') or []
                )
            }
        ]
        selected = (targeted or candidates)
        return bool(shared_source_port_ids), [str(message['id']) for message in selected]

    route_service = RoutingGenerationService()
    # The confirmed model cannot change during this proposal transaction.
    # Reuse one physical graph instead of rebuilding all bus memberships for
    # every message/consumer pair in a large project.
    graph_snapshot = route_service._hardware_graph()
    route_service._hardware_graph = lambda: graph_snapshot
    existing_keys = {(str((route.get('source') or {}).get('node_id')), str(destination.get('node_id')),
                      str((route.get('payload') or {}).get('message_id')))
                     for route in existing_routes for destination in route.get('destinations') or []}
    changes, seen = [], set()
    excluded_forwarding = []
    from ..routing.payload_scope import payload_scope_issues
    scope_messages = {str(item['id']): item for item in messages}
    scope_signals = {str(item['id']): item for item in signals}
    scope_interfaces = {str(item['id']): item for item in interfaces}

    def add_routes(source, destination, *, local_actuator=False):
        if not source or not destination or str(source['id']) == str(destination['id']):
            return
        source_id = str(source['id'])
        destination_id = str(destination['id'])
        has_local_transport, local_message_ids = local_tx_message(source_id, destination_id) if local_actuator else (False, [])
        message_ids = local_message_ids if has_local_transport else [str(message['id']) for message in tx_messages(source_id, destination_id)]
        if has_local_transport and not message_ids:
            raise ValueError(
                f'Lokale Aktorroute {source["name"]} → {destination["name"]} besitzt keine TX-Message '
                'auf einem gemeinsamen logischen und physischen Interface.'
            )
        for message_id in message_ids:
            add_route(source, destination, message_id)

    def add_route(source, destination, message_id):
        source_id, destination_id = str(source['id']), str(destination['id'])
        if hmi_choices.get((message_id, destination_id)) is False:
            return
        key = (source_id, destination_id, message_id)
        if key in seen:
            return
        seen.add(key)
        options = interfaces_by_node.get(destination_id) or [{}]
        exclusions = [payload_scope_issues({'payload': {'message_ids': [message_id]}, 'destinations': [
            {'node_id': destination_id, 'interface_id': str(interface.get('id') or '')}]},
            scope_messages, scope_signals, scope_interfaces) for interface in options]
        if all(any(issue['code'] in {'MESSAGE_ROUTING_DISABLED', 'SIGNAL_ROUTING_DISABLED'} for issue in issues)
               for issues in exclusions):
            excluded_forwarding.extend({**issue, 'source_node_id': source_id} for issue in exclusions[0]
                                       if issue['code'] in {'MESSAGE_ROUTING_DISABLED', 'SIGNAL_ROUTING_DISABLED'})
            return
        if key in existing_keys:
            return
        route = route_service.generate_route(source_node_id=key[0], destination_node_id=key[1], message_id=message_id)
        source_protocol = str(route.get('source', {}).get('protocol') or '')
        destination_protocol = str((route.get('destinations') or [{}])[0].get('protocol') or '')
        if source_protocol != destination_protocol:
            transformation = {
                'type': 'PROTOCOL_TRANSLATION',
                'from_protocol': source_protocol,
                'to_protocol': destination_protocol,
                'reason': 'Explizite Gateway-Übersetzung für den HMI-/Domänenübergang.',
            }
            route['route']['transformations'] = [transformation]
            # Preserve the actual discovered path, including multiple gateways.
            # A translation label must never insert an unrelated project gateway
            # or hide a missing physical path from validation.
        changes.append({'object_type': 'RoutingEntry', 'data': route})

    with routing_candidate_batch(route_service):
        for cluster in graph:
            for controller in cluster.get('controllers') or []:
                ecu = node(controller.get('ecu'))
                for sensor_name in controller.get('sensors') or []:
                    add_routes(node(sensor_name), ecu)
                for actuator_name in controller.get('actuators') or []:
                    add_routes(ecu, node(actuator_name), local_actuator=True)
                    add_routes(node(actuator_name), ecu)
            for hmi_route in cluster.get('hmi_routes') or []:
                if 'excluded_signals' in hmi_route and not hmi_route.get('signals'):
                    continue
                add_routes(node(hmi_route.get('source')), node(hmi_route.get('target')))
        for interface_list in interfaces_by_node.values():
            for interface in interface_list:
                for message in messages_by_interface.get(str(interface['id']), []):
                    source = next((item for item in nodes if str(item['id']) == str(interface.get('hardware_node_id') or '')), None)
                    for consumer_id in sorted(consumers(message)):
                        destination = next((item for item in nodes if str(item['id']) == consumer_id), None)
                        if source and destination:
                            add_route(source, destination, str(message['id']))
    if not changes:
        if seen:
            return {'status': 'UNCHANGED', 'existing_route_count': len(seen) - len(excluded_forwarding),
                    'excluded_forwarding': excluded_forwarding}
        raise ValueError('Aus dem bestätigten Systemcluster-Graph konnten keine prüfbaren Routen abgeleitet werden.')
    proposal = proposal_service.create(
        'WIZARD_ROUTING', changes,
        f'{len(changes)} Kommunikationsrouten aus den bestätigten Controller-Zuordnungen. '
        'Der kanonische Projektstand bleibt bis zur Freigabe unverändert.',
        assumptions=['Controller-Besitz bestimmt Sensor- und Aktor-Richtung; physische Pfade bleiben Gegenstand der Routing-Prüfung.'],
        evidence=[{'source': 'confirmed-system-cluster-graph', **identity, 'route_count': len(changes),
                   'excluded_forwarding': excluded_forwarding}],
    )
    return _supersede_previous('WIZARD_ROUTING', identity, proposals, proposal)


def _topology_bus(value: str | None) -> str:
    key = re.sub(r'[^A-Z0-9]+', '_', str(value or '').upper()).strip('_')
    if key in _TOPOLOGY_BUS_BY_PROTOCOL:
        return _TOPOLOGY_BUS_BY_PROTOCOL[key]
    # A missing mapping is not evidence for an automotive Ethernet connection.
    aliases = {'ARINC': 'arinc429', 'MODBUSTCP': 'modbus_tcp', 'MODBUSRTU': 'modbus_rtu', 'OPCUA': 'opc_ua'}
    technology = aliases.get(key, DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(value))
    try:
        return DEFAULT_TECHNOLOGY_REGISTRY.profile(technology)['id']
    except KeyError as error:
        raise ValueError(f'Anschlusstechnik {value!r} ist nicht eindeutig unterstützt. Bitte den physischen Anschluss festlegen; es wird kein Ersatznetz erzeugt.') from error


_SEMANTIC_NETWORK_FAMILIES = (
    ('powertrain', 'Antriebsstrang', ('motor', 'engine', 'antrieb', 'powertrain', 'kraftstoff', 'fuel', 'abgas', 'exhaust', 'getriebe', 'transmission', 'kupplung', 'clutch', 'drehmoment', 'torque', 'elektromotor', 'inverter', 'ladesteuerung')),
    ('energy', 'Energieversorgung', ('energie', 'energy', 'batterie', 'battery', 'bms', 'bordnetz', 'alternator', 'generator', 'spannung', 'voltage', 'strom', 'current')),
    ('chassis', 'Fahrwerk / Fahrdynamik', ('fahrwerk', 'fahrdynamik', 'bremse', 'brems', 'brake', 'lenkung', 'steering', 'suspension', 'daempfer', 'damper', 'reifen', 'tire', 'wheel', 'stabilitaet', 'allrad', 'anhaenger')),
    ('safety', 'Passive Sicherheit', ('airbag', 'restraint', 'rueckhalt', 'crash', 'impact', 'seatbelt', 'gurt')),
    ('driver-assistance', 'Fahrerassistenz', ('adas', 'fahrerassistenz', 'radar', 'kamera', 'camera', 'lidar', 'park', 'parking', 'spur', 'lane', 'ultraschall')),
    ('body-comfort', 'Karosserie / Komfort', ('karosserie', 'body', 'komfort', 'comfort', 'wischer', 'wiper', 'tuer', 'door', 'fenster', 'window', 'sitz', 'seat', 'keyless', 'heckklappe', 'tailgate', 'licht', 'light')),
    ('climate', 'Klima / Thermik', ('klima', 'climate', 'hvac', 'thermal', 'thermo', 'kuehlung', 'kuehl', 'kuehlkreislauf', 'cooling', 'kompressor', 'compressor', 'innenraum', 'cabin', 'refrigerant')),
    ('infotainment', 'Infotainment', ('infotainment', 'display', 'kombiinstrument', 'headup', 'audio', 'sound', 'telematik', 'navigation', 'connectivity', 'konnektivitaet')),
    ('diagnostics', 'Diagnose', ('diagnose', 'diagnostic', 'service', 'uds', 'obd', 'logging', 'trace')),
)


def _semantic_text(value: object) -> str:
    text = str(value or '').casefold()
    for source, target in (('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'), ('ß', 'ss')):
        text = text.replace(source, target)
    return re.sub(r'[^a-z0-9]+', '', text)


def _semantic_slug(value: object) -> str:
    text = str(value or '').casefold()
    for source, target in (('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'), ('ß', 'ss')):
        text = text.replace(source, target)
    return re.sub(r'(^-|-$)', '', re.sub(r'[^a-z0-9]+', '-', text))


def _confirmed_segment_memberships(prompt: str) -> dict[str, list[tuple[str, str, int]]]:
    """Map confirmed graph participants to their approved gateway segment.

    Variant 4 uses the configured participant limit per physical bus. Only the
    controllers belong to that backbone; low-level endpoints are mapped to
    separate local I/O segments by ``_confirmed_local_io_memberships``.
    """
    architecture = re.search(r'^- Netzarchitektur-ID:\s*([^\r\n]+)', prompt, re.M)
    if not architecture or architecture.group(1).strip().casefold() != 'gateway_ecu_segments':
        return {}
    raw = re.search(r'^- Systemcluster-Graph:\s*(\[[^\r\n]*\])\s*$', prompt, re.M)
    if not raw:
        return {}
    graph = json.loads(raw.group(1))
    limits = limits_from_prompt(prompt)
    memberships: dict[str, list[tuple[str, str, int]]] = {}
    for cluster in graph:
        controllers = [item for item in cluster.get('controllers') or [] if isinstance(item, dict)]
        label = str(cluster.get('label') or cluster.get('cluster_id') or 'Netzsegment').strip()
        base_id = str(cluster.get('bus_name') or _semantic_slug(label) or 'network').strip()
        technology = cluster.get('technology_id') or cluster.get('technology') or cluster.get('network_id') or 'CAN_FD'
        capacity = branch_capacity(limits, technology)
        for index, controller in enumerate(controllers):
            ordinal = index // capacity + 1
            segment_id = f'{base_id}-S{ordinal:02d}'
            membership = (segment_id, label, ordinal)
            for member in [controller.get('ecu')]:
                key = str(member or '').strip().casefold()
                if key and membership not in memberships.setdefault(key, []):
                    memberships[key].append(membership)
    return memberships


def _confirmed_local_io_memberships(prompt: str, technologies: dict | None = None) -> dict[str, tuple]:
    """Return endpoint -> (owner, base id, label, stable index)."""
    raw = re.search(r'^- Systemcluster-Graph:\s*(\[[^\r\n]*\])\s*$', prompt, re.M)
    if not raw:
        return {}
    memberships: dict[str, tuple] = {}
    architecture = architecture_from(prompt=prompt)
    for cluster in json.loads(raw.group(1)):
        label = str(cluster.get('label') or cluster.get('cluster_id') or 'Netzsegment').strip()
        base_id = str(cluster.get('bus_name') or _semantic_slug(label) or 'network').strip()
        for controller in cluster.get('controllers') or []:
            if not isinstance(controller, dict):
                continue
            owner = str(controller.get('ecu') or '').strip()
            endpoints = [*(controller.get('sensors') or []), *(controller.get('actuators') or [])]
            technology_indices = {}
            for index, endpoint in enumerate(sorted(endpoints, key=lambda value: [
                    (0, int(part)) if part.isdigit() else (1, part) for part in re.split(r'(\d+)', str(value).casefold())])):
                technology = (technologies or {}).get(str(endpoint).casefold())
                side = driving_side_from_prompt(prompt)
                zone = installation_zone(endpoint, driving_side=side, architecture=architecture)
                counter_key = (technology, zone if technology in LOCAL_BUSES else 'UNKNOWN')
                if technology is not None:
                    index = technology_indices.get(counter_key, 0)
                    technology_indices[counter_key] = index + 1
                key = str(endpoint or '').strip().casefold()
                if key and owner:
                    if key in memberships and memberships[key][0] != owner.casefold():
                        raise ValueError(f'Endpunkt {endpoint} ist mehreren System-Ownern zugeordnet.')
                    memberships[key] = (owner.casefold(), base_id, label, index, limits_from_prompt(prompt), zone, owner, zone_label(zone, architecture))
    return memberships


def _local_io_physical_network(
    bus: str,
    memberships: dict[str, tuple[str, str, str, int]],
    *items: dict,
) -> tuple[str, str] | None:
    names = {str(item.get('name') or '').strip().casefold() for item in items}
    for item in items:
        endpoint_name = str(item.get('name') or '').strip().casefold()
        membership = memberships.get(endpoint_name)
        if not membership:
            continue
        owner, base_id, _label, index, *settings = membership
        if owner not in names:
            continue
        group_size = branch_capacity(settings[0] if settings else limits_from_prompt(''), bus)
        ordinal = index // group_size + 1
        technology = bus.replace('_', '-')
        display = 'CAN' if bus == 'can_fd' else 'Ethernet' if bus == 'automotive_ethernet' else bus.upper()
        owner_name = next(
            str(candidate.get('name') or '') for candidate in items
            if str(candidate.get('name') or '').strip().casefold() == owner
        )
        if len(settings) > 2:
            owner_name = settings[2]
        network_id = f'{base_id}-IO-{_semantic_slug(owner_name)}-{technology}-S{ordinal:02d}'
        zone = settings[1] if len(settings) > 1 else 'UNKNOWN'
        if zone != 'UNKNOWN' and bus in LOCAL_BUSES:
            network_id = f'{base_id}-IO-{_semantic_slug(owner_name)}-{technology}-{zone}-S{ordinal:02d}'
            return network_id, f'{owner_name} {bus.replace("_", " ").upper()} {settings[3] if len(settings) > 3 else zone_label(zone)} {ordinal:02d}'
        return network_id, f'{owner_name} {display} I/O Segment {ordinal}'
    return None


def _segmented_physical_network(
    bus: str,
    memberships: dict[str, list[tuple[str, str, int]]],
    *items: dict,
) -> tuple[str, str] | None:
    candidates = [
        memberships.get(str(item.get('name') or '').strip().casefold(), [])
        for item in items
        if str(item.get('device_type') or '') != 'Gateway'
    ]
    candidates = [item for item in candidates if item]
    if not candidates:
        return None
    shared = list(candidates[0])
    for values in candidates[1:]:
        value_ids = {item[0] for item in values}
        shared = [item for item in shared if item[0] in value_ids]
    if not shared:
        return None
    segment_id, label, ordinal = shared[0]
    display = 'CAN' if bus == 'can_fd' else 'Ethernet' if bus == 'automotive_ethernet' else bus.upper()
    return segment_id, f'{label}-{display} Segment {ordinal}'


def _semantic_physical_network(bus: str, *items: dict) -> tuple[str, str] | None:
    candidates = []
    for item_index, item in enumerate(items):
        name = _semantic_text(item.get('name'))
        is_controller = str(item.get('device_type') or '') not in {'SensorController', 'ActuatorController', 'Gateway'}
        for family_index, (key, label, terms) in enumerate(_SEMANTIC_NETWORK_FAMILIES):
            specificity = max((len(_semantic_text(term)) for term in terms if engineering_phrase_match(str(item.get("name") or ""), term)), default=0)
            if specificity:
                candidates.append((10_000 if is_controller else 0, specificity, -family_index, -item_index, key, label))
    if not candidates:
        return None
    _controller, _specificity, _family_index, _item_index, _key, label = max(candidates)
    technology = bus.replace('_', '-')
    display = 'CAN' if bus == 'can_fd' else 'Ethernet' if bus == 'automotive_ethernet' else bus.upper()
    return f'{_semantic_slug(label)}-{technology}-bus', f'{label}-{display}'


def generate_network_topology(arguments: dict) -> dict:
    """Materialize approved logical routes as a reviewable physical topology.

    Every canonical hardware participant is represented exactly once. Physical
    edges are derived only from approved, valid routes; duplicate route
    segments share one edge and retain all contributing route IDs.
    """
    workflow_state = WorkflowStatusService(current_project_id()).get()
    prompt = with_spatial_architecture(effective_wizard_prompt(arguments['prompt']), workflow_state.get('parameters'))
    existing_topology = workflow_state.get('topology') or {}
    existing_nodes = {str(item.get('engineeringId') or ''): item for item in existing_topology.get('nodes') or []}
    existing_node_ids = {str(item.get('id') or ''): str(item.get('engineeringId') or '') for item in existing_nodes.values()}
    existing_segments = {}
    for edge in existing_topology.get('edges') or []:
        left, right = (existing_node_ids.get(str(edge.get(side) or ''), '') for side in ('source', 'target'))
        if left and right:
            existing_segments.setdefault((frozenset((left, right)), str(edge.get('bus') or '')), []).append(edge)
    hardware = sorted(model.objects('HardwareNode'), key=lambda item: (str(item.get('name', '')).casefold(), str(item['id'])))
    interfaces = model.objects('HardwareNetworkInterface')
    routes = [route for route in model.routes()
              if str(route.get('approval_state') or '').upper() == 'APPROVED'
              and (route.get('validation') or {}).get('valid') is True]
    if len(hardware) < 2:
        raise ValueError('Für eine Netzwerktopologie werden mindestens zwei kanonische Hardwareknoten benötigt.')
    if not routes:
        raise ValueError('Es existieren keine freigegebenen, validen Routen als Grundlage der Netzwerktopologie.')

    hardware_by_id = {str(item['id']): item for item in hardware}
    interfaces_by_node: dict[str, list[dict]] = {}
    for interface in interfaces:
        interfaces_by_node.setdefault(str(interface.get('hardware_node_id') or ''), []).append(interface)
    for values in interfaces_by_node.values():
        values.sort(key=lambda item: (str(item.get('technology', '')), str(item.get('name', '')), str(item['id'])))
    segment_memberships = _confirmed_segment_memberships(prompt)
    local_io_memberships = _confirmed_local_io_memberships(prompt, {str(h['name']).casefold(): _topology_bus(interfaces_by_node.get(str(h['id']), [{}])[0].get('technology')) for h in hardware if interfaces_by_node.get(str(h['id']))})

    kind_by_type = {
        'Gateway': 'gateway',
        'SensorController': 'sensor',
        'ActuatorController': 'actuator',
    }
    node_data: dict[str, dict] = {}
    port_refs: dict[tuple[str, str, str], str] = {}

    def reviewed_network(left, right, bus, *endpoints):
        saved = existing_segments.get((frozenset((left, right)), bus), [])
        preferred = [str(endpoint.get('network_id') or '') for endpoint in endpoints if endpoint.get('network_id')]
        selected = next((edge for network in preferred for edge in saved if str(edge.get('physicalNetworkId') or '') == network), None)
        if selected is None and len({str(edge.get('physicalNetworkId') or '') for edge in saved}) == 1:
            selected = saved[0]
        if selected and selected.get('physicalNetworkId'):
            return str(selected['physicalNetworkId']), str(selected.get('physicalNetworkName') or selected['physicalNetworkId'])
        for endpoint in endpoints:
            network = str(endpoint.get('network_id') or '')
            if network and all(any(str(interface.get('network_ref') or '') == network and _topology_bus(interface.get('technology')) == bus
                    for interface in interfaces_by_node.get(node_id, [])) for node_id in (left, right)):
                return network, str(endpoint.get('network_name') or network)
        return None

    def ensure_port(node_id: str, bus: str, network_id: str = '', network_name: str = '') -> str:
        key = (node_id, bus, network_id)
        if key in port_refs:
            return port_refs[key]
        candidates = interfaces_by_node.get(node_id, [])
        matching = [item for item in candidates if _topology_bus(item.get('technology')) == bus]
        saved_port = next((port for port in existing_nodes.get(node_id, {}).get('ports') or []
            if str(port.get('bus') or '') == bus and str(port.get('physicalNetworkId') or '') == network_id), None)
        interface = next((item for item in matching if str(item['id']) == str((saved_port or {}).get('hardwareInterfaceId') or '')),
            next((item for item in matching if str(item.get('network_ref') or '') == network_id), next((item for item in matching if not item.get('network_ref')), None)))
        network_suffix = f'-{network_id}' if network_id else ''
        port_id = str((saved_port or {}).get('id') or f'topology-port-{node_id}-{bus}{network_suffix}')
        port = {
            **deepcopy(saved_port or {}),
            'id': port_id,
            'name': network_name or str(interface.get('name') if interface else f'{bus}-Port'),
            'bus': bus,
            'side': (saved_port or {}).get('side', 'right'),
            'offset': (saved_port or {}).get('offset', 0.5),
        }
        if network_id:
            port['physicalNetworkId'] = network_id
            port['physicalNetworkName'] = network_name
        if interface is not None:
            port.update({
                'engineeringId': str(interface['id']),
                'hardwareInterfaceId': str(interface['id']),
            })
        node_data[node_id]['ports'].append(port)
        port_refs[key] = port_id
        return port_id

    for index, item in enumerate(hardware):
        identifier = str(item['id'])
        node_data[identifier] = {
            **deepcopy(existing_nodes.get(identifier) or {}),
            'id': str((existing_nodes.get(identifier) or {}).get('id') or f'topology-node-{identifier}'),
            'name': item['name'],
            'kind': kind_by_type.get(str(item.get('device_type')), 'ecu'),
            'x': (existing_nodes.get(identifier) or {}).get('x', 80 + (index % 10) * 220),
            'y': (existing_nodes.get(identifier) or {}).get('y', 80 + (index // 10) * 150),
            'ports': [],
            'engineeringId': identifier,
        }

    segments: dict[tuple[str, str, str, str], dict] = {}
    for route in sorted(routes, key=lambda item: (str(item.get('route_code', '')), str(item['id']))):
        source = str((route.get('source') or {}).get('node_id') or '')
        destinations = [str(item.get('node_id') or '') for item in route.get('destinations') or [] if isinstance(item, dict)]
        route_hops = [str(item.get('node_id') or '') for item in (route.get('route') or {}).get('hops') or [] if isinstance(item, dict)]
        source_bus = _topology_bus((route.get('source') or {}).get('protocol'))
        for destination_index, destination in enumerate(destinations):
            if source not in hardware_by_id or destination not in hardware_by_id:
                continue
            destination_bus = _topology_bus(((route.get('destinations') or [])[destination_index] or {}).get('protocol'))
            path = [node_id for node_id in route_hops if node_id in hardware_by_id]
            if not path or path[0] != source or path[-1] != destination:
                path = [source, destination]
            for segment_index, (left, right) in enumerate(zip(path, path[1:])):
                bus = source_bus if segment_index == 0 else destination_bus
                network = (
                    reviewed_network(left, right, bus,
                        *((route.get('source') or {},) if segment_index == 0 else ()),
                        *((route['destinations'][destination_index],) if right == destination else ()))
                    or
                    _local_io_physical_network(
                        bus, local_io_memberships, hardware_by_id[left], hardware_by_id[right]
                    )
                    or
                    _segmented_physical_network(
                        bus, segment_memberships, hardware_by_id[left], hardware_by_id[right]
                    )
                    or _semantic_physical_network(bus, hardware_by_id[left], hardware_by_id[right])
                )
                network_id, network_name = network or ('', '')
                key = (left, right, bus, network_id)
                reverse_key = (right, left, bus, network_id)
                segment = segments.get(key) or segments.get(reverse_key)
                route_id = str(route['id'])
                if segment:
                    segment['routingEntryIds'] = sorted(set([*segment['routingEntryIds'], route_id]))
                    segment['routingMetadata'][route_id] = {
                        'routeId': route_id,
                        'routeCode': str(route.get('route_code') or ''),
                        'name': str(route.get('name') or ''),
                        'source': source,
                        'target': destination,
                        'protocol': str((route.get('source') or {}).get('protocol') or ''),
                        'approvalState': 'APPROVED',
                    }
                    continue
                source_port = ensure_port(left, bus, network_id, network_name)
                target_port = ensure_port(right, bus, network_id, network_name)
                saved_edge = next((edge for edge in existing_segments.get((frozenset((left, right)), bus), [])
                    if str(edge.get('physicalNetworkId') or '') == network_id), {})
                edge_id = str(saved_edge.get('id') or 'topology-edge-' + hashlib.sha256(json.dumps(key).encode()).hexdigest()[:16])
                segments[key] = {
                    **deepcopy(saved_edge),
                    'id': edge_id,
                    'name': f'{hardware_by_id[left]["name"]} — {hardware_by_id[right]["name"]}',
                    'source': node_data[left]['id'],
                    'sourcePort': source_port,
                    'target': node_data[right]['id'],
                    'targetPort': target_port,
                    'bus': bus,
                    **({'physicalNetworkId': network_id, 'physicalNetworkName': network_name} if network_id else {}),
                    'direction': 'BIDIRECTIONAL',
                    'relationType': 'CONNECTED_VIA',
                    'engineeringSegmentId': f'{route_id}:segment:{segment_index}',
                    'routingEntryId': route_id,
                    'routingEntryIds': [route_id],
                    'routingMetadata': {route_id: {
                        'routeId': route_id,
                        'routeCode': str(route.get('route_code') or ''),
                        'name': str(route.get('name') or ''),
                        'source': source,
                        'target': destination,
                        'protocol': str((route.get('source') or {}).get('protocol') or ''),
                        'approvalState': 'APPROVED',
                    }},
                    'origin': 'ROUTING_TABLE',
                }

    if not segments:
        raise ValueError('Aus den freigegebenen Routen konnten keine physischen Segmente erzeugt werden.')
    # Physical connectivity is independent of route approval. Preserve reviewed
    # wiring even when a payload is invalid or no logical traffic uses it.
    fallback_count = 0
    for edge in existing_topology.get('edges') or []:
        left = existing_node_ids.get(str(edge.get('source') or ''))
        right = existing_node_ids.get(str(edge.get('target') or ''))
        network = str(edge.get('physicalNetworkId') or '')
        bus = str(edge.get('bus') or '')
        if left not in node_data or right not in node_data or not network:
            continue
        if (left, right, bus, network) in segments or (right, left, bus, network) in segments:
            continue
        preserved = deepcopy(edge)
        preserved.update(sourcePort=ensure_port(left, bus, network, edge.get('physicalNetworkName') or network),
                         targetPort=ensure_port(right, bus, network, edge.get('physicalNetworkName') or network),
                         routingEntryIds=[], routingMetadata={}, origin='PRESERVED_PHYSICAL_TOPOLOGY')
        preserved.pop('routingEntryId', None)
        segments[(left, right, bus, network)] = preserved
    # Do not fabricate wiring from spelling similarity or protocol alone.
    # Isolated hardware remains visibly isolated until a binding is specified.
    # A controller's declared message port exists independently of consumers.
    # Keep such ports visible even when the routing model has no receiver yet.
    declared_network_names = {str(n['id']): str(n.get('name') or n['id']) for n in model.networks()}
    message_ports = {str(message.get('hardware_interface_id') or '') for message in model.objects('Message')}
    saved_ports = {str(port.get('hardwareInterfaceId') or '') for node in existing_nodes.values() for port in node.get('ports') or []}
    for interface in interfaces:
        node_id = str(interface.get('hardware_node_id') or '')
        network_id = str(interface.get('network_ref') or '')
        if node_id in node_data and network_id and str(interface['id']) in message_ports | saved_ports:
            ensure_port(node_id, _topology_bus(interface.get('technology')), network_id,
                        declared_network_names.get(network_id, network_id))
    # A shared canonical network is explicit physical membership, even without
    # traffic. Connect its components; never cross networks by name similarity.
    bus_members = {}
    for (node_id, bus, network), port_id in port_refs.items():
        if network:
            bus_members.setdefault((bus, network), []).append((node_id, port_id))
    for (bus, network), members in bus_members.items():
        members.sort(key=lambda member: (hardware_by_id[member[0]].get('device_type') != 'Gateway', member[0]))
        if len(members) < 2:
            continue
        anchor, anchor_port = members[0]
        adjacency = {}
        for (left, right, edge_bus, edge_network) in segments:
            if edge_bus == bus and edge_network == network:
                adjacency.setdefault(left, set()).add(right)
                adjacency.setdefault(right, set()).add(left)
        def reachable(start):
            seen, todo = {start}, [start]
            while todo:
                for other in adjacency.get(todo.pop(), set()):
                    if other not in seen:
                        seen.add(other)
                        todo.append(other)
            return seen
        for node_id, port_id in members[1:]:
            if node_id in reachable(anchor):
                continue
            key = (anchor, node_id, bus, network)
            identifier = 'canonical-bus-' + hashlib.sha256(json.dumps(key).encode()).hexdigest()[:16]
            segments[key] = {'id': identifier, 'name': f'{hardware_by_id[anchor]["name"]} — {hardware_by_id[node_id]["name"]}',
                'source': node_data[anchor]['id'], 'target': node_data[node_id]['id'],
                'sourcePort': anchor_port, 'targetPort': port_id, 'bus': bus,
                'physicalNetworkId': network, 'physicalNetworkName': declared_network_names.get(network, network),
                'direction': 'BIDIRECTIONAL', 'relationType': 'CONNECTED_VIA',
                'engineeringSegmentId': identifier, 'routingEntryIds': [], 'routingMetadata': {}, 'origin': 'CANONICAL_BUS_BINDING'}
            adjacency.setdefault(anchor, set()).add(node_id)
            adjacency.setdefault(node_id, set()).add(anchor)
    topology = {'nodes': list(node_data.values()), 'edges': list(segments.values())}
    topology, physical_changes = materialize_physical_ports(topology, hardware, interfaces, model.networks(),
        routes=routes, messages=model.objects('Message'), prune_unconnected=False)
    from ..network_scene import build_network_scene
    positions = (existing_topology.get('scene') or {}).get('manualPositions')
    if not existing_topology.get('scene'):
        # Existing, explicitly positioned nodes survive a model refresh as well.
        positions = {node['id']: {key: node[key] for key in ('x', 'y', 'width', 'height') if key in node}
                     for node in existing_topology.get('nodes', []) if 'x' in node and 'y' in node}
    topology = build_network_scene(topology, prompt, positions=positions)
    policy = planning_policy(workflow_state)
    resource_receipt = resource_decision(workflow_state.get('topology') or {}, topology,
        planning_inventory(workflow_state, prompt), policy)
    state_signature = hashlib.sha256(json.dumps({
        'nodes': [(item['id'], item.get('version')) for item in hardware],
        'interfaces': [(item['id'], item.get('version'), item.get('technology')) for item in interfaces],
        'routes': [(item['id'], item.get('revision'), item.get('approval_state')) for item in routes],
        'resource_decision': resource_receipt,
    }, sort_keys=True).encode('utf-8')).hexdigest()
    fingerprint = hashlib.sha256(('wizard-network-v8-persisted-scene\n' + prompt + '\n' + state_signature).encode('utf-8')).hexdigest()
    for row in proposal_store.list_proposals(limit=100):
        contract = row.get('engineering_contract') or {}
        if (row['proposal_type'] == 'WIZARD_NETWORK_TOPOLOGY'
                and any(item.get('prompt_sha256') == fingerprint for item in row.get('evidence') or [])
                and (contract.get('validation_result') or {}).get('valid') is True):
            return proposal_service.envelope(row)
    return proposal_service.create(
        'WIZARD_NETWORK_TOPOLOGY',
        [*physical_changes, {'object_type': 'NetworkTopology', 'data': {'name': 'Wizard-Netzwerktopologie', 'topology': topology,
                                                  'resource_decision': resource_receipt}}],
        f'Physische Netzwerktopologie aus {len(routes)} freigegebenen Routen: '
        f'{len(topology["nodes"])} Geräte und {len(topology["edges"])} deduplizierte Segmente; '
        f'{fallback_count} Teilnehmer wurden ohne künstliche logische Route physisch ergänzt. '
        'Der Workflow-Stand bleibt bis zur menschlichen Freigabe unverändert. '
        + (decision_summary(resource_receipt) if policy['mode'] == 'AUTO_SIZE' else 'Der feste Ressourcenbestand bleibt verbindlich.'),
        assumptions=['Busse folgen den validierten Endpunktprotokollen; gemeinsame physische Segmente bündeln ihre logischen Routen.',
                     'Unabhängige Netze benötigen eigene Hardwarekanäle. Die aufgeführten Kanalergänzungen werden gemeinsam mit der Topologie freigegeben.'],
        evidence=[{'source': 'approved-routing-table', 'prompt_sha256': fingerprint,
                   'route_count': len(routes), 'node_count': len(topology['nodes']), 'edge_count': len(topology['edges']),
                   'physical_completion_edges': fallback_count}],
    )


def plan_capacity_remediation(arguments: dict) -> dict:
    """Decide resource sizing from measured load and explicit hard limits."""
    prompt = effective_wizard_prompt(arguments['prompt'])
    workflow = WorkflowStatusService(current_project_id())
    state = workflow.get()
    capacity = CapacityTimingService(current_project_id()).latest()
    if not capacity or capacity.get('is_outdated'):
        capacity = CapacityTimingService(current_project_id()).calculate(persist=False)
    return plan_network_distribution(
        capacity,
        model.objects('HardwareNode'),
        state.get('topology') or {},
        parameters=state.get('parameters') or {},
        allowed_protocols=((state.get('context') or {}).get('engineering_scope_rules') or {}).get('communication_systems'),
        available_protocol_counts=planning_inventory(state, prompt),
        resource_policy=planning_policy(state),
        physical_interfaces=model.objects('HardwareNetworkInterface'),
    )


def generate_capacity_network_repair(arguments: dict) -> dict:
    """Turn safe same-technology branch splits into a governed topology proposal."""
    prompt = effective_wizard_prompt(arguments['prompt'])
    state = WorkflowStatusService(current_project_id()).get()
    plan = plan_capacity_remediation(arguments)
    decisions = [item for item in plan.get('networks') or [] if item.get('decision') == 'SPLIT_CURRENT_TECHNOLOGY']
    if not decisions:
        raise ValueError(
            'Kein sicher materialisierbarer Segment-Split vorhanden. '
            'Ein Technologiewechsel benötigt eine explizite Interface- und Gateway-Freigabe.'
        )
    topology, changed_edges = split_topology_by_distribution(state.get('topology') or {}, plan)
    if changed_edges <= 0:
        raise ValueError('Der Capacity-Plan konnte keiner physischen Route des überlasteten Zweigs zugeordnet werden.')
    topology, physical_changes = materialize_physical_ports(topology, model.objects('HardwareNode'),
        model.objects('HardwareNetworkInterface'), model.networks(), routes=model.routes(), messages=model.objects('Message'))
    policy = planning_policy(state)
    resource_receipt = resource_decision(state.get('topology') or {}, topology,
        planning_inventory(state, prompt), policy)
    signature = hashlib.sha256(json.dumps({
        'prompt': prompt,
        'topology': state.get('topology') or {},
        'decisions': decisions,
        'resource_decision': resource_receipt,
        'physical_changes': physical_changes,
    }, sort_keys=True).encode('utf-8')).hexdigest()
    for row in proposal_store.list_proposals(limit=100):
        contract = row.get('engineering_contract') or {}
        if (row['proposal_type'] == 'CAPACITY_NETWORK_REPAIR'
                and any(item.get('capacity_repair_sha256') == signature for item in row.get('evidence') or [])
                and (contract.get('validation_result') or {}).get('valid') is True):
            return proposal_service.envelope(row)
    branch_text = '; '.join(
        f"{item['network_id']}: {item['current_load_percent']:.2f}% auf "
        f"{item['proposed_segments']} {item['protocol']}-Segmente, Prognose "
        f"{item['projected_max_load_percent']:.2f}%"
        for item in decisions
    )
    reserve_text = ' '.join(warning['message'] for item in decisions for warning in item.get('warnings') or [])
    return proposal_service.create(
        'CAPACITY_NETWORK_REPAIR',
        [*physical_changes, {'object_type': 'NetworkTopology', 'data': {
            'name': 'Capacity-optimierte Netzwerktopologie', 'topology': topology,
            'resource_decision': resource_receipt,
        }}],
        f'Gezielte Reparatur der überlasteten physischen Zweige: {branch_text}. '
        f'{changed_edges} routenbelegte physische Kanten werden neu segmentiert; '
        'unbetroffene Zweige bleiben unverändert. Der Projektstand ändert sich erst nach menschlicher Freigabe. '
        + (reserve_text + ' Die Übernahme bestätigt den physischen Plan einschließlich dieser offenen Reserven, keine Funktionsfreigabe. ' if reserve_text else '')
        + (decision_summary(resource_receipt) if policy['mode'] == 'AUTO_SIZE' else 'Der feste Ressourcenbestand bleibt verbindlich.'),
        assumptions=[
            ('Die eingegebenen Netzanzahlen sind Ausgangswerte; das Tool dimensioniert zusätzliche Segmente anhand der Ziel-Buslast. Explizite hard_limits bleiben verbindlich.'
             if policy['mode'] == 'AUTO_SIZE' else 'Die bestätigte Anzahl freier Bussegmente ist die verbindliche Ressourcenobergrenze.'),
            'Ein Technologiewechsel wird nicht stillschweigend materialisiert; Interfaces und Gateways benötigen separate Freigabe.',
        ],
        evidence=[{
            'source': 'capacity-branch-remediation',
            'capacity_repair_sha256': signature,
            'target_load_percent': plan.get('target_load_percent'),
            'protocol_inventory': plan.get('protocol_inventory') or {},
            'branches': decisions,
            'changed_edges': changed_edges,
            'resource_decision': resource_receipt,
            'decision_rationale': plan.get('decision_rationale'),
        }],
        confidence=0.95,
    )
