"""Real MCP regression for combined wizard creation, without local LLM calls."""
import asyncio
import json
from collections import Counter
from uuid import uuid4

from backend.agent_core.api.mcp_client import EngineeringMCPClient
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.core.engineering_agent import EngineeringAgent
from backend.engineering.agent_tools.runtime import ToolAuthority
from backend.engineering.agent_tools.runtime import execute
from backend.agent_core.api.tool_contract import Permission
from backend.engineering.agent_tools import wizard_generation, model, proposal_service
from backend.simulator_engineering_mcp.server import create_server
from backend.engineering.workflow.service import WorkflowStatusService
from backend.engineering.repository import create_object, update_object, get_object
from backend.engineering.agent_tools import conversation
from backend.engineering.agent_tools.run_status import reconcile_model_apply
from backend.engineering.agent_tools import run_status
import pytest


def test_canopen_retains_application_capability_over_physical_can():
    from backend.engineering.models import INTERFACE_TYPES, validate_choice
    from backend.engineering.agent_tools.validation import _network_supports_interface
    from backend.engineering.routing.generation import INTERFACE_TO_PROTOCOL
    from backend.engineering.routing.validation import INTERFACE_PROTOCOLS, physical_route_technology
    from backend.engineering.physical_ports import technology_id
    assert validate_choice('CANopen', INTERFACE_TYPES, 'technology') == 'CANopen'
    contract = wizard_generation._technology_contract('CANopen')
    assert contract['technology_id'] == 'canopen'
    assert contract['capabilities']['supports_request_response'] is True
    assert wizard_generation._network_protocol('CANopen') == 'CAN'
    assert wizard_generation._topology_bus('CANopen') == 'can'
    assert _network_supports_interface('CAN', 'CANopen')
    assert not _network_supports_interface('LIN', 'CANopen')
    assert INTERFACE_TO_PROTOCOL['CANopen'] == 'CAN'
    assert INTERFACE_PROTOCOLS['CANopen'] == {'CAN'}
    assert technology_id('CANopen') == technology_id('CAN')
    assert physical_route_technology('CANopen') == physical_route_technology('CAN') == 'CAN'


def test_explicit_s04_rates_preserve_each_technology_and_reject_invalid_values():
    prompt = 'LIN:\n19,2 kbit/s\nSensoren 500 ms\nEthernet:\n100 Mbit/s\n'
    assert wizard_generation._explicit_technology_bitrates(prompt, ['lin', 'ethernet']) == {
        'lin': 19_200, 'ethernet': 100_000_000,
    }
    with pytest.raises(ValueError, match='TechnologyProfile'):
        wizard_generation._explicit_technology_bitrates('LIN:\n2 Mbit/s', ['lin'])


def test_explicit_can_fd_phases_and_i2c_candidate_stay_distinct_from_evidence():
    prompt = 'CAN-FD: 500 kbit/s arbitration, 2 Mbit/s data\nEthernet: 100 Mbit/s'
    assert wizard_generation._explicit_can_fd_phases(prompt, ['can_fd']) == {
        'arbitration_bitrate': 500_000, 'data_bitrate': 2_000_000,
    }
    assert wizard_generation._explicit_technology_bitrates(prompt, ['can_fd', 'ethernet']) == {
        'ethernet': 100_000_000,
    }
    with pytest.raises(ValueError, match='TechnologyProfile'):
        wizard_generation._explicit_can_fd_phases('CAN-FD: 2 Mbit/s arbitration, 2 Mbit/s data', ['can_fd'])
    candidate, proposal = wizard_generation._rate_review_candidate('i2c')
    assert candidate == 100_000
    assert proposal['status'] == 'REVIEW_REQUIRED'


def test_gateway_free_v0_identifies_only_the_controller_as_main_controller():
    controller = {'device_type': 'EmbeddedController'}
    sensor = {'device_type': 'SensorController'}
    specification = {
        'networkArchitecture': 'sensor_ecu_actuator',
        'chains': [controller, sensor],
    }

    assert wizard_generation._is_local_main_controller(controller, specification)
    assert not wizard_generation._is_local_main_controller(sensor, specification)

    specification['chains'].append({'device_type': 'Gateway'})
    assert not wizard_generation._is_local_main_controller(controller, specification)

    specification['chains'].pop()
    specification['networkArchitecture'] = 'gateway_direct'
    assert not wizard_generation._is_local_main_controller(controller, specification)


def test_gateway_function_is_not_an_alternative_host_for_declared_domain_functions():
    specification = {
        'chains': [
            {'hardware_name': 'Embedded', 'device_type': 'EmbeddedController'},
            {'hardware_name': 'Ethernet', 'device_type': 'Gateway'},
            {'hardware_name': 'Positionssensor1', 'device_type': 'SensorController'},
        ],
    }
    function_refs = {
        'embedded': '$controller-function',
        'ethernet': '$gateway-function',
        'positionssensor1': None,
    }

    assert wizard_generation._declared_function_hosts(specification, function_refs) == ['embedded']


def test_explicit_function_assignments_preserve_each_confirmed_controller():
    prompt = '- Funktionszuordnungen: {"EnvironmentPerception":"Edge Computer","MotionControl":"Robot"}'
    assert wizard_generation._declared_function_assignments(prompt) == {
        'environmentperception': 'edge computer',
        'motioncontrol': 'robot',
    }
    with pytest.raises(ValueError, match='Ungültige Funktionszuordnungen'):
        wizard_generation._declared_function_assignments('- Funktionszuordnungen: {"MotionControl":42}')


def test_wizard_direct_gpio_signal_has_binding_without_message_or_bus(monkeypatch):
    def chain(name, device_type, technology):
        return {
            'hardware_name': name, 'hardware_description': name,
            'device_type': device_type, 'device_class': 4 if device_type == 'ECU' else 0,
            'function_name': name + 'Function', 'function_description': name,
            'interface_name': name + '_' + technology, 'interface_type': technology,
            'transport_network_ref': None, 'message_name': name + 'Data',
            'message_id_hex': None, 'direction': 'tx', 'cycle_ms': 20, 'dlc': 1,
            'signal_name': name + 'Value', 'start_bit': 0, 'length_bits': 1,
            'byte_order': 'little_endian', 'data_type': 'unsigned',
            'factor': 1, 'offset_value': 0,
        }
    spec = {
        'domain': 'Custom', 'modelType': 'custom',
        'targetCounts': {'gateways': 0, 'ecus': 1, 'sensors': 1, 'actuators': 0},
        'communicationSystemCounts': {'ethernet': 1, 'gpio': 1},
        'chains': [chain('RaspberryPi', 'ECU', 'Ethernet'),
                   chain('PT100', 'SensorController', 'GPIO')],
    }
    graph = [{'network_id': 'detected:ethernet', 'bus_name': 'Controller',
              'controllers': [{'ecu': 'RaspberryPi', 'sensors': ['PT100'], 'actuators': []}]}]
    prompt = '- Systemcluster-Graph: ' + json.dumps(graph, separators=(',', ':'))
    captured = {}
    monkeypatch.setattr(wizard_generation.proposal_store, 'list_proposals', lambda limit: [])
    monkeypatch.setattr(wizard_generation.model, 'objects', lambda _kind: [])
    monkeypatch.setattr(wizard_generation, 'extract_specification', lambda _prompt: spec)
    monkeypatch.setattr(wizard_generation.proposal_service, 'create',
                        lambda proposal_type, changes, summary, **metadata:
                        captured.update(changes=changes) or captured)
    changes = wizard_generation.generate({'prompt': prompt})['changes']
    direct = next(item for item in changes if item['object_type'] == 'Signal'
                  and item['data']['name'] == 'PT100Value')
    binding = direct['data']['configuration']['direct_signal_binding']
    assert 'message_id' not in direct['data']
    assert binding['signal_type'] == 'GPIO'
    assert binding['destination_hardware_node_ref']
    assert all(item['data'].get('name') != 'PT100Data' for item in changes if item['object_type'] == 'Message')
    assert not any(item['object_type'] == 'Network' and item['data']['technology'] == 'GPIO' for item in changes)


def test_canonical_direct_signal_persists_without_transport_unit():
    authority = ToolAuthority(f'pytest-direct-binding-{uuid4()}')

    def operation():
        source = create_object('HardwareNode', {'name': 'PassiveSwitch', 'device_type': 'SensorController', 'device_class': 0})
        target = create_object('HardwareNode', {'name': 'Controller', 'device_type': 'ECU', 'device_class': 4})
        port = create_object('HardwareNetworkInterface', {
            'name': 'SwitchInput', 'hardware_node_id': str(source['id']), 'technology': 'GPIO'})
        binding = {'source_hardware_node_ref': str(source['id']),
                   'destination_hardware_node_ref': str(target['id']),
                   'physical_port_ref': str(port['id']), 'signal_type': 'GPIO',
                   'validation_status': 'REVIEW_REQUIRED'}
        signal = create_object('Signal', {'name': 'SwitchState',
            'configuration': {'direct_signal_binding': binding}})
        assert signal['message_id'] is None
        assert signal['configuration']['direct_signal_binding'] == binding
        interface = create_object('Interface', {'name': 'SwitchLogic',
            'hardware_node_id': str(source['id']), 'interface_type': 'GPIO'})
        with pytest.raises(Exception, match='DIRECT_IO_MESSAGE_CREATED'):
            create_object('Message', {'name': 'InvalidSwitchFrame', 'interface_id': str(interface['id'])})
        return {'ok': True}

    result = execute(authority, 'test_direct_binding', Permission.READ_MODEL, {}, lambda _: operation())
    assert result.success, result.findings


def test_repeat_reuses_named_hardware_port_when_only_network_reference_changed():
    authority = ToolAuthority(f'pytest-repeat-port-reuse-{uuid4()}')
    original = '''- Industrie: Custom
- Netzwerktechnologien: I2C (i2c)
- Hardware-Sollwerte: {"gateways":0,"ecus":1,"sensors":1,"actuators":0}
- Geräteanschlüsse: {"RaspberryPi":"I2C","Druck":"I2C"}
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
Ein RaspberryPi liest einen Drucksensor.
'''

    def apply_then_repeat():
        proposal = wizard_generation.generate({'prompt': original})
        validated = proposal_service.validate(proposal['proposal_id'])
        assert validated['status'] == 'VALIDATED', validated['validation_result']
        approved = proposal_service.review(proposal['proposal_id'], revision=validated['revision'],
            decision='approve', actor='test-human', trace_id=str(uuid4()))
        proposal_service.apply(approved['proposal_id'], actor='test-human', trace_id=str(uuid4()))
        repeated = wizard_generation.generate({'prompt': original.replace(
            '- Geräteanschlüsse: {"RaspberryPi":"I2C","Druck":"I2C"}',
            '- Geräteanschlüsse: {"Druck":"I2C"}')})
        return repeated

    result = execute(authority, 'test_repeat_port_reuse', Permission.GENERATE_PROPOSAL, {},
                     lambda _: apply_then_repeat())
    assert result.success, result.findings
    duplicate_ports = [change for change in result.data.get('changes') or []
                       if change['object_type'] == 'HardwareNetworkInterface'
                       and change.get('action', 'CREATE') == 'CREATE']
    assert not duplicate_ports, duplicate_ports


def test_generated_can_identifier_skips_persisted_and_pending_identifiers():
    existing = [{'message_id_hex': '0x100'}]
    pending = [
        {'object_type': 'Message', 'data': {'message_id_hex': '0x101'}},
        {'object_type': 'Signal', 'data': {'message_id_hex': '0x102'}},
    ]

    assert wizard_generation._next_generated_can_identifier(existing, pending) == '0x102'


def define_fixture_command_signals():
    """Explicit test specification; production must never invent command bits."""
    for message in model.objects('Message'):
        if (((message.get('configuration') or {}).get('transport_unit') or {}).get('provenance') or {}).get('generator') == 'wizard-local-actuator-command' and not any(str(s.get('message_id')) == str(message['id']) for s in model.objects('Signal')):
            create_object('Signal', {'name': 'FixtureCommand_' + str(message['id']),
                'message_id': str(message['id']), 'start_bit': 0, 'length_bits': 1,
                'byte_order': 'little_endian', 'data_type': 'unsigned', 'factor': 1,
                'offset_value': 0, 'min_value': 0, 'max_value': 1})


def test_capacity_repair_apply_releases_review_gate(monkeypatch):
    execution = {
        'run_id': 'capacity-repair-run-12345678',
        'state': 'REVIEW_REQUIRED',
        'step': 'capacity_timing',
    }
    summary = {
        'active_step': 'network_editor',
        'statuses': {
            'network_editor': 'COMPLETE',
            'parameters': 'APPROVED',
            'capacity_timing': 'OUTDATED',
        },
        'artifact_checks': {'network_editor': {'complete': True}},
        'context': {'agent_execution': execution},
    }
    updates = []

    class FakeWorkflowStatusService:
        def __init__(self, project_id):
            assert project_id == 'capacity-repair-project'

        def get(self, summary=False):
            assert summary is True
            return summary_data

        def set_context(self, context, summary=False):
            assert summary is True
            updates.append(context)

    summary_data = summary
    monkeypatch.setattr(run_status, 'WorkflowStatusService', FakeWorkflowStatusService)
    monkeypatch.setattr(conversation, 'read', lambda: {
        'active_proposal': 'capacity-repair-proposal',
        'current_requirement': 'Lauf-ID: capacity-repair-run-12345678',
    })

    reconcile_model_apply('capacity-repair-project', {
        'proposal_id': 'capacity-repair-proposal',
        'proposal_type': 'CAPACITY_NETWORK_REPAIR',
        'status': 'APPLIED',
    })

    reconciled = updates[0]['agent_execution']
    assert reconciled['state'] == 'READY_TO_CONTINUE'
    assert reconciled['step'] == 'capacity_timing'
    assert 'Capacity-Reparatur übernommen' in reconciled['message']


def test_confirmed_names_generate_reviewable_model_and_complete_routing():
    authority = ToolAuthority(f'pytest-confirmed-identities-{uuid4()}')
    prompt = '''- Industrie: Automotive
- Netzwerktechnologien: CAN-FD (can_fd)
- Hardware-Sollwerte: {"gateways":1,"ecus":1,"sensors":1,"actuators":1}
- Aktor-Befehle: {"MotorValve":{"length_bits":1,"data_type":"boolean","factor":1,"unit":"code","min_value":0,"max_value":1,"semantic":{"semantic_type":"BOOLEAN"},"data":{"enum_values":{"CLOSE":0,"OPEN":1}}}}
- Systemcluster-Graph: [{"network_id":"can_fd","bus_name":"Drive","controllers":[{"ecu":"Motorsteuerung","sensors":["MotorTemperature"],"actuators":["MotorValve"]}]}]
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
Erzeuge ein Netzwerk mit einem Gateway, einer Motorsteuerung, einem Temperatursensor und einem Stellglied.
'''
    def generate_and_apply():
        proposal = wizard_generation.generate({'prompt': prompt})
        proposal = proposal_service.validate(proposal['proposal_id'])
        assert proposal['status'] == 'VALIDATED', proposal['validation_result']
        names = {c['data']['name'] for c in proposal['changes'] if c['object_type'] == 'HardwareNode'}
        assert {'Motorsteuerung', 'MotorTemperature', 'MotorValve'} <= names
        approved = proposal_service.review(proposal['proposal_id'], revision=proposal['revision'],
            decision='approve', actor='test-human', trace_id=str(uuid4()))
        proposal_service.apply(approved['proposal_id'], actor='test-human', trace_id=str(uuid4()))
        repeated = wizard_generation.generate({
            'prompt': prompt + '\n- Wiederholungsprüfung: gleiche bestätigte Architektur',
        })
        repeated_creates = [change for change in repeated.get('changes') or []
                            if change.get('action', 'CREATE') == 'CREATE']
        assert not repeated_creates, repeated_creates
        define_fixture_command_signals()
        routing = wizard_generation.generate_routing({'prompt': prompt})
        routing = proposal_service.validate(routing['proposal_id'])
        assert routing['status'] == 'VALIDATED', routing['validation_result']
        assert len(routing['changes']) == 3  # Local I/O; status without a recipient stays internal.
        approved_routing = proposal_service.review(routing['proposal_id'], revision=routing['revision'],
            decision='approve', actor='test-human', trace_id=str(uuid4()))
        proposal_service.apply(approved_routing['proposal_id'], actor='test-human', trace_id=str(uuid4()))
        assert wizard_generation.generate_routing({'prompt': prompt + '\nFortsetzung des bestätigten Wizard-Auftrags: Ziel: data_science_intelligence.'})['status'] == 'UNCHANGED'
        with pytest.raises(ValueError, match='Routing-Teilnehmer fehlen.*Unknown'):
            wizard_generation.generate_routing({'prompt': prompt.replace('MotorTemperature', 'Unknown')})
    result = execute(authority, 'test_confirmed_identity', Permission.GENERATE_PROPOSAL, {}, lambda _: generate_and_apply())
    assert result.success, result


@pytest.mark.parametrize('display_technology', ['can_fd', 'ethernet'])
@pytest.mark.parametrize('segmented', [False, True])
def test_confirmed_backbones_are_routable_before_topology_creation(display_technology, segmented):
    authority = ToolAuthority(f'pytest-backbone-ports-{uuid4()}')
    graph = [
        {'network_id': 'can_fd', 'bus_name': 'Drive', 'controllers': [
            {'ecu': 'Motorsteuerung', 'sensors': [], 'actuators': []}],
         'hmi_routes': [{'source': 'Motorsteuerung', 'target': 'Anzeige'}]},
        {'network_id': display_technology, 'bus_name': 'Display', 'controllers': [
            {'ecu': 'Anzeige', 'sensors': [], 'actuators': []}]},
    ]
    prompt = '\n'.join([
        '- Industrie: Automotive',
        '- Netzwerktechnologien: CAN-FD (can_fd); Ethernet (ethernet)',
        '- Hardware-Sollwerte: {"gateways":1,"ecus":2,"sensors":0,"actuators":0}',
        '- Systemcluster-Graph: ' + json.dumps(graph),
        'Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:',
        'Motorsteuerung und Anzeige mit einem zentralen Gateway verbinden.',
    ])
    if segmented:
        prompt += '\n- Netzarchitektur-ID: gateway_ecu_segments'

    def check():
        proposal = wizard_generation.generate({'prompt': prompt})
        for change in proposal['changes']:
            data = change.get('data') or {}
            if change['object_type'] == 'Network' and data.get('technology') == 'ETHERNET':
                assert data['name'].startswith('ETH_') and data['name_source'] == 'generated'
                channels = [item['data'] for item in proposal['changes'] if item['object_type'] == 'HardwareNetworkInterface'
                            and item['data'].get('network_ref') == data['id']]
                assert channels and all(channel['name'] == data['name'] for channel in channels)
        proposal = proposal_service.validate(proposal['proposal_id'])
        assert proposal['status'] == 'VALIDATED', proposal['validation_result']
        approved = proposal_service.review(proposal['proposal_id'], revision=proposal['revision'],
            decision='approve', actor='test-human', trace_id=str(uuid4()))
        proposal_service.apply(approved['proposal_id'], actor='test-human', trace_id=str(uuid4()))
        gateway = next(row for row in model.objects('HardwareNode') if row['device_type'] == 'Gateway')
        ports = [row for row in model.objects('HardwareNetworkInterface') if str(row['hardware_node_id']) == str(gateway['id'])]
        expected = {'Drive-S01', 'Display-S01'} if segmented else {'Drive', 'Display'}
        assert expected <= {row['network_ref'] for row in ports}
        route = wizard_generation.generate_routing({'prompt': prompt})
        route = proposal_service.validate(route['proposal_id'])
        assert route['status'] == 'VALIDATED', route['validation_result']
        assert len(route['changes']) == 1  # Only the confirmed Motorsteuerung-to-Anzeige route.
        assert any(change['data']['route']['gateways'] for change in route['changes'])

    result = execute(authority, 'test_backbone_ports', Permission.GENERATE_PROPOSAL, {}, lambda _: check())
    assert result.success, result


@pytest.mark.parametrize(('local_type', 'expected_identifier'), [('LIN', None), ('CAN', '0x100')])
def test_engineering_proposal_adds_local_controller_tx_message_for_actuator(
    monkeypatch, local_type, expected_identifier,
):
    def chain(name, device_type, interface_type, network_ref):
        return {
            'hardware_name': name,
            'hardware_description': f'{name} hardware',
            'device_type': device_type,
            'device_class': 3 if device_type == 'ECU' else 1,
            'function_name': f'{name}Function',
            'function_description': f'{name} function',
            'interface_name': f'{name}_{interface_type}',
            'interface_type': interface_type,
            'transport_network_ref': network_ref,
            'message_name': f'{name}Data',
            'message_id_hex': None,
            'direction': 'tx',
            'cycle_ms': 20,
            'dlc': 8,
            'signal_name': f'{name}Status',
            'start_bit': 0,
            'length_bits': 8,
            'byte_order': 'little_endian',
            'data_type': 'uint8',
            'factor': 1,
            'offset_value': 0,
        }

    spec = {
        'domain': 'Automotive',
        'modelType': 'automotive',
        'targetCounts': {'gateways': 0, 'ecus': 1, 'sensors': 0, 'actuators': 1},
        'communicationSystemCounts': {'can_fd': 1, local_type.casefold(): 1},
        'chains': [
            chain('System', 'Gateway', 'CAN_FD', 'Antriebsstrang'),
            chain('Abgasnachbehandlung', 'ECU', 'CAN_FD', 'Antriebsstrang'),
            chain(
                'AbgasnachbehandlungSchaltausgang',
                'ActuatorController',
                local_type,
                f'Antriebsstrang-IO-abgasnachbehandlung-{local_type.casefold()}',
            ),
        ],
    }
    graph = [{
        'network_id': 'can_fd',
        'bus_name': 'Antriebsstrang',
        'controllers': [{
            'ecu': 'Abgasnachbehandlung',
            'sensors': [],
            'actuators': ['AbgasnachbehandlungSchaltausgang'],
        }],
    }]
    prompt = '- Systemcluster-Graph: ' + json.dumps(graph, separators=(',', ':'))
    captured = {}

    monkeypatch.setattr(wizard_generation.proposal_store, 'list_proposals', lambda limit: [])
    monkeypatch.setattr(wizard_generation.model, 'objects', lambda _kind: [])
    monkeypatch.setattr(wizard_generation, 'extract_specification', lambda _prompt: spec)

    def capture(proposal_type, changes, summary, **metadata):
        captured.update(proposal_type=proposal_type, changes=changes, summary=summary, metadata=metadata)
        return captured

    monkeypatch.setattr(wizard_generation.proposal_service, 'create', capture)

    proposal = wizard_generation.generate({'prompt': prompt})
    changes = proposal['changes']
    by_ref = {'$' + item['local_ref']: item for item in changes if item.get('local_ref')}
    local_interface = next(
        item for item in changes
        if item['object_type'] == 'Interface'
        and item['data']['name'] == f'Abgasnachbehandlung_{local_type}_IO'
    )
    local_port = next(
        item for item in changes
        if item['object_type'] == 'HardwareNetworkInterface'
        and item['data']['hardware_node_id'] == local_interface['data'].get('hardware_node_id',
            by_ref[local_interface['data']['function_id']]['data']['hardware_node_id'])
        and item['data']['network_ref'] == f'Antriebsstrang-IO-abgasnachbehandlung-{local_type.casefold()}-S01'
    )
    local_message = next(
        item for item in changes
        if item['object_type'] == 'Message'
        and item['data']['name'] == f'Abgasnachbehandlung {local_type} IO Befehl'
    )
    actuator = next(
        item for item in changes
        if item['object_type'] == 'HardwareNode'
        and item['data']['name'] == 'AbgasnachbehandlungSchaltausgang'
    )
    backbone_message = next(
        item for item in changes
        if item['object_type'] == 'Message' and item['data']['name'] == 'Abgasnachbehandlung'
    )

    assert local_message['data']['direction'] == 'tx'
    assert by_ref[local_message['data']['interface_id']] is local_interface
    assert by_ref[local_message['data']['hardware_interface_id']] is local_port
    assert local_port['data']['technology'] == local_interface['data']['interface_type'] == local_type
    assert local_port['data']['network_ref'] == f'Antriebsstrang-IO-abgasnachbehandlung-{local_type.casefold()}-S01'
    assert local_message['data'].get('message_id_hex') == expected_identifier
    assert local_message['data']['configuration']['transport_unit']['consumer_refs'] == ['$' + actuator['local_ref']]
    assert local_message['data']['configuration']['cycle_source'] == 'ACTUATOR_STATUS_CANDIDATE_REQUIRES_REVIEW'
    assert backbone_message['data']['interface_id'] != local_message['data']['interface_id']
    assert backbone_message['data']['hardware_interface_id'] != local_message['data']['hardware_interface_id']
    confirmed_owner = by_ref[actuator['data']['identity']['system_owner_id']]
    assert confirmed_owner['data']['name'] == 'Abgasnachbehandlung'
    assert actuator['data']['identity']['system_owner_source'] == 'wizard-confirmed'
    assert changes.index(confirmed_owner) < changes.index(actuator)


def test_generate_routing_uses_local_actuator_message_but_keeps_hmi_backbone_message(monkeypatch):
    nodes = [
        {'id': 'ecu', 'name': 'Abgasnachbehandlung', 'device_type': 'ECU'},
        {'id': 'actuator', 'name': 'AbgasnachbehandlungSchaltausgang', 'device_type': 'ActuatorController'},
        {'id': 'hmi', 'name': 'Kombiinstrument', 'device_type': 'ECU'},
        {'id': 'gateway', 'name': 'System', 'device_type': 'Gateway'},
    ]
    interfaces = [
        {'id': 'ecu-can', 'name': 'Abgasnachbehandlung_CAN_FD', 'hardware_node_id': 'ecu', 'interface_type': 'CAN_FD'},
        {'id': 'ecu-lin', 'name': 'Abgasnachbehandlung_LIN_IO', 'hardware_node_id': 'ecu', 'interface_type': 'LIN'},
        {'id': 'actuator-lin', 'name': 'Schaltausgang_LIN', 'hardware_node_id': 'actuator', 'interface_type': 'LIN'},
        {'id': 'hmi-ethernet', 'name': 'Kombiinstrument_Ethernet', 'hardware_node_id': 'hmi', 'interface_type': 'Ethernet'},
    ]
    hardware_interfaces = [
        {'id': 'ecu-can-port', 'hardware_node_id': 'ecu', 'technology': 'CAN_FD', 'network_ref': 'Antriebsstrang'},
        {'id': 'ecu-lin-port', 'hardware_node_id': 'ecu', 'technology': 'LIN', 'network_ref': 'Local-LIN'},
        {'id': 'actuator-lin-port', 'hardware_node_id': 'actuator', 'technology': 'LIN', 'network_ref': 'Local-LIN'},
        {'id': 'hmi-ethernet-port', 'hardware_node_id': 'hmi', 'technology': 'Ethernet', 'network_ref': 'Infotainment'},
    ]
    messages = [
        {
            'id': 'backbone-message',
            'name': 'AbgasnachbehandlungData',
            'interface_id': 'ecu-can',
            'hardware_interface_id': 'ecu-can-port',
            'direction': 'tx',
        },
        {
            'id': 'local-actuator-message',
            'name': 'Abgasnachbehandlung_LIN_IO_Command',
            'interface_id': 'ecu-lin',
            'hardware_interface_id': 'ecu-lin-port',
            'direction': 'tx',
            'configuration': {'transport_unit': {'consumer_refs': ['actuator']}},
        },
    ]
    objects = {
        'HardwareNode': nodes,
        'Interface': interfaces,
        'HardwareNetworkInterface': hardware_interfaces,
        'Message': messages,
        'Function': [],
        'Signal': [],
    }
    graph = [{
        'controllers': [{
            'ecu': 'Abgasnachbehandlung',
            'sensors': [],
            'actuators': ['AbgasnachbehandlungSchaltausgang'],
        }],
        'hmi_routes': [{'source': 'Abgasnachbehandlung', 'target': 'Kombiinstrument'}],
    }]
    prompt = '- Systemcluster-Graph: ' + json.dumps(graph, separators=(',', ':'))
    calls = []

    class FakeRoutingGenerationService:
        def _hardware_graph(self):
            return {}, {}
        def generate_route(self, *, source_node_id, destination_node_id, message_id):
            calls.append((source_node_id, destination_node_id, message_id))
            local = message_id == 'local-actuator-message'
            destination_protocol = 'LIN' if destination_node_id == 'actuator' else 'ETHERNET'
            return {
                'name': f'{source_node_id} to {destination_node_id}',
                'source': {
                    'node_id': source_node_id,
                    'interface_id': 'ecu-lin' if local else 'ecu-can',
                    'port_id': 'ecu-lin-port' if local else 'ecu-can-port',
                    'network_id': 'Local-LIN' if local else 'Antriebsstrang',
                    'protocol': 'LIN' if local else 'CAN_FD',
                },
                'payload': {'message_id': message_id, 'signal_ids': []},
                'destinations': [{'node_id': destination_node_id, 'protocol': destination_protocol}],
                'route': {
                    'hops': [{'node_id': source_node_id},
                             *([{'node_id': 'gateway', 'name': 'System'}] if destination_node_id == 'hmi' else []),
                             {'node_id': destination_node_id}],
                    'gateways': [{'node_id': 'gateway', 'name': 'System'}] if destination_node_id == 'hmi' else [],
                    'transformations': [],
                    'priority': 'NORMAL',
                },
                'timing': {},
                'routing_policy': {},
                'validation': {'valid': True},
            }

    messages.extend([
        {**messages[0], 'id': 'second-backbone-message'},
        {'id': 'feedback-message', 'interface_id': 'actuator-lin', 'hardware_interface_id': 'actuator-lin-port', 'direction': 'tx'},
    ])
    captured = {}
    monkeypatch.setattr(wizard_generation.proposal_store, 'list_proposals', lambda limit: [])
    monkeypatch.setattr(wizard_generation.model, 'objects', lambda kind: objects[kind])
    monkeypatch.setattr(wizard_generation, 'RoutingGenerationService', FakeRoutingGenerationService)

    def capture(proposal_type, changes, summary, **metadata):
        captured.update(proposal_type=proposal_type, changes=changes, summary=summary, metadata=metadata)
        return captured

    monkeypatch.setattr(wizard_generation.proposal_service, 'create', capture)

    proposal = wizard_generation.generate_routing({'prompt': prompt})
    actuator_route, feedback_route, hmi_route, second_hmi = [item['data'] for item in proposal['changes']]

    assert calls == [
        ('ecu', 'actuator', 'local-actuator-message'),
        ('actuator', 'ecu', 'feedback-message'),
        ('ecu', 'hmi', 'backbone-message'),
        ('ecu', 'hmi', 'second-backbone-message'),
    ]
    assert actuator_route['payload']['message_id'] == 'local-actuator-message'
    assert actuator_route['source']['interface_id'] == 'ecu-lin'
    assert actuator_route['source']['port_id'] == 'ecu-lin-port'
    assert actuator_route['route']['gateways'] == []
    assert hmi_route['payload']['message_id'] == 'backbone-message'
    assert hmi_route['route']['gateways'] == [{'node_id': 'gateway', 'name': 'System'}]
    assert hmi_route['route']['transformations'][0]['type'] == 'PROTOCOL_TRANSLATION'


def test_semantic_network_assignment_keeps_powertrain_on_one_named_can():
    motor = {'name': 'Motorsteuerung', 'device_type': 'ECU'}
    fuel = {'name': 'Kraftstoffsystem', 'device_type': 'ECU'}
    brake = {'name': 'Bremsensteuerung', 'device_type': 'ECU'}

    assert wizard_generation._semantic_physical_network('can_fd', motor, fuel) == (
        'antriebsstrang-can-fd-bus', 'Antriebsstrang-CAN')
    assert wizard_generation._semantic_physical_network('can_fd', motor, fuel) != (
        wizard_generation._semantic_physical_network('can_fd', brake, brake)
    )


def test_confirmed_gateway_architecture_honors_configured_seven_total_participants():
    controllers = [
        {'ecu': f'Controller{i}', 'sensors': [f'Sensor{i}'], 'actuators': [f'Actuator{i}']}
        for i in range(1, 8)
    ]
    graph = json.dumps([{
        'cluster_id': 'family:chassis',
        'label': 'Fahrwerk / Fahrdynamik',
        'bus_name': 'Fahrwerk_Fahrdynamik_03',
        'controllers': controllers,
    }], separators=(',', ':'))
    prompt = (
        '- Netzarchitektur-ID: gateway_ecu_segments\n'
        '- Bus-Teilnehmergrenzen: {"can_fd":7}\n'
        f'- Systemcluster-Graph: {graph}\n'
    )

    memberships = wizard_generation._confirmed_segment_memberships(prompt)
    local_memberships = wizard_generation._confirmed_local_io_memberships(prompt)

    assert memberships['controller1'][0][0] == 'Fahrwerk_Fahrdynamik_03-S01'
    assert 'sensor6' not in memberships
    assert local_memberships['sensor6'][0] == 'controller6'
    assert local_memberships['actuator7'][0] == 'controller7'
    assert wizard_generation._segmented_physical_network(
        'can_fd', memberships,
        {'name': 'Controller7', 'device_type': 'ECU'},
    ) == ('Fahrwerk_Fahrdynamik_03-S02', 'Fahrwerk / Fahrdynamik-CAN Segment 2')
    assert wizard_generation._local_io_physical_network(
        'can_fd', local_memberships,
        {'name': 'Sensor7', 'device_type': 'SensorController'},
        {'name': 'Controller7', 'device_type': 'ECU'},
    ) == ('Fahrwerk_Fahrdynamik_03-IO-controller7-can-fd-S01', 'Controller7 CAN I/O Segment 1')


def test_combined_wizard_creates_validated_model_without_reasoner(monkeypatch, tmp_path):
    authority = ToolAuthority(f'pytest-wizard-generator-{uuid4()}')
    prompt = '''Strukturierte Vorgaben fuer den Engineering-Agenten:
- Lauf-ID: test-wizard-12345678
- Industrie: Automotive
- Netzwerktechnologien: CAN-FD (can_fd); LIN (lin)
- Hardware-Sollwerte: {"gateways":1,"ecus":50,"sensors":100,"actuators":100}
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
Erzeuge ein Fahrzeugnetzwerk mit 100 Sensoren, 100 Aktuatoren, 50 ECUs und 1 Gateway.
25 LIN, 10 CAN-FD und 5 Automotive Ethernet. Prüfe, welche Nachrichten das Gateway passieren.
'''

    class NoReasoner:
        async def next(self, *args):
            raise AssertionError('Confirmed mass creation must not depend on an LLM tool decision')

    async def invoke():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAgent(client, reasoner=NoReasoner()).run(
                prompt, AgentContext(active_project_id=authority.project_id))

    result = asyncio.run(invoke())
    assert result['status'] == 'READY_FOR_REVIEW', result
    proposal = result['proposals'][0]
    assert proposal['status'] == 'VALIDATED', proposal['validation_result']
    hardware = [c for c in proposal['changes'] if c['object_type'] == 'HardwareNode']
    assert len(hardware) == 251
    assert len({c['data']['name'] for c in hardware}) == 251
    assert not proposal['canonical_ids']  # Review remains required.
    assert any(event.get('workload', {}).get('completed', 0) > 0 for event in result['events'] if event.get('workload'))
    by_ref = {'$' + c['local_ref']: c for c in proposal['changes']}
    signal_counts = Counter()
    for change in proposal['changes']:
        if change['object_type'] != 'Signal':
            continue
        message = by_ref[change['data']['message_id']]
        port = by_ref[message['data']['hardware_interface_id']]
        signal_counts[port['data']['hardware_node_id']] += 1
    assert all(signal_counts['$' + c['local_ref']] >= 5 for c in hardware if c['data']['device_type'] == 'ECU')
    duplicate = execute(authority, 'test_retry', Permission.GENERATE_PROPOSAL, {}, lambda _: wizard_generation.generate({'prompt': prompt}))
    assert duplicate.success, duplicate
    assert duplicate.data['proposal_id'] == proposal['proposal_id']
    untouched = execute(authority, 'test_canonical', Permission.READ_MODEL, {}, lambda _: model.objects('HardwareNode'))
    assert untouched.data == []
    # Simulate the two explicit human actions in this isolated test project only.
    approved = execute(authority, 'test_human_review', Permission.READ_MODEL, {}, lambda _: proposal_service.review(
        proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='test-human', trace_id=str(uuid4())))
    assert approved.success and approved.data['status'] == 'APPROVED', approved
    applied = execute(authority, 'test_human_apply', Permission.READ_MODEL, {}, lambda _: proposal_service.apply(
        proposal['proposal_id'], actor='test-human', trace_id=str(uuid4())))
    assert applied.success and applied.data['status'] == 'APPLIED', applied
    assert len(applied.data['canonical_ids']) == len(proposal['changes'])
    check = WorkflowStatusService(authority.project_id).get(summary=True)['artifact_checks']['engineering_model']
    assert check['complete'], check
    assert check['consistency']['functions_unexpected'] == 0
    def restore_review_state():
        state = conversation.read()
        state.update(active_proposal=proposal['proposal_id'], current_requirement=prompt)
        conversation.write(state)
        WorkflowStatusService(authority.project_id).set_context({'agent_execution': {
            'run_id': 'test-wizard-12345678', 'state': 'REVIEW_REQUIRED', 'step': 'engineering_model',
            'completed': 1, 'total': 1}})
        reconcile_model_apply(authority.project_id, applied.data)
        return WorkflowStatusService(authority.project_id).get(summary=True)['context']['agent_execution']
    reconciled = execute(authority, 'test_apply_status', Permission.READ_MODEL, {}, lambda _: restore_review_state())
    assert reconciled.success and reconciled.data['state'] == 'READY_TO_CONTINUE', reconciled

    canonical_hardware = sorted(execute(authority, 'test_route_nodes', Permission.READ_MODEL, {},
        lambda _: model.objects('HardwareNode')).data, key=lambda item: item['name'].casefold())
    interfaces = execute(authority, 'test_route_interfaces', Permission.READ_MODEL, {}, lambda _: model.objects('Interface')).data
    # SQL created_at values share one transaction timestamp; UUID ordering must
    # not select a different transport fixture or calculated function per run.
    interface_by_node = {str(item.get('hardware_node_id')): item.get('interface_type') for item in
                         sorted(interfaces, key=lambda item: (item.get('configuration') or {}).get('endpoint_role') == 'SYSTEM_CONTROLLER')}
    available_sensor_types = {interface_by_node[str(item['id'])] for item in canonical_hardware if item['device_type'] == 'SensorController'}
    available_actuator_types = {interface_by_node[str(item['id'])] for item in canonical_hardware if item['device_type'] == 'ActuatorController'}
    ecu = next(item for item in canonical_hardware if item['device_type'] == 'ECU' and interface_by_node[str(item['id'])] in available_sensor_types & available_actuator_types)
    ecu_type = interface_by_node[str(ecu['id'])]
    sensor = next(item for item in canonical_hardware if item['device_type'] == 'SensorController' and interface_by_node[str(item['id'])] == ecu_type)
    actuator = next(item for item in canonical_hardware if item['device_type'] == 'ActuatorController' and interface_by_node[str(item['id'])] == ecu_type)
    hmi = next(item for item in canonical_hardware if item['device_type'] == 'ECU' and interface_by_node[str(item['id'])] != ecu_type)
    # This positive end-to-end fixture explicitly budgets shared LIN scheduling
    # and the gateway hop. Strict deadline failures are covered separately; a
    # random catalog sensor with timeout == cycle is not a valid success fixture.
    def define_fixture_timing():
        from backend.engineering.repository import update_object
        define_fixture_command_signals()
        # This fixture explicitly connects the selected participants to one
        # test bus; protocol equality alone must no longer fabricate a path.
        selected_nodes = {str(item['id']) for item in (ecu, sensor, actuator, hmi)}
        confirmed_rates = {'CAN_FD': 500_000, 'LIN': 19_200, 'Ethernet': 100_000_000}
        def confirmed_bus_rates(technology):
            return {'bitrate': confirmed_rates[technology], **({'arbitration_bitrate': 500_000,
                'data_bitrate': 2_000_000} if technology == 'CAN_FD' else {})}
        for port in model.objects('HardwareNetworkInterface'):
            network = 'fixture-confirmed-shared-bus' if port['technology'] == ecu_type else 'fixture-' + port['technology'].lower()
            # This positive simulation fixture explicitly confirms the bus rate.
            # Registry defaults alone are insufficient for capacity release.
            update_object('HardwareNetworkInterface', str(port['id']), {
                'network_ref': network,
                'capabilities': {**(port.get('capabilities') or {}),
                                 **confirmed_bus_rates(port['technology'])},
            })
        gateway = next(item for item in canonical_hardware if item['device_type'] == 'Gateway')
        all_ports = model.objects('HardwareNetworkInterface')
        source_port = next(p for p in all_ports if str(p['hardware_node_id']) == str(ecu['id']) and p['technology'] == ecu_type)
        target_port = next(p for p in all_ports if str(p['hardware_node_id']) == str(hmi['id']) and p['technology'] == interface_by_node[str(hmi['id'])])
        update_object('HardwareNetworkInterface', str(target_port['id']), {'network_ref': 'fixture-hmi-bus'})
        target_port = {**target_port, 'network_ref': 'fixture-hmi-bus'}
        canvas_nodes = {}
        edges = []
        def fixture_canvas_port(node, port):
            canvas = canvas_nodes.setdefault(str(node['id']), {'id': str(node['id']), 'engineeringId': str(node['id']), 'name': node['name'], 'kind': 'gateway' if node['device_type'] == 'Gateway' else 'ecu', 'x': 0, 'y': 0, 'ports': []})
            bus = {'CAN_FD': 'can_fd', 'LIN': 'lin', 'Ethernet': 'automotive_ethernet'}.get(port['technology'], port['technology'].lower())
            result = {'id': str(port['id']), 'hardwareInterfaceId': str(port['id']), 'engineeringId': str(port['id']), 'physicalNetworkId': port['network_ref'], 'bus': bus, 'name': port['name'], 'side': 'right', 'offset': 0.5}
            canvas['ports'].append(result)
            return result
        for index, (node, endpoint) in enumerate([(ecu, source_port), (hmi, target_port)]):
            gateway_port = create_object('HardwareNetworkInterface', {'hardware_node_id': str(gateway['id']), 'name': 'Fixture gateway ' + str(index), 'technology': endpoint['technology'], 'network_ref': endpoint['network_ref'], 'channel_index': 100 + index,
                'capabilities': confirmed_bus_rates(endpoint['technology'])})
            left, right = fixture_canvas_port(node, endpoint), fixture_canvas_port(gateway, gateway_port)
            edges.append({'id': 'fixture-edge-' + str(index), 'source': str(node['id']), 'target': str(gateway['id']), 'sourcePort': left['id'], 'targetPort': right['id'], 'bus': left['bus'], 'physicalNetworkId': endpoint['network_ref'], 'engineeringRelationId': 'fixture-' + str(index), 'routingEntryIds': [], 'origin': 'TEST_SPECIFICATION'})
        # Physical canonical bus membership is sufficient before the editor is generated.
        from backend.engineering.repository import update_object
        source_ids = {str(item['id']) for item in (sensor, actuator, ecu)}
        selected_interfaces = {str(item['id']) for item in interfaces if str(item.get('hardware_node_id')) in source_ids}
        configured = {}
        aliases = {'maximum_latency_ms', 'maximum_latency', 'deadline_ms', 'deadline', 'maximum_jitter_ms',
                   'maximum_jitter', 'timeout', 'data_freshness_limit'}
        for message in model.objects('Message'):
            if str(message.get('interface_id')) not in selected_interfaces:
                continue
            limits = {'max_latency_ms': 100, 'jitter_limit_ms': 20,
                      'timeout_ms': max(500, 3 * float(message.get('cycle_ms') or 100)),
                      'freshness_ms': max(500, 3 * float(message.get('cycle_ms') or 100))}
            configuration = {key: value for key, value in (message.get('configuration') or {}).items() if key not in aliases}
            update_object('Message', str(message['id']), {'configuration': {**configuration, **limits}})
            configured[str(message['id'])] = limits
        for signal in model.objects('Signal'):
            limits = configured.get(str(signal.get('message_id')))
            if limits:
                communication = {key: value for key, value in (signal.get('communication') or {}).items() if key not in aliases}
                update_object('Signal', str(signal['id']), {'communication': {**communication, **limits}})
    timed = execute(authority, 'test_define_transport_requirements', Permission.READ_MODEL, {}, lambda _: define_fixture_timing())
    assert timed.success, timed
    graph = json.dumps([{'cluster_id': 'test', 'controllers': [{
        'ecu': ecu['name'], 'sensors': [sensor['name']], 'actuators': [actuator['name']]}],
        'hmi_routes': [{'source': ecu['name'], 'target': hmi['name']}]}], separators=(',', ':'))
    continuation_prompt = prompt + f'\n- Systemcluster-Graph: {graph}\nFortsetzung des bestätigten Wizard-Auftrags: Ziel: routing.'
    async def route_continuation():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAgent(client, reasoner=NoReasoner()).run(
                continuation_prompt, AgentContext(active_project_id=authority.project_id))
    routed = asyncio.run(route_continuation())
    if routed['status'] != 'READY_FOR_REVIEW':
        print(json.dumps([p.get('validation_result') for p in routed.get('proposals', [])], default=str))
    assert routed['status'] == 'READY_FOR_REVIEW', routed
    routing_proposal = routed['proposals'][0]
    assert routing_proposal['proposal_type'] == 'WIZARD_ROUTING'
    assert routing_proposal['status'] == 'VALIDATED'
    assert len(routing_proposal['changes']) == 4  # Includes the actuator feedback transport
    hmi_route = routing_proposal['changes'][-1]['data']
    assert hmi_route['route']['gateways']
    assert hmi_route['route']['transformations'][0]['type'] == 'PROTOCOL_TRANSLATION'
    assert not routing_proposal['canonical_ids']

    route_approved = execute(authority, 'test_routing_review', Permission.READ_MODEL, {}, lambda _: proposal_service.review(
        routing_proposal['proposal_id'], revision=routing_proposal['revision'], decision='approve', actor='test-human', trace_id=str(uuid4())))
    assert route_approved.success and route_approved.data['status'] == 'APPROVED', route_approved
    route_applied = execute(authority, 'test_routing_apply', Permission.READ_MODEL, {}, lambda _: proposal_service.apply(
        routing_proposal['proposal_id'], actor='test-human', trace_id=str(uuid4())))
    assert route_applied.success and route_applied.data['status'] == 'APPLIED', route_applied
    routing_check = WorkflowStatusService(authority.project_id).get(summary=True)['artifact_checks']['routing']
    assert not routing_check['complete']
    assert routing_check['coverage']['missing_message_ids']
    blocked_repeat = asyncio.run(route_continuation())
    assert blocked_repeat['status'] == 'INCOMPLETE'
    assert not blocked_repeat['proposals']
    assert not any(event['type'] == 'APPROVAL' for event in blocked_repeat['events'])
    # This mass-model test confirms four relationships only. The remaining
    # devices do not acquire invented consumers merely to make the gate green.
    selected_messages = sorted({message_id for change in routing_proposal['changes']
                                for message_id in ([change['data']['payload']['message_id']]
                                                   if change['data']['payload'].get('message_id') else
                                                   change['data']['payload'].get('message_ids') or [])})
    service = WorkflowStatusService(authority.project_id)
    service.save_parameters({**service.get()['parameters'], 'simulation_scope': {
        'mode': 'MESSAGE', 'include_all': False, 'message_ids': selected_messages, 'signal_ids': [],
        'reason': 'Integrationstest der vier explizit bestätigten Transportbeziehungen im großen Modell.',
    }})
    routing_check = service.get(summary=True)['artifact_checks']['routing']
    assert routing_check['complete'], routing_check
    assert routing_check['coverage']['scope_mode'] == 'SELECTED'
    assert routing_check['coverage']['excluded_messages'] > 0

    network_prompt = prompt + f'\n- Systemcluster-Graph: {graph}\nFortsetzung des bestätigten Wizard-Auftrags: Ziel: data_science_intelligence.'
    async def network_continuation():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAgent(client, reasoner=NoReasoner()).run(
                network_prompt, AgentContext(active_project_id=authority.project_id))
    networked = asyncio.run(network_continuation())
    assert networked['status'] == 'READY_FOR_REVIEW', networked
    network_proposal = networked['proposals'][0]
    assert network_proposal['proposal_type'] == 'WIZARD_NETWORK_TOPOLOGY'
    assert network_proposal['status'] == 'VALIDATED', network_proposal['validation_result']
    topology = next(change['data']['topology'] for change in network_proposal['changes'] if change['object_type'] == 'NetworkTopology')
    assert len(topology['nodes']) == len(canonical_hardware)
    assert len(topology['edges']) >= 3
    assert all(node['engineeringId'] for node in topology['nodes'])
    assert all(edge.get('engineeringRelationId') or edge.get('engineeringSegmentId') for edge in topology['edges'])
    assert all(edge.get('engineeringSegmentId') and not edge.get('engineeringRelationId')
               for edge in topology['edges'] if edge['origin'] == 'ROUTING_TABLE')
    assert all(edge['routingEntryIds'] for edge in topology['edges'] if edge['origin'] == 'ROUTING_TABLE')
    connected_node_ids = {node_id for edge in topology['edges'] for node_id in (edge['source'], edge['target'])}
    assert connected_node_ids == {node['id'] for node in topology['nodes']}
    assert WorkflowStatusService(authority.project_id).get(summary=True)['artifact_checks']['network_editor']['status'] == 'EMPTY'

    topology_approved = execute(authority, 'test_topology_review', Permission.READ_MODEL, {}, lambda _: proposal_service.review(
        network_proposal['proposal_id'], revision=network_proposal['revision'], decision='approve', actor='test-human', trace_id=str(uuid4())))
    assert topology_approved.success and topology_approved.data['status'] == 'APPROVED', topology_approved
    topology_applied = execute(authority, 'test_topology_apply', Permission.READ_MODEL, {}, lambda _: proposal_service.apply(
        network_proposal['proposal_id'], actor='test-human', trace_id=str(uuid4())))
    assert topology_applied.success and topology_applied.data['status'] == 'APPLIED', topology_applied
    topology_check = WorkflowStatusService(authority.project_id).get(summary=True)['artifact_checks']['network_editor']
    assert topology_check['complete'], topology_check
    assert topology_check['counts'] == {'nodes': len(canonical_hardware), 'edges': len(topology['edges'])}
    def restore_topology_conversation():
        topology_conversation = conversation.read()
        topology_conversation.update(active_proposal=network_proposal['proposal_id'], current_requirement=network_prompt)
        conversation.write(topology_conversation)
    restored = execute(authority, 'test_topology_conversation', Permission.READ_MODEL, {}, lambda _: restore_topology_conversation())
    assert restored.success, restored
    WorkflowStatusService(authority.project_id).set_context({'agent_execution': {
        'run_id': 'test-wizard-12345678', 'state': 'REVIEW_REQUIRED', 'step': 'network_editor',
        'completed': 1, 'total': 1}})
    topology_status = execute(authority, 'test_topology_apply_status', Permission.READ_MODEL, {}, lambda _: (
        reconcile_model_apply(authority.project_id, topology_applied.data),
        WorkflowStatusService(authority.project_id).get(summary=True)['context']['agent_execution'],
    )[1])
    assert topology_status.success and topology_status.data['state'] == 'READY_TO_CONTINUE', topology_status
    assert topology_status.data['step'] == 'parameters', topology_status

    # A partial parameter draft used to send this continuation to the LLM and
    # leave the wizard blocked without a canonical change.
    # This fixture explicitly uses shared cross-system transports to exercise
    # gateway translation. Declare that architecture; it is not a local branch.
    shared_networks = execute(authority, 'test_shared_networks', Permission.READ_MODEL, {},
                              lambda _: model.networks()).data
    # Fresh model/topology creation must not turn a UI/default duration into an
    # unmarked explicit limit before the registry-default step owns provenance.
    initial_parameters = WorkflowStatusService(authority.project_id).get()['parameters']
    assert 'duration_s' not in initial_parameters or (initial_parameters.get('parameter_provenance') or {}).get('duration_s', {}).get('source') == 'TECHNOLOGY_DEFAULT'
    WorkflowStatusService(authority.project_id).save_parameters(
        {'target_bus_load_percent': 60,
         'networks': [{**network, 'spatial_scope': 'backbone'} for network in shared_networks]}, actor='test-human'
    )
    assert not WorkflowStatusService(authority.project_id).get(summary=True)['artifact_checks']['parameters']['complete']

    capacity_prompt = prompt + '\nFortsetzung des bestätigten Wizard-Auftrags: Ziel: capacity_timing.'
    async def capacity_continuation():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAgent(client, reasoner=NoReasoner()).run(
                capacity_prompt, AgentContext(active_project_id=authority.project_id))
    capacity_result = asyncio.run(capacity_continuation())
    assert capacity_result['status'] == 'COMPLETED', capacity_result
    assert any(item['tool'] == 'generate_wizard_parameters' and item['status'] == 'SUCCESS'
               for item in capacity_result['trace'])
    assert any(item['tool'] == 'calculate_capacity' and item['status'] == 'SUCCESS'
               for item in capacity_result['trace'])
    parameter_state = WorkflowStatusService(authority.project_id).get()
    assert parameter_state['artifact_checks']['parameters']['complete']
    assert parameter_state['parameters']['technology'] in parameter_state['parameters']['technology_defaults']
    assert {'can_fd', 'lin'}.issubset(parameter_state['parameters']['technology_defaults'])
    assert parameter_state['parameters']['parameter_provenance']['duration_s'] == {'source': 'TECHNOLOGY_DEFAULT', 'value': 1}
    capacity_status = WorkflowStatusService(authority.project_id).get(summary=True)['statuses']['capacity_timing']
    assert capacity_status in {'COMPLETE', 'WARNING'}, capacity_status
    capacity_snapshot = WorkflowStatusService(authority.project_id).latest_analysis('capacity_timing')
    assert capacity_snapshot['results']['overview']['route_count'] == 4
    assert capacity_snapshot['results']['overview']['network_count'] >= 1

    from backend.engineering.agent_tools import simulation_gateway
    from backend.app import create_app
    import importlib
    application_api = importlib.import_module('backend.app.api')
    from backend.app import job_service
    from backend.engineering.project_context import current_project_id
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT', str(tmp_path / 'saved'))
    jobs = job_service.JobService(synchronous=True, persist=False)
    monkeypatch.setattr(application_api, 'JOBS', jobs)
    client = create_app(testing=True).test_client()
    def local_http(path, payload=None):
        response = client.open('/api' + path, method='GET' if payload is None else 'POST',
                               json=payload, headers={'X-Project-ID': current_project_id()})
        assert response.status_code < 400, response.get_json()
        return response.get_json()
    monkeypatch.setattr(simulation_gateway, 'request_json', local_http)

    simulation_result = asyncio.run(network_continuation())
    assert simulation_result['status'] == 'COMPLETED', json.dumps(simulation_result, default=str)
    simulation_tools = [item['tool'] for item in simulation_result['trace']]
    assert 'validate_simulation_preflight' in simulation_tools
    assert 'create_simulation_snapshot' in simulation_tools
    assert 'start_simulation' in simulation_tools
    assert 'get_simulation_status' in simulation_tools
    assert 'assess_intelligence' in simulation_tools
    assert 'kein prüfbarer Änderungs- oder Workload-Aufruf' not in simulation_result['text']
    workflow_after_simulation = WorkflowStatusService(authority.project_id).get(summary=True)
    simulation_analysis = WorkflowStatusService(authority.project_id).latest_analysis('results_analysis')
    frozen_snapshot = WorkflowStatusService(authority.project_id).get_simulation_snapshot(simulation_analysis['results']['simulation_snapshot_id'])
    assert frozen_snapshot['configuration']['observation_window']['source'] == 'DERIVED_REQUIREMENTS'
    assert frozen_snapshot['configuration']['parameters']['parameter_provenance']['duration_s']['source'] == 'TECHNOLOGY_DEFAULT'
    assert workflow_after_simulation['statuses']['simulation'] == 'COMPLETE', json.dumps({
        'assessment': simulation_analysis['results'].get('assessment'),
        'findings': simulation_analysis.get('findings'),
    }, default=str)
    assert workflow_after_simulation['statuses']['results_analysis'] == 'COMPLETE'
    assert workflow_after_simulation['statuses']['data_science_intelligence'] in {'COMPLETE', 'WARNING'}
    assert all(value in {'COMPLETE', 'APPROVED', 'WARNING'}
               for value in workflow_after_simulation['statuses'].values())
    assert list((tmp_path / 'saved' / authority.project_id / 'runs').rglob('universal_trace.jsonl'))
    repeated = asyncio.run(network_continuation())
    assert repeated['status'] == 'COMPLETED'
    assert not any(item['tool'] == 'start_simulation' for item in repeated['trace'])
    assert len(jobs.list(authority.project_id)) == 1


def test_rail_cluster_graph_produces_valid_native_rail_interfaces():
    authority = ToolAuthority(f'pytest-rail-wizard-{uuid4()}')
    prompt = '''Strukturierte Vorgaben fuer den Engineering-Agenten:
- Lauf-ID: test-rail-wizard
- Industrie: Rail
- Systemcluster-Graph: [{"network_id":"mvb","network_label":"rail · mvb","controllers":[{"ecu":"TrainControl","sensors":["TrainSpeed"],"actuators":["TrainControlStellglied"]}]}]
- Hardware-Sollwerte: {"gateways":1,"ecus":1,"sensors":1,"actuators":1}
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
Erzeuge ein kleines Rail-Modell mit einem Gateway, einer ECU, einem Sensor und einem Aktor.
'''

    result = execute(authority, 'test_rail_wizard', Permission.GENERATE_PROPOSAL, {},
                     lambda _: wizard_generation.generate({'prompt': prompt}))
    assert result.success, result.findings
    validated = execute(authority, 'test_rail_validate', Permission.VALIDATE,
                        {'proposal_id': result.data['proposal_id']},
                        lambda args: proposal_service.validate(args['proposal_id']))
    assert validated.success, validated.findings
    assert validated.data['status'] == 'VALIDATED', validated.data['validation_result']
    rail_interfaces = [change['data'] for change in validated.data['changes']
                       if change['object_type'] in {'Interface', 'HardwareNetworkInterface'}
                       and (change['data'].get('interface_type') == 'MVB' or change['data'].get('technology') == 'MVB')]
    assert rail_interfaces


def test_industrial_model_type_generates_plc_and_registry_backed_transport_chain():
    authority = ToolAuthority(f'pytest-industrial-wizard-{uuid4()}')
    prompt = '''Strukturierte Vorgaben fuer den Engineering-Agenten:
- Lauf-ID: test-industrial-wizard
- Industrie: Industrial Automation / SPS
- Projekt-Modelltyp: industrial_automation
- Kommunikationstechnologien: PROFINET
- Systemcluster-Graph: [{"network_id":"profinet","network_label":"industrial_automation · profinet","controllers":[{"ecu":"SPSLeitsystem","sensors":["Temperatur"],"actuators":[]}]}]
- Hardware-Sollwerte: {"gateways":0,"ecus":1,"sensors":1,"actuators":0}
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
Erzeuge eine SPS mit Temperaturmessung über PROFINET.
'''

    result = execute(authority, 'test_industrial_wizard', Permission.GENERATE_PROPOSAL, {},
                     lambda _: wizard_generation.generate({'prompt': prompt}))
    assert result.success, result.findings
    proposal = result.data
    hardware = [change['data'] for change in proposal['changes'] if change['object_type'] == 'HardwareNode']
    assert len([item for item in hardware if item['device_type'] == 'PLC']) == 1
    assert not [item for item in hardware if item['device_type'] == 'ECU']
    ports = [change['data'] for change in proposal['changes'] if change['object_type'] == 'HardwareNetworkInterface']
    assert ports and all(port['technology'] == 'ProfiNET' for port in ports)
    messages = [change['data'] for change in proposal['changes'] if change['object_type'] == 'Message']
    assert all(message['configuration']['model_type'] == 'TransportUnit' for message in messages)
    assert all(message['configuration']['technology_binding']['technology_id'] == 'profinet' for message in messages)
    signals = [change['data'] for change in proposal['changes'] if change['object_type'] == 'Signal']
    assert all(signal['protocol_bindings'][0]['model_type'] == 'PayloadElement' for signal in signals)
    assert proposal['evidence'][0]['model_type'] == 'industrial_automation'


def test_mixed_confirmed_controller_technologies_create_separate_networks():
    authority = ToolAuthority(f'pytest-industrial-mixed-network-{uuid4()}')
    prompt = '''Strukturierte Vorgaben fuer den Engineering-Agenten:
- Lauf-ID: test-industrial-mixed-network
- Industrie: Industrial Automation / SPS
- Projekt-Modelltyp: industrial_automation
- Netzwerktechnologien: Ethernet; PROFINET; EtherCAT
- Netzarchitektur-ID: gateway_ecu_segments
- Hardware-Sollwerte: {"gateways":1,"ecus":3,"sensors":0,"actuators":0}
- Geräteanschlüsse: {"PLC1":"PROFINET","PLC2":"PROFINET","PLC3":"EtherCAT","System":"Ethernet"}
- Systemcluster-Graph: [{"network_id":"ethernet","network_label":"Ethernet","bus_name":"Maschine_Motion","controllers":[{"ecu":"PLC1"},{"ecu":"PLC2"},{"ecu":"PLC3"}]}]
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
Erzeuge drei PLCs mit PROFINET- und EtherCAT-Segmenten an einem Ethernet-Backbone.
'''

    def generate_apply_and_repeat():
        proposal = wizard_generation.generate({'prompt': prompt})
        validated = proposal_service.validate(proposal['proposal_id'])
        assert validated['status'] == 'VALIDATED', validated['validation_result']
        approved = proposal_service.review(proposal['proposal_id'], revision=validated['revision'],
            decision='approve', actor='test-human', trace_id=str(uuid4()))
        proposal_service.apply(approved['proposal_id'], actor='test-human', trace_id=str(uuid4()))
        repeated = wizard_generation.generate({'prompt': prompt + '\n- Wiederholungsprüfung: gleiche bestätigte Architektur'})
        return {'proposal': proposal, 'repeated': repeated}

    result = execute(authority, 'test_industrial_mixed_network', Permission.GENERATE_PROPOSAL, {},
                     lambda _: generate_apply_and_repeat())
    assert result.success, result.findings
    proposal = result.data['proposal']
    repeated = result.data['repeated']
    networks = [change['data'] for change in proposal['changes'] if change['object_type'] == 'Network']
    by_technology = {network['technology']: network for network in networks}
    assert by_technology['PROFINET']['id'] == 'Maschine_Motion-profinet-S01'
    assert by_technology['ETHERCAT']['id'] == 'Maschine_Motion-ethercat-S01'
    interfaces = [change['data'] for change in proposal['changes']
                  if change['object_type'] == 'HardwareNetworkInterface']
    assert {(interface['technology'], interface['network_ref']) for interface in interfaces} >= {
        ('ProfiNET', 'Maschine_Motion-profinet-S01'),
        ('EtherCAT', 'Maschine_Motion-ethercat-S01'),
    }
    repeated_creates = [change for change in repeated.get('changes') or []
                        if change.get('action', 'CREATE') == 'CREATE']
    assert not repeated_creates, repeated_creates


@pytest.mark.parametrize('architecture', ['gateway_ecu_segments', 'gateway_segments_hybrid_ai'])
def test_v4_physical_memberships_split_explicit_controller_buses(architecture):
    prompt = '''- Netzarchitektur-ID: ARCHITECTURE
- Geräteanschlüsse: {"PLC1":"ProfiNET","PLC2":"ProfiNET","PLC3":"EtherCAT"}
- Systemcluster-Graph: [{"network_id":"detected:ethernet","bus_name":"Maschine_Motion","controllers":[{"ecu":"PLC1"},{"ecu":"PLC2"},{"ecu":"PLC3"}]}]
'''.replace('ARCHITECTURE', architecture)

    memberships = wizard_generation._confirmed_segment_memberships(prompt)

    assert memberships['plc1'][0][0] == 'Maschine_Motion-profinet-S01'
    assert memberships['plc2'][0][0] == 'Maschine_Motion-profinet-S01'
    assert memberships['plc3'][0][0] == 'Maschine_Motion-ethercat-S01'


@pytest.mark.parametrize('device_class', [0, 1, 2])
def test_basic_sensor_interfaces_reparent_without_losing_children(device_class):
    authority = ToolAuthority(f'pytest-class-reparent-{uuid4()}')
    def operation():
        hardware = create_object('HardwareNode', {'name': 'TemperatureProbe', 'device_type': 'SensorController', 'device_class': device_class})
        function = create_object('Function', {'name': 'ObsoleteFunction', 'hardware_node_id': str(hardware['id'])})
        interface = create_object('Interface', {'name': 'TemperaturePort', 'function_id': str(function['id']), 'interface_type': 'CAN_FD'})
        message = create_object('Message', {'name': 'TemperatureFrame', 'interface_id': str(interface['id']),
            'direction': 'tx', 'cycle_ms': 10, 'dlc': 8})
        signal = create_object('Signal', {'name': 'Temperature', 'message_id': str(message['id']),
            'start_bit': 0, 'length_bits': 8, 'byte_order': 'little_endian', 'data_type': 'unsigned',
            'factor': 1, 'offset_value': 0})
        moved = update_object('Interface', str(interface['id']), {'function_id': None,
            'hardware_node_id': str(hardware['id']), 'expected_version': interface['version'], 'actor': 'test'})
        assert moved['function_id'] is None
        assert str(moved['hardware_node_id']) == str(hardware['id'])
        assert str(get_object('Message', str(message['id']))['interface_id']) == str(interface['id'])
        assert str(get_object('Signal', str(signal['id']))['message_id']) == str(message['id'])
        proposal = proposal_service.create('TEST_CLASS_POLICY', [{'object_type':'Function', 'data':{
            'name':'InvalidGeneratedFunction', 'hardware_node_id':str(hardware['id'])}}], 'test')
        assert not proposal_service.validate(proposal['proposal_id'])['validation_result']['valid']
        return {'ok': True}
    result = execute(authority, 'test_reparent', Permission.READ_MODEL, {}, lambda _: operation())
    assert result.success, result.findings
