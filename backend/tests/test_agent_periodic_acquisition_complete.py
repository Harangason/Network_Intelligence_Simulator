"""Real governed acquisition from explicit synthetic device contracts."""
import asyncio
import json
from copy import deepcopy
from uuid import uuid4

import pytest

from backend.agent_core.api.mcp_client import EngineeringMCPClient
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.runtime.service import EngineeringAssistantService
from backend.engineering.agent_tools import conversation, model, proposal_service
from backend.engineering.agent_tools.runtime import ToolAuthority
from backend.engineering.repository import create_object, update_object
from backend.simulator_engineering_mcp.server import create_server
from backend.tests.test_agent_recipient_repair_runtime import scoped

PROMPT = 'Lege eine ECU an, die mir die Stellgliedpositionen im System alle 30 Sekunden abfragt.'
REQUIREMENTS = {'confirmed': True, 'maximum_event_to_response_ms': 250, 'sampling_delay_ms': 0, 'actuation_delay_ms': 0}
STATUS = {'name': 'DeviceStatus', 'start_bit': 0, 'length_bits': 4, 'byte_order': 'little_endian',
          'data_type': 'unsigned', 'factor': 1, 'offset_value': 0, 'min_value': 0, 'max_value': 15,
          'unit': 'code', 'semantic': {'semantic_type': 'STATE', 'meaning': 'Betriebszustand'},
          'data': {'enum_values': {'OFF': 0, 'INIT': 1, 'READY': 2, 'ACTIVE': 3, 'DEGRADED': 4, 'ERROR': 5},
                   'default_value': 'OFF', 'invalid_values': [15], 'reserved_values': list(range(6, 15))}}
REQUEST = {'name': 'ReadPosition', 'start_bit': 0, 'length_bits': 8, 'byte_order': 'little_endian',
           'data_type': 'unsigned', 'factor': 1, 'offset_value': 0, 'min_value': 1, 'max_value': 1,
           'unit': 'code', 'semantic': {'semantic_type': 'STATE', 'meaning': 'Positionsanfrage'},
           'data': {'enum_values': {'READ_POSITION': 1}}}


def seed():
    from backend.engineering.goal_execution.store import save_resource
    from backend.engineering.workflow.service import WorkflowStatusService
    from backend.engineering.communication_repair import load_plan
    from backend.engineering.communication_contract_repair import scan_signal_recipients
    from backend.engineering.routing.validation import RoutingValidator
    from backend.engineering.routing.repository import create_proposal, accept_proposal_routes, save_validation, approve_routes
    authority = ToolAuthority('complete-acquisition-' + uuid4().hex)
    def create():
        nodes, functions, interfaces, ports = [], [], [], []
        provenance = {'source': 'SCRIPTED_TEST_FIXTURE', 'synthetic': True, 'confirmed': True}
        for name, kind in [('PositionActuator', 'ActuatorController'), ('ExistingController', 'ECU')]:
            node = create_object('HardwareNode', {'name': name, 'device_type': kind, 'device_class': 4, 'provenance': provenance})
            function = create_object('Function', {'name': name + '_Function', 'hardware_node_id': str(node['id'])})
            interface = create_object('Interface', {'name': name + '_CAN_FD', 'function_id': str(function['id']), 'interface_type': 'CAN_FD'})
            controller_id = str(uuid4()); physical_id = str(uuid4())
            save_resource('CommunicationCapability', {'id': str(uuid4()), 'hardware_node_ref': str(node['id']), 'technology': 'CAN_FD',
                'supported': True, 'controller_count': 1, 'max_channels': 1, 'max_ports': 1, 'supported_bitrates': [500000], 'provenance': provenance})
            save_resource('CommunicationController', {'id': controller_id, 'hardware_node_ref': str(node['id']), 'technology': 'CAN_FD',
                'max_channels': 1, 'active_channels': [1], 'provenance': provenance})
            port = create_object('HardwareNetworkInterface', {'name': name + '_Port', 'hardware_node_id': str(node['id']),
                'technology': 'CAN_FD', 'controller_ref': controller_id, 'channel_index': 1, 'network_ref': 'acquisition-can',
                'physical_port_ref': physical_id, 'bitrate': 500000, 'data_bitrate': 2000000})
            save_resource('PhysicalPort', {'id': physical_id, 'hardware_node_ref': str(node['id']), 'controller_ref': controller_id,
                'hardware_interface_ref': str(port['id']), 'technology': 'CAN_FD', 'channel_index': 1, 'network_ref': 'acquisition-can',
                'connection_status': 'CONNECTED', 'provenance': provenance})
            save_resource('NetworkConnection', {'connection_id': str(uuid4()), 'port_ref': physical_id, 'network_ref': 'acquisition-can',
                'technology_binding_ref': str(port['id']), 'created_by': 'SCRIPTED_TEST_FIXTURE', 'provenance': provenance})
            nodes.append(node); functions.append(function); interfaces.append(interface); ports.append(port)
        messages = []
        for i in range(2):
            config = {'maximum_latency_ms': 250, 'communication_contract': {'scope': 'FUNCTION_OUTPUT',
                'consumer_refs': [str(functions[1-i]['id'])], 'transmission': {'mode': 'CYCLIC', 'period_ms': 100,
                    'functional_requirements': REQUIREMENTS}}}
            if i == 0:
                config['request_response_acquisition'] = {'confirmed': True, 'request_frame_id': '0x201',
                    'response_frame_id': '0x202', 'request_signal': REQUEST,
                    'response_processing_ms': 1, 'response_minimum_interval_ms': 100,
                    'functional_requirements': {**REQUIREMENTS, 'maximum_event_to_response_ms': 30250}}
            message = create_object('Message', {'name': 'PositionFeedback' if i == 0 else 'ControllerStatus',
                'interface_id': str(interfaces[i]['id']), 'hardware_interface_id': str(ports[i]['id']),
                'message_id_hex': hex(0x100 + i), 'cycle_ms': 100, 'dlc': 2 if i == 0 else 1, 'direction': 'tx', 'configuration': config})
            messages.append(message)
            create_object('Signal', {**deepcopy(STATUS), 'name': nodes[i]['name'] + 'Status', 'message_id': str(message['id']),
                                    'start_bit': 10 if i == 0 else 0})
        position = create_object('Signal', {'name': 'ActualPosition', 'message_id': str(messages[0]['id']),
            'start_bit': 0, 'length_bits': 10, 'byte_order': 'little_endian', 'data_type': 'unsigned', 'unit': 'mm',
            'factor': 0.1, 'offset_value': 0, 'min_value': 0, 'max_value': 100, 'semantic': {'semantic_type': 'NUMERIC'},
            'configuration': {'physical_quantity': 'position'}})
        update_object('HardwareNode', str(nodes[1]['id']), {'identity': {'acquisition_controller_template': {
            'confirmed': True, 'hardware_interface_ref': str(ports[1]['id']), 'status_cycle_ms': 100,
            'status_consumer_ref': str(functions[1]['id']), 'status_frame_id': '0x220',
            'status_signal': STATUS, 'status_functional_requirements': REQUIREMENTS}}})
        workflow = WorkflowStatusService(authority.project_id)
        workflow.save_parameters({'industry': 'industrial_automation', 'technology': 'can_fd', 'bitrate': 500000,
            'data_bitrate': 2000000, 'cycle_ms': 100, 'payload_bytes': 2,
            'formats': ['universal-jsonl'], 'queue_size': 256,
            'warning_threshold': 60, 'critical_threshold': 75, 'overload_threshold': 90,
            'target_bus_load_percent': 60,
            'networks': [{'id': 'acquisition-can', 'name': 'Acquisition_CAN', 'technology': 'CAN_FD',
                          'bitrate': 500000, 'data_bitrate': 2000000}]}, actor='SCRIPTED_TEST_FIXTURE')
        topology = {'nodes': [{'id': 'node-' + str(i), 'engineeringId': str(n['id']), 'name': n['name'], 'kind': 'ecu',
            'ports': [{'id': 'drawing-' + str(i), 'hardwareInterfaceId': str(ports[i]['id']), 'bus': 'CAN_FD',
                       'physicalNetworkId': 'acquisition-can'}]} for i, n in enumerate(nodes)],
            'edges': [{'id': 'confirmed-wire', 'source': 'node-0', 'target': 'node-1', 'sourcePort': 'drawing-0',
                      'targetPort': 'drawing-1', 'bus': 'CAN_FD', 'physicalNetworkId': 'acquisition-can',
                      'engineeringSegmentId': 'confirmed-wire', 'origin': 'CANONICAL_BUS_BINDING'}]}
        workflow.save_topology(topology, actor='SCRIPTED_TEST_FIXTURE')
        planner, _ = load_plan(); routes = scan_signal_recipients(planner, RoutingValidator().validate)['changes']
        assert len(routes) == 2
        for change in routes:
            draft = create_proposal({'prompt': 'Explicit fixture routing', 'generated_routes': [change['data']], 'actor': 'SCRIPTED_TEST_FIXTURE'})
            route = accept_proposal_routes(str(draft['proposal_id']), [0], actor='SCRIPTED_TEST_FIXTURE')[0]
            save_validation(str(route['id']), RoutingValidator().validate(route, exclude_route_id=str(route['id'])), actor='SCRIPTED_TEST_FIXTURE')
            approve_routes([str(route['id'])], actor='SCRIPTED_TEST_FIXTURE')
            for edge in topology['edges']:
                if any(edge['id'] in path.get('edges', []) for path in route['route'].get('physical_paths', [])):
                    edge.setdefault('routingEntryIds', []).append(str(route['id']))
        workflow.save_topology(topology, actor='SCRIPTED_TEST_FIXTURE')
        return {'actuator': str(nodes[0]['id']), 'controller': str(nodes[1]['id']), 'position': str(position['id']),
                'position_message': str(messages[0]['id']), 'controller_port': str(ports[1]['id'])}
    return authority, scoped(authority, create)


def invoke(authority):
    context = AgentContext(active_project_id=authority.project_id)
    started = scoped(authority, lambda: conversation.begin(PROMPT, context)); run_id = started['run_id']
    class NoReasoner:
        async def next(self, *args): raise AssertionError('Explicit model contracts must use canonical acquisition planning.')
    async def run():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAssistantService(client, reasoner=NoReasoner(),
                persist=lambda w: scoped(authority, lambda: conversation.save_runtime_workload(run_id, w))).execute(
                    PROMPT, AgentContext.model_validate(started['context']), saved_state=scoped(authority, conversation.read),
                    emit=lambda e: scoped(authority, lambda: conversation.record_event(run_id, e)) if e.get('id') else None)
    result = asyncio.run(run()); scoped(authority, lambda: conversation.finish(run_id)); return result


def test_original_acquisition_proposes_and_applies_complete_atomic_model():
    authority, ids = seed(); before = scoped(authority, model.model)
    result = invoke(authority)
    assert result['runtime']['status'] == 'READY_FOR_REVIEW', json.dumps(result['events'], ensure_ascii=True)
    proposal = result['proposals'][0]
    assert proposal['proposal_type'] == 'PERIODIC_ACQUISITION' and proposal['status'] == 'VALIDATED', proposal
    assert scoped(authority, model.model) == before
    assert len([c for c in proposal['changes'] if c['object_type'] == 'RoutingEntry']) == 3
    def apply():
        proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='human-test', trace_id=uuid4().hex)
        applied = proposal_service.apply(proposal['proposal_id'], actor='human-test', trace_id=uuid4().hex)
        assert conversation.reconcile_runtime_model_apply(applied)
        return applied
    applied = scoped(authority, apply); after = scoped(authority, model.model)
    assert len(after['hardware']) == len(before['hardware']) + 1
    assert len(after['routing']) == len(before['routing']) + 3
    for key in ['hardware', 'functions', 'interfaces', 'hardware-interfaces', 'messages', 'signals']:
        assert all(old == next(row for row in after[key] if row['id'] == old['id']) for old in before[key]), key
    work = scoped(authority, conversation.read)['engineering_workloads'][result['runtime']['workload_id']]
    if work['status'] != 'COMPLETED':
        from backend.engineering.db import get_connection
        def details():
            with get_connection() as connection:
                return model.json_safe(connection.execute('SELECT analysis_type,status,findings,results FROM engineering_analysis_snapshots WHERE project_id=%s', (authority.project_id,)).fetchall())
        assert work['status'] == 'COMPLETED', json.dumps({'completion': work['result']['completion'], 'snapshots': scoped(authority, details)}, ensure_ascii=True)
    assert work['result']['periodic_acquisition']['period_ms'] == 30000
    assert work['result']['periodic_acquisition']['source_signal_ids'] == [ids['position']]
    scoped(authority, lambda: proposal_service.apply(applied['proposal_id'], actor='human-test', trace_id=uuid4().hex))
    assert scoped(authority, model.model) == after
    from backend.engineering.simulation import prepare_workflow_simulation_config
    from hardware_profile import normalize_hardware_config
    from universal_trace import generate_universal_events
    config = scoped(authority, lambda: prepare_workflow_simulation_config(
        {'duration_s': 61, 'max_events': 20000, 'seed': 42, 'scenario': {'mode': 'NORMAL'}}, authority.project_id))
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1700000000)
    request_id = next(row['id'] for row in after['messages']
        if (row.get('configuration') or {}).get('generation_role') == 'ACQUISITION_REQUEST')
    response_id = next(row['id'] for row in after['messages']
        if (row.get('configuration') or {}).get('generation_role') == 'ACQUISITION_RESPONSE')
    requests = [row for row in events if request_id in row.get('message_ids', [])]
    responses = [row for row in events if response_id in row.get('message_ids', [])]
    assert len(requests) >= 2 and len(responses) >= 2
    assert requests[1]['origin_scheduled_time_s'] - requests[0]['origin_scheduled_time_s'] == 30
    for reply in responses:
        request = next(row for row in requests if row['event_id'] == reply['caused_by_event_id'])
        assert reply['transaction_id'] == request['transaction_id']
        assert reply['scheduled_time_s'] >= request['time_s'] + .001 - 1e-9
        assert reply['signals']
    assert scoped(authority, model.model) == after


@pytest.mark.parametrize('field,value', [('response_processing_ms', None), ('response_processing_ms', -1),
    ('response_minimum_interval_ms', 0), ('response_minimum_interval_ms', 40000), ('confirmed', False)])
def test_unconfirmed_or_invalid_exchange_never_proposes_complete_acquisition(field, value):
    authority, ids = seed()
    def alter():
        message = next(row for row in model.objects('Message') if row['id'] == ids['position_message'])
        config = deepcopy(message['configuration']); config['request_response_acquisition'][field] = value
        update_object('Message', ids['position_message'], {'configuration': config})
    scoped(authority, alter); before = scoped(authority, model.model)
    result = invoke(authority)
    assert not result['proposals']
    assert result['runtime']['status'] != 'COMPLETED'
    assert scoped(authority, model.model) == before


@pytest.mark.parametrize('prompt', ['Bitte nicht: ' + PROMPT, PROMPT + ' Lösche dann alle anderen ECUs.',
                                  'Erkläre, wie man Stellgliedpositionen alle 30 Sekunden abfragt.'])
def test_complete_planner_does_not_expand_ambiguous_or_negative_intent(prompt):
    from backend.engineering.agent_tools.periodic_acquisition import prepare
    authority, _ = seed(); result = invoke(authority)
    def check():
        state = conversation.read(); work = state['engineering_workloads'][result['runtime']['workload_id']]
        work['goal']['original_request'] = prompt; conversation.write(state)
        before = model.model()
        outcome = prepare({'workload_id': work['goal']['goal_id']})
        assert outcome['proposal'] is None
        assert outcome['findings'][0]['code'] == 'ACQUISITION_INTENT_AMBIGUOUS'
        assert model.model() == before
    scoped(authority, check)


def test_preview_rejects_response_pointing_to_an_unrelated_existing_message():
    from backend.engineering.agent_tools.periodic_acquisition import validate_preview
    from backend.engineering.models import EngineeringValidationError
    authority, ids = seed(); result = invoke(authority)
    changes = deepcopy(result['proposals'][0]['changes'])
    response = next(change for change in changes if change['local_ref'] == 'response-0')
    response['data']['configuration']['communication_contract']['transmission']['request_message_ref'] = ids['position_message']
    def rejected():
        with pytest.raises(EngineeringValidationError, match='Endpunkten'):
            validate_preview(changes)
    scoped(authority, rejected)
