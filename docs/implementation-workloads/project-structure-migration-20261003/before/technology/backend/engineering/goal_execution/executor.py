"""Atomic, revision-checked execution with a durable journal outside the savepoint."""
from copy import deepcopy
from datetime import datetime, timezone
from .models import DesiredEngineeringState, GoalCompletionEvaluator
from .graph import ModelGraphService, digest
from .store import get_goal, save_goal
from . import commands
from ..db import get_connection, flush_model_changes, _request_unit
from ..project_context import current_project_id
from ..agent_tools.model import json_safe


def journal(goal, kind, **details):
    goal.setdefault('journal', []).append({'time': datetime.now(timezone.utc).isoformat(), 'kind': kind, **json_safe(details)})


def execute(workload_id):
    if _request_unit.get() is None:
        raise RuntimeError('Ausführungsaufträge benötigen eine gesperrte Projekttransaktion.')
    goal = get_goal(workload_id)
    if goal['status'] == 'COMPLETE': return goal
    auth = goal.get('authorization')
    if not auth: raise PermissionError('Dieser Auftrag besitzt keine serverseitig gespeicherte Ausführungsfreigabe.')
    strategy = next((s for s in goal['strategies'] if s['id'] == auth['approved_strategy']), None)
    if not strategy or digest(strategy['plan']) != auth['plan_hash'] or auth['approved_goal'] != goal['goal']:
        raise PermissionError('Plan und Freigabe stimmen nicht überein.')
    graph = ModelGraphService.load()
    if graph.revision != auth['model_revision']:
        goal.update(status='PLAN_STALE', authorization=None)
        for item in goal.get('port_decisions', []): item['status'] = 'OUTDATED'
        journal(goal, 'PLAN_STALE', expected=auth['model_revision'], actual=graph.revision)
        return save_goal(goal)
    if goal.get('attempts', 0) >= 3:
        goal.update(status='BLOCKED', findings=[{'code': 'REPAIR_LIMIT', 'message': 'Drei Ausführungsversuche fehlgeschlagen. Ursache gezielt prüfen.'}])
        return save_goal(goal)
    goal['attempts'] = goal.get('attempts', 0) + 1
    goal['status'] = 'RUNNING'
    goal['plan'] = deepcopy(strategy['plan'])
    actor = f'goal:{auth["authorized_by"]}:{workload_id}'
    current_step = None
    def phase(key, operation):
        nonlocal current_step
        current_step = next(s for s in goal['plan']['steps'] if s['step_id'] == key)
        current_step['status'] = 'RUNNING'
        journal(goal, 'STEP_STARTED', step_id=key, tool=current_step['tool'])
        from .progress import publish
        publish(goal)
        value = operation()
        current_step['status'] = 'SUCCEEDED'
        journal(goal, 'STEP_SUCCEEDED', step_id=key)
        return value
    unit = _request_unit.get()
    previous_dirty = unit.model_changed if unit else False
    try:
        with get_connection():
            phase('revision', lambda: graph.revision == auth['model_revision'])
            source = graph.hni[strategy['source_port']]
            phase('capability', lambda: commands.checked_port(graph, source, role='source'))
            phase('controller', lambda: commands.inspect_port_decision(graph, goal['host_refs'][1], strategy['technology'], strategy['network_ref']))
            target = phase('interface', lambda: commands.ensure_destination(graph, goal, strategy, actor))
            updated = ModelGraphService.load()
            phase('port', lambda: commands.checked_port(updated, target, role='target'))
            phase('port_binding', lambda: [commands.persist_port_resources(updated, port, actor, workload_id) for port in (source, target)])
            phase('network', lambda: commands.checked_port(updated, target))
            phase('topology', lambda: None if strategy.get('path') else commands.ensure_topology(updated, source, target, actor))
            updated = ModelGraphService.load()
            phase('functions', lambda: [updated.host(ref) for ref in goal['desired_state']['target_objects']])
            receiver = phase('functional_interfaces', lambda: commands.ensure_receiver_interface(updated, goal, target, actor))
            phase('payload', lambda: commands.bind_messages(updated, goal, source, actor))
            updated = ModelGraphService.load()
            phase('transport', lambda: validate_transport(updated, goal, source))
            phase('packing', lambda: validate_transport(updated, goal, source))
            phase('identifier', lambda: validate_identifiers(updated, goal, source))
            goal['route_ids'] = phase('routing', lambda: commands.ensure_routes(updated, goal, strategy, source, target, receiver, actor))
            phase('supersede', lambda: None)  # Versioned updates retain their original functional intent.
            phase('invalidate', lambda: invalidate_and_refresh(goal, actor))
            from ..capacity.service import CapacityTimingService, PreflightService
            goal['capacity'] = phase('capacity', lambda: CapacityTimingService(current_project_id()).calculate())
            phase('timing', lambda: validate_capacity(goal, source))
            updated = ModelGraphService.load()
            phase('addresses', lambda: validate_addresses(updated, goal))
            phase('validation', lambda: validate_final(updated, goal, source, target))
            goal['preflight'] = phase('preflight', lambda: PreflightService(current_project_id()).run())
            goal['completion'] = phase('completion', lambda: complete_and_repair(updated, goal, source, target, actor))
            goal['status'] = goal['completion']['status']
            goal['result_revision'] = updated.revision
            goal['authorization'] = None  # Consumed; resume must re-inspect, never replay mutations.
            applied_decision = (strategy.get('port_decision') or {}).get('decision_id')
            for item in goal.get('port_decisions', []):
                item['status'] = 'APPLIED' if item['decision_id'] == applied_decision else 'SUPERSEDED'
            if goal['status'] == 'COMPLETE' and goal.get('followup_goals') and auth['authorized_by'] != 'technical-preview':
                goal['connection_completion'] = deepcopy(goal['completion'])
                goal['followup_authorization'] = {'goal': goal['goal'], 'model_revision': updated.revision,
                    'goal_types': goal['plan']['followup_goals'], 'authorized_by': auth['authorized_by']}
                goal['completion'] = {**goal['completion'], 'status': 'INCOMPLETE', 'missing_conditions': ['simulation_complete', 'communication_observed']}
                goal['status'] = 'FOLLOWUP_PENDING'
            journal(goal, 'EXECUTION_FINISHED', status=goal['status'], route_ids=goal['route_ids'], completion=goal['completion'])
    except Exception as error:
        if unit: unit.model_changed = previous_dirty
        if current_step: current_step['status'] = 'FAILED'
        for step in goal['plan']['steps']:
            if step['status'] == 'SUCCEEDED': step['status'] = 'ROLLED_BACK'
        goal['findings'] = getattr(error, 'findings', [{'severity': 'ERROR', 'code': 'EXECUTION_FAILED', 'message': str(error)}])
        goal['status'] = 'BLOCKED' if isinstance(error, commands.ExecutionBlocked) else 'FAILED'
        goal['completion'] = GoalCompletionEvaluator().evaluate(DesiredEngineeringState.model_validate(goal['desired_state']), {}, blockers=goal['findings'], failed=goal['status'] == 'FAILED')
        goal.pop('route_ids', None)
        journal(goal, 'CANONICAL_BATCH_ROLLED_BACK', findings=goal['findings'])
    from .outputs import ensure_outputs
    saved = save_goal(goal)
    return ensure_outputs(saved) if auth['authorized_by'] != 'technical-preview' else saved


def invalidate_and_refresh(goal, actor):
    from ..workflow.service import WorkflowStatusService
    flush_model_changes(actor=actor, reason=goal['goal'])
    workflow = WorkflowStatusService(current_project_id())
    for step in ('engineering_model', 'routing', 'network_editor', 'parameters'):
        workflow.refresh_source_status(step, actor=actor, reason='Ausführungsplan: kanonische Artefakte erneut geprüft')


def complete_and_repair(graph, goal, source, target, actor):
    """Repair derived artifacts only. Architecture and missing requirements are decisions."""
    from ..capacity.service import CapacityTimingService, PreflightService
    result = completion(graph, goal, source, target)
    repairable = {'WORKFLOW_STEP_NOT_READY', 'CAPACITY_SOURCE_NOT_READY', 'CAPACITY_MISSING_OR_OUTDATED'}
    seen = set()
    for attempt in range(2):
        errors = [f for f in goal['preflight'].get('findings', []) if f.get('severity') == 'ERROR']
        fingerprint = digest(errors)
        if result['status'] == 'COMPLETE' or not errors or any(f.get('code') not in repairable for f in errors) or fingerprint in seen:
            break
        seen.add(fingerprint)
        journal(goal, 'DERIVED_REPAIR_STARTED', attempt=attempt + 1, findings=errors)
        invalidate_and_refresh(goal, actor)
        goal['capacity'] = CapacityTimingService(current_project_id()).calculate()
        validate_capacity(goal, source)
        goal['preflight'] = PreflightService(current_project_id()).run()
        graph = ModelGraphService.load()
        result = completion(graph, goal, source, target)
        journal(goal, 'DERIVED_REPAIR_EVALUATED', attempt=attempt + 1, completion=result)
    return result


def validate_transport(graph, goal, source):
    from ..message_packing import valid_payload_bytes
    from ..signal_audit import inspect_message_signals
    from ..capacity.transmission import profile
    from ..capacity.dimensioning import transmission_contract
    for mid in goal['message_ids']:
        message = graph.messages[mid]
        signals = [s for s in graph.signals.values() if str(s.get('message_id')) == mid]
        reports = inspect_message_signals(signals, message)
        errors = [c for r in reports for c in r['checks'] if c['severity'] in {'ERROR', 'OPEN'}]
        dlc = message.get('dlc')
        if not signals or type(dlc) is not int or valid_payload_bytes(source['technology'], dlc) != dlc or errors:
            raise commands.ExecutionBlocked('TRANSPORT_INVALID', 'Signalbelegung oder Nutzlast ist nicht vollständig gültig.', errors)
        release = profile(transmission_contract(message), message.get('cycle_ms'))
        if release['errors']:
            raise commands.ExecutionBlocked('TRAFFIC_RELEASE_INVALID', 'Der explizite Sendevertrag ist unvollständig.', release)


def validate_identifiers(graph, goal, source):
    from ..physical_ports import technology_id
    from ..message_bindings import message_hardware_interface_ids
    if technology_id(source['technology']) not in {'can', 'can_fd', 'can_xl'}: return
    networks = {source['network_ref']}
    for mid in goal['message_ids']:
        networks.update(graph.hni[p]['network_ref'] for p in message_hardware_interface_ids(graph.messages[mid])
            if p in graph.hni and graph.hni[p].get('network_ref'))
    seen = {}
    for message in graph.messages.values():
        ports = message_hardware_interface_ids(message)
        memberships = {graph.hni.get(p, {}).get('network_ref') for p in ports} & networks
        if not memberships: continue
        raw = message.get('message_id_hex')
        try: number = int(str(raw), 16)
        except (TypeError, ValueError):
            if str(message['id']) in goal['message_ids']: raise commands.ExecutionBlocked('FRAME_IDENTIFIER_MISSING', 'Die Nachricht benötigt eine explizite CAN-Kennung.')
            continue
        extended = bool((message.get('configuration') or {}).get('extended_id'))
        if not 0 <= number <= (0x1FFFFFFF if extended else 0x7FF):
            raise commands.ExecutionBlocked('FRAME_IDENTIFIER_INVALID', 'Die CAN-Kennung liegt außerhalb des Identifierraums.')
        for network in memberships:
            key = (network, number, extended)
            if key in seen and seen[key] != str(message['id']):
                raise commands.ExecutionBlocked('FRAME_IDENTIFIER_COLLISION', 'Die vorhandene CAN-Kennung kollidiert auf einem beteiligten Netz. Bestehende Kennungen werden nicht still geändert.')
            seen[key] = str(message['id'])


def validate_capacity(goal, source):
    results = goal['capacity']['results']
    routes = [r for r in results['routes'] if r['route_id'] in goal['route_ids']]
    affected_networks = {source['network_ref'], *(r.get('network_id') for r in routes)}
    networks = [n for n in results['networks'] if n['network_id'] in affected_networks]
    if not networks or not routes:
        raise commands.ExecutionBlocked('CAPACITY_EVIDENCE_MISSING', 'Die berechneten Ergebnisse enthalten den neuen Transport nicht.')
    if any(n.get('status') in {'FAIL', 'OVERLOAD', 'CRITICAL'} or n.get('burst_load_percent', 0) > n.get('target_bus_load_percent', results['overview']['target_bus_load_percent']) for n in networks):
        raise commands.ExecutionBlocked('NETWORK_CAPACITY_EXCEEDED', 'Die gewählte Verbindung überschreitet die freigegebene Netzkapazität.', networks)
    if any(n.get('communication_schedule', {}).get('status') in {'MODEL_INCONSISTENT', 'INFEASIBLE', 'INVALID'} for n in networks):
        raise commands.ExecutionBlocked('COMMUNICATION_SCHEDULE_INVALID', 'Für den gewählten Weg existiert kein konsistenter Sendeplan.', networks)
    if any(r.get('latency_status') == 'FAIL' or r.get('jitter_status') == 'FAIL' for r in routes):
        raise commands.ExecutionBlocked('TIMING_REQUIREMENT_VIOLATED', 'Der gewählte Pfad verletzt eine Zeitvorgabe.', routes)


def validate_addresses(graph, goal):
    from ..addressing import LogicalNodeAddressAllocator
    for ref in goal['host_refs']:
        hardware = graph.hardware[ref]
        if hardware.get('diagnostic_addressable') is not False and (hardware.get('logical_node_address') is None or hardware.get('address_status') != 'ASSIGNED'):
            raise commands.ExecutionBlocked('LOGICAL_ADDRESS_UNRESOLVED', 'Eine beteiligte Hardware besitzt keine gültige logische Adresse.')
        if hardware.get('logical_node_address') is not None and any(str(h['id']) != ref and h.get('logical_node_address') == hardware['logical_node_address'] and h.get('address_namespace') == hardware.get('address_namespace') for h in graph.hardware.values()):
            raise commands.ExecutionBlocked('LOGICAL_ADDRESS_COLLISION', 'Die logische Knotenadresse ist im Namensraum mehrfach vergeben.')
        if hardware.get('logical_node_address') is not None:
            address = LogicalNodeAddressAllocator(namespace=hardware.get('address_namespace') or 'PROJECT').validate_address(hardware['logical_node_address'], node_id=ref)
            if not address['valid']:
                raise commands.ExecutionBlocked('LOGICAL_ADDRESS_INVALID', 'Die logische Knotenadresse verletzt die bestätigte Adresspolicy.', address)


def validate_final(graph, goal, source, target):
    from ..routing.validation import RoutingValidator
    from ..routing.repository import get_route
    findings = commands.topology_port_findings(graph.model['topology'], list(graph.hardware.values()), list(graph.hni.values()))
    if findings: raise commands.ExecutionBlocked('TOPOLOGY_INVALID', 'Die gespeicherten physischen Verknüpfungen sind ungültig.', findings)
    for rid in goal['route_ids']:
        checked = RoutingValidator().validate(json_safe(get_route(rid)), exclude_route_id=rid)
        if not checked['valid']: raise commands.ExecutionBlocked('ROUTING_INVALID', 'Abschließende Routing-Prüfung fehlgeschlagen.', checked)
    commands.checked_port(graph, source); commands.checked_port(graph, target)


def completion(graph, goal, source, target):
    from ..routing.repository import get_route
    from ..workflow.service import WorkflowStatusService
    # Evidence follows successful canonical validators, never a navigation action.
    evidence = {key: False for key in goal['desired_state']['completion_criteria']}
    validated = {s['step_id'] for s in goal['plan']['steps'] if s['status'] == 'SUCCEEDED'}
    checks = {'source_resolved': 'functions', 'target_resolved': 'functions', 'hosts_resolved': 'functions',
        'payload_identified': 'payload', 'functional_relationship': 'routing', 'capability_valid': 'capability',
        'controller_valid': 'controller', 'channel_valid': 'port', 'interface_valid': 'functional_interfaces',
        'port_valid': 'port_binding', 'network_membership_valid': 'network', 'technology_binding_valid': 'transport',
        'transport_valid': 'packing', 'identifiers_valid': 'identifier', 'address_valid': 'addresses', 'routing_valid': 'validation',
        'capacity_valid': 'capacity', 'projections_current': 'validation', 'stale_results_invalidated': 'invalidate'}
    evidence.update({key: stage in validated for key, stage in checks.items()})
    routes = [json_safe(get_route(rid)) for rid in goal['route_ids']]
    functional = [m for n in goal['capacity']['results']['networks']
        for m in n.get('evaluation', {}).get('functional', {}).get('messages', []) if str(m.get('message_id')) in goal['message_ids']]
    metrics = [r for r in goal['capacity']['results']['routes'] if r['route_id'] in goal['route_ids']]
    evidence['timing_valid'] = (set(goal['message_ids']) <= {str(m['message_id']) for m in functional}
        and all(m['status'] == 'PASS' for m in functional) and bool(metrics) and all(r.get('timing_verified') is True for r in metrics))
    evidence['preflight_valid'] = goal['preflight'].get('ready_for_simulation') is True
    workflow = WorkflowStatusService(current_project_id())
    evidence['projections_current'] = evidence['projections_current'] and workflow.latest_analysis('capacity_timing') is not None
    result = GoalCompletionEvaluator().evaluate(DesiredEngineeringState.model_validate(goal['desired_state']), evidence)
    if result['status'] == 'INCOMPLETE' and set(result['missing_conditions']) <= {'timing_valid', 'preflight_valid'}:
        result['status'] = 'READY_FOR_REVIEW'
    return {**result, 'evidence': evidence, 'model_revision': graph.revision,
        'note': 'Kapazitätsnachweis und funktionale Timing-Freigabe werden getrennt bewertet.'}
