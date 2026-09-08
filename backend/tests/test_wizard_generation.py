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
import pytest


def test_semantic_network_assignment_keeps_powertrain_on_one_named_can():
    motor = {'name': 'Motorsteuerung', 'device_type': 'ECU'}
    fuel = {'name': 'Kraftstoffsystem', 'device_type': 'ECU'}
    brake = {'name': 'Bremsensteuerung', 'device_type': 'ECU'}

    assert wizard_generation._semantic_physical_network('can_fd', motor, fuel) == (
        'antriebsstrang-can-fd-bus', 'Antriebsstrang-CAN')
    assert wizard_generation._semantic_physical_network('can_fd', motor, fuel) != (
        wizard_generation._semantic_physical_network('can_fd', brake, brake)
    )


def test_combined_wizard_creates_validated_model_without_reasoner(monkeypatch):
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

    canonical_hardware = execute(authority, 'test_route_nodes', Permission.READ_MODEL, {}, lambda _: model.objects('HardwareNode')).data
    interfaces = execute(authority, 'test_route_interfaces', Permission.READ_MODEL, {}, lambda _: model.objects('Interface')).data
    interface_by_node = {str(item.get('hardware_node_id')): item.get('interface_type') for item in interfaces}
    available_sensor_types = {interface_by_node[str(item['id'])] for item in canonical_hardware if item['device_type'] == 'SensorController'}
    available_actuator_types = {interface_by_node[str(item['id'])] for item in canonical_hardware if item['device_type'] == 'ActuatorController'}
    ecu = next(item for item in canonical_hardware if item['device_type'] == 'ECU' and interface_by_node[str(item['id'])] in available_sensor_types & available_actuator_types)
    ecu_type = interface_by_node[str(ecu['id'])]
    sensor = next(item for item in canonical_hardware if item['device_type'] == 'SensorController' and interface_by_node[str(item['id'])] == ecu_type)
    actuator = next(item for item in canonical_hardware if item['device_type'] == 'ActuatorController' and interface_by_node[str(item['id'])] == ecu_type)
    hmi = next(item for item in canonical_hardware if item['device_type'] == 'ECU' and interface_by_node[str(item['id'])] != ecu_type)
    graph = json.dumps([{'cluster_id': 'test', 'controllers': [{
        'ecu': ecu['name'], 'sensors': [sensor['name']], 'actuators': [actuator['name']]}],
        'hmi_routes': [{'source': ecu['name'], 'target': hmi['name']}]}], separators=(',', ':'))
    continuation_prompt = prompt + f'\n- Systemcluster-Graph: {graph}\nFortsetzung des bestätigten Wizard-Auftrags: Ziel: routing.'
    async def route_continuation():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAgent(client, reasoner=NoReasoner()).run(
                continuation_prompt, AgentContext(active_project_id=authority.project_id))
    routed = asyncio.run(route_continuation())
    assert routed['status'] == 'READY_FOR_REVIEW', routed.get('proposals', [{}])[0].get('validation_result', routed)
    routing_proposal = routed['proposals'][0]
    assert routing_proposal['proposal_type'] == 'WIZARD_ROUTING'
    assert routing_proposal['status'] == 'VALIDATED'
    assert len(routing_proposal['changes']) == 3
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
    assert routing_check['complete'], routing_check

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
    topology = network_proposal['changes'][0]['data']['topology']
    assert len(topology['nodes']) == len(canonical_hardware)
    assert len(topology['edges']) >= 3
    assert all(node['engineeringId'] for node in topology['nodes'])
    assert all(edge['engineeringRelationId'] for edge in topology['edges'])
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
    topology_conversation = conversation.read()
    topology_conversation.update(active_proposal=network_proposal['proposal_id'], current_requirement=network_prompt)
    conversation.write(topology_conversation)
    WorkflowStatusService(authority.project_id).set_context({'agent_execution': {
        'run_id': 'test-wizard-12345678', 'state': 'REVIEW_REQUIRED', 'step': 'network_editor',
        'completed': 1, 'total': 1}})
    topology_status = execute(authority, 'test_topology_apply_status', Permission.READ_MODEL, {}, lambda _: (
        reconcile_model_apply(authority.project_id, topology_applied.data),
        WorkflowStatusService(authority.project_id).get(summary=True)['context']['agent_execution'],
    )[1])
    assert topology_status.success and topology_status.data['state'] == 'READY_TO_CONTINUE', topology_status
    assert topology_status.data['step'] == 'capacity_timing', topology_status

    # A partial parameter draft used to send this continuation to the LLM and
    # leave the wizard blocked without a canonical change.
    WorkflowStatusService(authority.project_id).save_parameters(
        {'target_bus_load_percent': 60}, actor='test-human'
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
    capacity_status = WorkflowStatusService(authority.project_id).get(summary=True)['statuses']['capacity_timing']
    assert capacity_status in {'COMPLETE', 'WARNING'}, capacity_status
    capacity_snapshot = WorkflowStatusService(authority.project_id).latest_analysis('capacity_timing')
    assert capacity_snapshot['results']['overview']['route_count'] == 3
    assert capacity_snapshot['results']['overview']['network_count'] >= 1

    preflight_result = asyncio.run(network_continuation())
    assert preflight_result['status'] == 'READY_TO_CONTINUE', preflight_result
    assert [item['tool'] for item in preflight_result['trace']].count('calculate_capacity') == 0
    assert any(item['tool'] == 'validate_simulation_preflight' for item in preflight_result['trace'])
    assert 'kein prüfbarer Änderungs- oder Workload-Aufruf' not in preflight_result['text']
    assert WorkflowStatusService(authority.project_id).get(summary=True)['statuses']['validation'] == 'APPROVED'

    from backend.engineering.agent_tools import simulation_gateway
    simulation_job_id = 'test-wizard-simulation-job'
    def start_simulation(snapshot_id):
        WorkflowStatusService(authority.project_id).update_simulation_snapshot(
            snapshot_id,
            status='COMPLETED',
            job_id=simulation_job_id,
            result={
                'runtime_metrics': {'network_count': 1, 'event_count': 3},
                'trace': {'event_count': 3},
                'hardware_validation': {'valid': True},
                'warnings': [],
            },
        )
        return {'id': simulation_job_id, 'status': 'completed'}
    monkeypatch.setattr(simulation_gateway, 'start', start_simulation)
    monkeypatch.setattr(simulation_gateway, 'job', lambda job_id: {
        'id': job_id, 'status': 'completed', 'result': {'runtime_metrics': {'event_count': 3}},
    })

    simulation_result = asyncio.run(network_continuation())
    assert simulation_result['status'] == 'READY_TO_CONTINUE', simulation_result
    simulation_tools = [item['tool'] for item in simulation_result['trace']]
    assert 'create_simulation_snapshot' in simulation_tools
    assert 'start_simulation' in simulation_tools
    assert 'get_simulation_status' in simulation_tools
    assert 'kein prüfbarer Änderungs- oder Workload-Aufruf' not in simulation_result['text']
    workflow_after_simulation = WorkflowStatusService(authority.project_id).get(summary=True)
    assert workflow_after_simulation['statuses']['simulation'] == 'COMPLETE'
    assert workflow_after_simulation['statuses']['results_analysis'] == 'COMPLETE'


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
