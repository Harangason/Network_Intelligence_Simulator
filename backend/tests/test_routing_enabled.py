"""Forwarding switches preserve local wire traffic and complete physical frames."""
from copy import deepcopy

import pytest

from backend.engineering.models import EngineeringValidationError
from backend.engineering.routing.payload_scope import payload_scope_issues


def message(*, enabled=True, local=False):
    return {'id': 'frame', 'name': 'Motor frame', 'dlc': 8, 'cycle_ms': 20,
            'configuration': {'routing': {'enabled': enabled}, 'communication_contract': {
                'scope': 'LOCAL_IO' if local else 'FUNCTION_OUTPUT', 'consumer_refs': ['motor']}}}


def signal(identifier, enabled):
    return {'id': identifier, 'name': identifier, 'message_id': 'frame', 'start_bit': 0,
            'length_bits': 1, 'configuration': {'routing': {'enabled': enabled}}}


def route(destination='display', payload=None):
    return {'source': {'node_id': 'hall'}, 'payload': payload or {'message_ids': ['frame']},
            'destinations': [{'node_id': destination}]}


@pytest.mark.parametrize('message_enabled,signal_enabled', [(False, True), (True, False), (False, False)])
def test_off_preserves_confirmed_local_io_but_blocks_external_forwarding(message_enabled, signal_enabled):
    messages = {'frame': message(enabled=message_enabled, local=True)}
    signals = {'hall-position': signal('hall-position', signal_enabled)}
    before = deepcopy((messages, signals))
    assert not payload_scope_issues(route('motor'), messages, signals)
    issues = payload_scope_issues(route('display'), messages, signals)
    assert issues[0]['code'] == ('SIGNAL_ROUTING_DISABLED' if message_enabled else 'MESSAGE_ROUTING_DISABLED')
    assert (messages, signals) == before  # No DLC, encoding or ownership rewrite.


def test_on_does_not_grant_local_measurements_a_new_function_consumer():
    issues = payload_scope_issues(route(), {'frame': message(local=True)}, {'hall': signal('hall', True)})
    assert [issue['code'] for issue in issues] == ['LOCAL_IO_RECIPIENT_MISMATCH']


@pytest.mark.parametrize('payload', [{'message_ids': ['frame']}, {'message_id': 'frame'},
    {'message_ids': ['frame'], 'signal_ids': ['status']}, {'signal_ids': ['status']}])
def test_unselected_off_signal_still_blocks_the_whole_original_frame(payload):
    messages = {'frame': message()}
    signals = {'hall': signal('hall', False), 'status': signal('status', True)}
    issues = payload_scope_issues(route(payload=payload), messages, signals)
    assert [issue['code'] for issue in issues] == ['SIGNAL_ROUTING_DISABLED']
    assert issues[0]['signal_ids'] == ['hall']
    assert messages['frame']['dlc'] == 8


def test_separate_explicit_output_frame_remains_routable():
    messages = {'frame': message(), 'output': {**message(), 'id': 'output', 'dlc': 1}}
    signals = {'hall': signal('hall', False), 'output-status': {**signal('output-status', True), 'message_id': 'output'}}
    assert not payload_scope_issues(route(payload={'message_ids': ['output']}), messages, signals)
    assert messages['frame']['dlc'] == 8 and messages['output']['dlc'] == 1


def test_off_does_not_reinterpret_existing_global_consumers_as_local():
    messages = {'frame': message(enabled=False)}
    assert payload_scope_issues(route('motor'), messages)[0]['code'] == 'MESSAGE_ROUTING_DISABLED'


@pytest.mark.parametrize('local', [False, True])
def test_payload_suggestion_scope_exposes_effective_frame_switch_and_keeps_local_receivers(local):
    from backend.engineering.routing.payload_scope import message_scope, scope_allows
    scope = message_scope(message(local=local), {'hall': signal('hall', False), 'status': signal('status', True)})
    assert scope['routing_enabled'] is True  # The message's own editable switch.
    assert scope['forwarding_enabled'] is False and scope['restricted'] is True
    assert scope['blocked_signal_ids'] == ['hall']
    assert scope_allows(scope, {'node_id': 'motor'}) is local
    assert not scope_allows(scope, {'node_id': 'display'})


def test_approved_simulation_rechecks_hidden_disabled_fields(monkeypatch):
    from backend.engineering.routing import payload_scope, config_builder
    monkeypatch.setattr(payload_scope, 'load_payload_context', lambda: (
        {'frame': message()}, {'hall': signal('hall', False), 'status': signal('status', True)}, {}))
    approved = {**route(payload={'message_id': 'frame', 'signal_ids': ['status']}), 'approval_state': 'APPROVED'}
    with pytest.raises(EngineeringValidationError, match='hall'):
        config_builder.CommunicationConfigBuilder().build([approved])


@pytest.mark.parametrize('kind', ['Message', 'Signal'])
@pytest.mark.parametrize('value', ['false', 0, 1, None, [], {}])
def test_routing_switch_accepts_only_actual_boolean_values(kind, value):
    from backend.engineering.repository import get_spec
    with pytest.raises(EngineeringValidationError, match='true oder false'):
        get_spec(kind).validate({'interface_id': 'i', 'message_id': 'm', 'configuration': {'routing': {'enabled': value}}})


def test_wizard_replanning_keeps_saved_forwarding_choice():
    from backend.tests.test_wizard_communication import fixture
    from backend.engineering.wizard_communication import communication_plan
    prompt, graph = fixture()
    first = communication_plan(prompt, graph)
    first['sensor']['routing'] = {'enabled': False}
    for key, config in first.items():
        graph['Message'][key]['configuration'] = config
    assert communication_plan(prompt, graph) == first


@pytest.mark.parametrize('switch_kind', ['Message', 'Signal'])
def test_wizard_generation_keeps_local_routes_and_omits_switched_off_global_consumers(monkeypatch, switch_kind):
    from backend.tests.test_wizard_communication import fixture
    from backend.engineering.wizard_communication import communication_plan
    from backend.engineering.agent_tools import wizard_generation as generation
    prompt, graph = fixture()
    for key, config in communication_plan(prompt, graph).items():
        graph['Message'][key]['configuration'] = config
    graph['Message']['sensor']['configuration']['routing'] = {'enabled': False}
    if switch_kind == 'Message':
        graph['Message']['ecu']['configuration']['routing'] = {'enabled': False}
    else:
        # The communication fixture disables ECU forwarding by default.
        # Enable the frame here so this variant isolates the signal switch.
        graph['Message']['ecu']['configuration']['routing'] = {'enabled': True}
        graph['Signal'] = {'private': {'name': 'PrivateState', 'message_id': 'ecu',
                                     'configuration': {'routing': {'enabled': False}}}}
    monkeypatch.setattr(generation.model, 'objects', lambda kind: [{**row, 'id': key} for key, row in graph.get(kind, {}).items()])
    monkeypatch.setattr(generation.model, 'routes', lambda: [])
    monkeypatch.setattr(generation.proposal_store, 'list_proposals', lambda **_: [])
    captured, calls = {}, []
    def create(kind, changes, rationale, **metadata):
        captured.update(changes=changes, metadata=metadata)
        return captured
    monkeypatch.setattr(generation.proposal_service, 'create', create)
    class Routes:
        def _hardware_graph(self):
            return {}, {}
        def generate_route(self, *, source_node_id, destination_node_id, message_id):
            calls.append((source_node_id, destination_node_id, message_id))
            return {'source': {'protocol': 'CAN_FD'}, 'destinations': [{'protocol': 'CAN_FD'}]}
    monkeypatch.setattr(generation, 'RoutingGenerationService', Routes)
    generation.generate_routing({'prompt': prompt})
    assert ('sensor', 'ecu', 'sensor') in calls
    assert ('actuator', 'ecu', 'actuator') in calls
    assert not any(mid == 'ecu' for _, _, mid in calls)
    excluded = captured['metadata']['evidence'][0]['excluded_forwarding']
    assert excluded and all(issue['message_id'] == 'ecu' for issue in excluded)
    assert {issue['code'] for issue in excluded} == {('MESSAGE_ROUTING_DISABLED' if switch_kind == 'Message' else 'SIGNAL_ROUTING_DISABLED')}


def test_repair_does_not_restore_forwarding_of_a_disabled_field():
    from backend.tests.test_communication_repair import sample
    from backend.engineering.communication_repair import RepairPlanner, complete_plan
    state, objects, routes, history = sample()
    objects['Signal'][0]['configuration'] = {'routing': {'enabled': False}}
    before = deepcopy((objects, routes))
    plan = complete_plan(RepairPlanner(state, objects, routes, history))
    group = plan['groups'][0]
    assert group['status'] == 'BLOCKED' and not group['options']
    assert 'Geroutet ist ausgeschaltet' in group['reason']
    assert (objects, routes) == before


def test_off_keeps_local_bus_load_and_timing_but_removes_external_frame_load(monkeypatch):
    from backend.engineering.capacity import service as capacity
    from backend.engineering.workflow.models import default_statuses, default_versions
    local = message(enabled=False, local=True)
    output = {**message(), 'id': 'output', 'dlc': 1}
    def capacity_route(identifier, mid, target, network, protocol):
        return {'id': identifier, 'name': identifier, 'approval_state': 'APPROVED', 'status': 'APPROVED',
            'source': {'node_id': 'hall' if mid == 'frame' else 'motor', 'network_id': network, 'protocol': protocol},
            'destinations': [{'node_id': target, 'network_id': network, 'protocol': protocol}],
            'payload': {'message_id': mid}, 'route': {'gateways': []}, 'timing': {'cycle_time_ms': 20}}
    rows = [capacity_route('local', 'frame', 'motor', 'motor-lin', 'LIN'),
            capacity_route('output', 'output', 'display', 'system-can', 'CAN_FD')]
    objects = {'Message': [local, output], 'Signal': [signal('hall', False)], 'HardwareNode': [
        {'id': 'motor', 'name': 'Motor', 'device_type': 'ECU'}]}
    monkeypatch.setattr(capacity, 'list_objects', lambda kind, **kwargs: deepcopy(objects.get(kind, [])))
    monkeypatch.setattr(capacity, 'list_routes', lambda **kwargs: deepcopy(rows))
    service = capacity.CapacityTimingService('routing-off-test')
    monkeypatch.setattr(service.workflow, 'get', lambda: {'project_id': 'routing-off-test', 'versions': default_versions(),
        'statuses': {key: 'COMPLETE' for key in default_statuses()}, 'parameters': {'technology': 'can_fd', 'bitrate': 500_000, 'data_bitrate': 2_000_000, 'networks': [{'id': 'motor-lin', 'bitrate': 19_200}, {'id': 'system-can', 'bitrate': 500_000, 'data_bitrate': 2_000_000}]}, 'topology': {}})
    monkeypatch.setattr(service, 'latest', lambda: None)
    before = service.calculate(persist=False)
    rows.append(capacity_route('forbidden', 'frame', 'display', 'system-can', 'CAN_FD'))
    after = service.calculate(persist=False)
    assert before['results']['networks'] == after['results']['networks']
    assert before['results']['routes'] == after['results']['routes']
    local_metric = next(item for item in after['results']['routes'] if item['route_id'] == 'local')
    assert local_metric['average_load_percent'] > 0 and local_metric['transmission_latency_ms'] > 0
    assert local_metric['payload_bytes'] == 8 and local_metric['cycle_ms'] == 20
    assert {item['route_id'] for item in after['results']['routes']} == {'local', 'output'}
    assert any(item['code'] == 'MESSAGE_ROUTING_DISABLED' and item['excluded_from_load'] for item in after['findings'])


@pytest.fixture
def request_unit():
    from backend.engineering.db import RequestUnit
    from backend.engineering.project_context import current_project_id
    unit = RequestUnit(current_project_id())
    try:
        yield unit
    finally:
        unit.close()


def test_canonical_sql_message_only_route_cannot_hide_off_signal_and_revision_is_checked(request_unit):
    from backend.engineering.repository import create_object, update_object, get_object
    from backend.engineering.routing.validation import RoutingValidator
    from backend.engineering.project_context import current_project_id
    from backend.engineering.workflow.service import WorkflowStatusService
    from backend.engineering.db import flush_model_changes
    from backend.engineering.db import ConcurrentUpdateError
    src = create_object('HardwareNode', {'name': 'DriveUnit', 'device_type': 'ECU'})
    dst = create_object('HardwareNode', {'name': 'DisplayUnit', 'device_type': 'ECU'})
    interfaces = [create_object('Interface', {'name': node['name'] + 'Output', 'hardware_node_id': str(node['id']),
        'interface_type': 'CAN_FD'}) for node in (src, dst)]
    frame = create_object('Message', {'name': 'DriveData', 'interface_id': str(interfaces[0]['id']), 'dlc': 8,
        'cycle_ms': 20, 'message_id_hex': '0x120', 'configuration': {'routing': {'enabled': True}}})
    hidden = create_object('Signal', {'name': 'HallInternal', 'message_id': str(frame['id']), 'start_bit': 0,
        'length_bits': 16, 'factor': 0.01, 'configuration': {'routing': {'enabled': True}}})
    visible = create_object('Signal', {'name': 'DriveReady', 'message_id': str(frame['id']), 'start_bit': 16,
        'length_bits': 1})
    flush_model_changes(actor='test', reason='Create forwarding fixture')
    workflow = WorkflowStatusService(current_project_id())
    before = workflow.get()['versions']['engineering_model']
    saved = update_object('Signal', str(hidden['id']), {'expected_version': hidden['version'],
        'configuration': {'routing': {'enabled': False}}})
    flush_model_changes(actor='test', reason='Disable external forwarding')
    assert saved['version'] == hidden['version'] + 1
    assert get_object('Signal', str(hidden['id']))['configuration']['routing']['enabled'] is False
    assert workflow.get()['versions']['engineering_model'] > before
    assert get_object('Message', str(frame['id']))['dlc'] == 8
    with pytest.raises(ConcurrentUpdateError):
        update_object('Signal', str(hidden['id']), {'expected_version': hidden['version'],
            'configuration': {'routing': {'enabled': True}}})
    validator = RoutingValidator()
    for payload in ({'message_ids': [str(frame['id'])]}, {'signal_ids': [str(visible['id'])]}):
        result = validator.validate({'source': {'node_id': str(src['id']), 'interface_id': str(interfaces[0]['id']), 'protocol': 'CAN_FD'},
            'destinations': [{'node_id': str(dst['id']), 'interface_id': str(interfaces[1]['id']), 'protocol': 'CAN_FD'}], 'payload': payload})
        assert 'SIGNAL_ROUTING_DISABLED' in {issue['code'] for issue in result['errors']}


def test_http_edit_scope_roundtrip_and_project_isolation():
    from backend.tests.test_engineering_api import _client
    client = _client()
    def create(resource, **data):
        response = client.post('/api/engineering/' + resource, json=data)
        assert response.status_code == 201, response.get_json()
        return response.get_json()
    node = create('hardware-nodes', name='Motor', device_type='ECU')
    interface = create('interfaces', name='DriveOutput', hardware_node_id=node['id'], interface_type='CAN_FD')
    frame = create('messages', name='DriveFrame', interface_id=interface['id'], dlc=8,
                   configuration={'routing': {'enabled': True}})
    field = create('signals', name='PrivateHall', message_id=frame['id'], start_bit=0, length_bits=16,
                   configuration={'routing': {'enabled': True}})
    path = '/api/engineering/signals/' + field['id']
    response = client.patch(path, json={'expected_version': field['version'], 'configuration': {'routing': {'enabled': False}}})
    assert response.status_code == 200, response.get_json()
    saved = response.get_json()
    assert client.get(path).get_json()['configuration']['routing']['enabled'] is False
    scope = client.get('/api/engineering/routing/message-scopes').get_json()['items'][frame['id']]
    assert scope['routing_enabled'] is True and scope['forwarding_enabled'] is False
    assert scope['blocked_signal_ids'] == [field['id']] and scope['restricted'] is True
    assert client.patch(path, json={'expected_version': saved['version'],
        'configuration': {'routing': {'enabled': 'false'}}}).status_code == 400
    assert client.get(path).get_json()['version'] == saved['version']
    foreign = client.get('/api/engineering/routing/message-scopes', headers={'X-Project-ID': 'pytest-foreign-routing-scope'})
    assert foreign.status_code == 200 and foreign.get_json()['items'] == {}
    assert client.get('/api/engineering/messages/' + frame['id']).get_json()['dlc'] == 8


@pytest.mark.parametrize('kind', ['Message', 'Signal'])
def test_goal_planner_does_not_offer_an_externally_disabled_payload(request_unit, kind):
    from backend.tests.test_goal_execution_sql import fixture, prepare
    from backend.engineering.repository import update_object
    data = fixture()
    row = data['message' if kind == 'Message' else 'signal']
    update_object(kind, str(row['id']), {'expected_version': row['version'],
        'configuration': {**row['configuration'], 'routing': {'enabled': False}}})
    goal = prepare(data)
    assert goal['status'] == 'BLOCKED' and not goal['strategies']
    assert goal['findings'][0]['code'] == 'PAYLOAD_DATA_GAP'
