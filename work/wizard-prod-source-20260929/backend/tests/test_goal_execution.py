"""Goal and resource contracts: physical capacity must never be invented."""
import pytest
from backend.engineering.goal_execution.graph import ModelGraphService
from backend.engineering.goal_execution.ports import inspect_port_decision
from backend.engineering.goal_execution.models import GoalCompletionEvaluator, DesiredEngineeringState, GoalType

def graph_fixture():
    model = {'project_id': 'test', 'hardware': [{'id': 'adas', 'name': 'ADAS', 'device_type': 'ECU'}],
        'hardware-interfaces': [], 'parameters': {'networks': [{'id': 'can', 'name': 'Chassis_CAN', 'technology': 'CAN_FD', 'bitrate': 500000}]}}
    resources = {'CommunicationCapability': [{'id': 'cap', 'hardware_node_ref': 'adas', 'technology': 'CAN_FD',
        'supported': True, 'controller_count': 1, 'max_channels': 1, 'max_ports': 1, 'supported_bitrates': [500000]}],
        'CommunicationController': [{'id': 'ctrl', 'hardware_node_ref': 'adas', 'technology': 'CAN_FD', 'max_channels': 1, 'active_channels': [], 'status': 'ACTIVE'}]}
    return model, resources

def decide(model, resources):
    return inspect_port_decision(ModelGraphService(model, resources), 'adas', 'CAN_FD', 'can')

def test_capability_and_free_controller_requires_explicit_port_decision():
    model, resources = graph_fixture()
    result = decide(model, resources)
    assert result['status'] == 'OPEN'
    assert [o['id'] for o in result['options']] == ['CREATE_AND_CONNECT_PORT']
    assert result['options'][0]['channel_index'] == 1
    assert model['hardware-interfaces'] == []


def test_allocated_channel_without_connector_completes_existing_interface():
    model, resources = graph_fixture()
    model['hardware-interfaces'] = [{'id': 'hni', 'hardware_node_id': 'adas', 'technology': 'CAN_FD',
        'controller_ref': 'ctrl', 'channel_index': 1, 'physical_port_ref': None, 'network_ref': None}]
    decision = decide(model, resources)
    assert decision['options'][0]['hardware_interface_ref'] == 'hni'
    assert decision['options'][0]['channel_index'] == 1
    model['hardware-interfaces'][0]['network_ref'] = 'other-can'
    assert decide(model, resources)['status'] == 'BLOCKED'


def test_simulation_observation_does_not_change_architecture_revision():
    model, resources = graph_fixture()
    initial = ModelGraphService(model, resources)
    derived = {'relation_type': 'SIMULATED_IN', 'source': 'simulation_derived', 'target_type': 'SimulationRun'}
    assert ModelGraphService(model, resources, relations=[derived]).revision == initial.revision
    assert ModelGraphService(model, resources, relations=[{'relation_type': 'CONNECTED_VIA'}]).revision != initial.revision


def test_relation_row_order_cannot_revoke_a_simulation_authorization():
    from copy import deepcopy
    from itertools import permutations
    model, resources = graph_fixture()
    relations = [
        {'id': 'relation-b', 'relation_type': 'CONNECTED_VIA', 'source_id': 'adas', 'target_id': 'can',
         'attributes': {'path': ['source-port', 'target-port']}, 'created_at': '2026-09-14T00:00:00Z'},
        {'id': 'relation-a', 'relation_type': 'RUNS_ON', 'source_id': 'park', 'target_id': 'adas',
         'created_at': '2026-09-14T00:00:00Z'},
        {'id': 'relation-c', 'relation_type': 'CONSUMED_BY', 'source_id': 'status', 'target_id': 'park',
         'created_at': '2026-09-14T00:00:00Z'},
    ]
    initial = ModelGraphService(model, resources, relations=relations).revision
    observed = {'id': 'observation', 'relation_type': 'SIMULATED_IN', 'source': 'simulation_derived',
                'source_id': 'route', 'target_type': 'SimulationRun', 'target_id': 'job'}
    for ordering in permutations(relations):
        assert ModelGraphService(model, resources, relations=ordering).revision == initial
        assert ModelGraphService(model, resources, relations=[observed, *ordering]).revision == initial
    changed = deepcopy(relations)
    changed[0]['attributes']['path'].reverse()
    assert ModelGraphService(model, resources, relations=changed).revision != initial
    changed = deepcopy(relations)
    changed[1]['target_id'] = 'another-controller'
    assert ModelGraphService(model, resources, relations=changed).revision != initial
    assert ModelGraphService(model, resources, relations=relations[:-1]).revision != initial

@pytest.mark.parametrize('missing,code', [('CommunicationCapability', 'COMMUNICATION_CAPABILITY_MISSING'), ('CommunicationController', 'COMMUNICATION_CONTROLLER_MISSING')])
def test_missing_hardware_fact_is_not_inferred(missing, code):
    model, resources = graph_fixture(); resources.pop(missing)
    result = decide(model, resources)
    assert result['status'] == 'BLOCKED'
    assert code in {f['code'] for f in result['findings']}

def test_existing_port_reused_and_occupied_port_not_replugged():
    model, resources = graph_fixture()
    interface = {'id': 'hni', 'hardware_node_id': 'adas', 'technology': 'CAN_FD', 'controller_ref': 'ctrl',
        'channel_index': 1, 'physical_port_ref': 'connector', 'network_ref': 'can'}
    model['hardware-interfaces'] = [interface]
    assert decide(model, resources)['recommended_option'] == 'REUSE'
    interface['network_ref'] = 'other-can'
    result = decide(model, resources)
    assert result['status'] == 'BLOCKED'
    assert {'PORT_ALREADY_CONNECTED', 'HARDWARE_INTERFACE_CAPACITY_EXCEEDED'} <= {f['code'] for f in result['findings']}

def test_global_limit_is_not_bypassed_by_a_second_controller():
    model, resources = graph_fixture()
    resources['CommunicationController'].append({**resources['CommunicationController'][0], 'id': 'ctrl2'})
    assert decide(model, resources)['status'] == 'BLOCKED'

@pytest.mark.parametrize('change', [{'technology': 'Ethernet'}, {'bitrate': 1000000}, {'allow_new_participants': False}, {'max_participants': 0}])
def test_incompatible_network_never_offered(change):
    model, resources = graph_fixture(); model['parameters']['networks'][0].update(change)
    assert decide(model, resources)['options'] == []

def test_navigation_or_tool_success_is_not_completion():
    desired = DesiredEngineeringState(goal='Verbinden', goal_type=GoalType.CONNECT_FUNCTIONS, target_objects=['a', 'b'])
    result = GoalCompletionEvaluator().evaluate(desired, {'tool_success': True, 'opened_view': True})
    assert result['status'] == 'INCOMPLETE'
    assert 'routing_valid' in result['missing_conditions']

def test_function_host_comes_from_model_not_name():
    model, resources = graph_fixture()
    model['functions'] = [{'id': 'park', 'name': 'ParkAssist', 'hardware_node_id': 'adas'}]
    assert ModelGraphService(model, resources).find_host_hardware('park')['id'] == 'adas'

def test_existing_port_without_confirmed_controller_is_not_a_feasible_option():
    model, resources = graph_fixture()
    model['hardware-interfaces'] = [{'id': 'hni', 'hardware_node_id': 'adas', 'technology': 'CAN_FD',
        'controller_ref': 'missing', 'channel_index': 1, 'physical_port_ref': 'connector', 'network_ref': 'can'}]
    result = decide(model, resources)
    assert result['status'] == 'BLOCKED'
    assert not result['options']

def test_second_channel_requires_decision_and_preserves_occupied_port():
    model, resources = graph_fixture()
    resources['CommunicationCapability'][0].update(max_channels=2, max_ports=2)
    resources['CommunicationController'][0]['max_channels'] = 2
    model['hardware-interfaces'] = [{'id': 'hni', 'hardware_node_id': 'adas', 'technology': 'CAN_FD',
        'controller_ref': 'ctrl', 'channel_index': 1, 'physical_port_ref': 'connector', 'network_ref': 'another-network'}]
    result = decide(model, resources)
    assert result['status'] == 'OPEN'
    assert result['recommended_option'] == 'CREATE_AND_CONNECT_PORT'
    assert result['options'][0]['channel_index'] == 2
    assert model['hardware-interfaces'][0]['network_ref'] == 'another-network'

def test_nonexistent_network_and_stale_resource_projection_are_blocked():
    model, resources = graph_fixture()
    graph = ModelGraphService(model, resources)
    result = inspect_port_decision(graph, 'adas', 'CAN_FD', 'missing')
    assert result['status'] == 'BLOCKED'
    assert result['findings'][0]['code'] == 'NETWORK_NOT_FOUND'

def test_simulation_followup_preserves_explicit_scope_and_does_not_replace_fault_request():
    from backend.engineering.goal_execution.followups import simulation_configuration, requested_followups
    assert requested_followups('Verbinde A mit B ohne Simulation') == []
    config = simulation_configuration('Verbinde A mit B und simuliere für 250 ms, Seed 17', {})
    assert config['duration_s'] == 0.25 and config['seed'] == 17
    with pytest.raises(ValueError, match='Szenario'):
        simulation_configuration('Verbinde A mit B und simuliere einen Bus-Ausfall', {})
