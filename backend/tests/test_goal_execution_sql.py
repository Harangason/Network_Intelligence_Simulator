"""Canonical SQL integration. Refuses to run against a product database."""
import os
from uuid import uuid4
import pytest

# conftest validates the explicit DSN before importing this module. Disposable
# test databases have unique names, so do not silently skip their integration.
pytestmark = pytest.mark.skipif(not os.environ.get('ENGINEERING_TEST_DATABASE_URL'), reason='isolated verification database required')

@pytest.fixture
def project():
    from backend.engineering.project_context import activate_project, reset_project
    from backend.engineering.db import RequestUnit
    project = 'goal-verification-' + uuid4().hex
    token = activate_project(project); unit = RequestUnit(project)
    try:
        yield project
        unit.finish(False)
    finally:
        unit.close(); reset_project(token)

def fixture():
    from backend.engineering.repository import create_object
    from backend.engineering.workflow.service import WorkflowStatusService
    from backend.engineering.project_context import current_project_id
    from backend.engineering.goal_execution.store import save_resource
    from backend.engineering.agent_tools.model import json_safe
    def obj(kind, **data): return json_safe(create_object(kind, data))
    src = obj('HardwareNode', name='ChassisController', device_type='ECU')
    dst = obj('HardwareNode', name='ADAS_Controller', device_type='ECU')
    sf = obj('Function', name='ParkAssist', hardware_node_id=src['id'])
    df = obj('Function', name='DriverAssistance', hardware_node_id=dst['id'])
    si = obj('Interface', name='ParkAssistOutput', function_id=sf['id'], interface_type='CAN_FD')
    di = obj('Interface', name='DriverAssistanceEthernet', function_id=df['id'], interface_type='Ethernet')
    for h in (src, dst):
        save_resource('CommunicationCapability', {'id': 'cap-' + h['id'], 'hardware_node_ref': h['id'], 'technology': 'CAN_FD',
            'supported': True, 'controller_count': 1, 'max_channels': 1, 'max_ports': 1, 'supported_bitrates': [500000]})
        save_resource('CommunicationController', {'id': 'controller-' + h['id'], 'hardware_node_ref': h['id'], 'technology': 'CAN_FD', 'max_channels': 1})
    sp = obj('HardwareNetworkInterface', name='Chassis_CAN', hardware_node_id=src['id'], technology='CAN_FD',
        controller_ref='controller-' + src['id'], channel_index=1, physical_port_ref='connector-' + src['id'],
        network_ref='chassis-can', bitrate=500000, data_bitrate=2000000)
    message = obj('Message', name='ParkAssistStatus', interface_id=si['id'], hardware_interface_id=sp['id'],
        message_id_hex='0x120', cycle_ms=100, dlc=1, direction='tx',
        configuration={'maximum_latency_ms': 20, 'maximum_jitter_ms': 5,
            'communication_contract': {'scope': 'FUNCTION_OUTPUT', 'consumer_refs': [df['id']],
                'transmission': {'mode': 'CYCLIC', 'period_ms': 100, 'functional_requirements': {
                    'confirmed': True, 'maximum_event_to_response_ms': 250, 'sampling_delay_ms': 0, 'actuation_delay_ms': 0}}}})
    signal = obj('Signal', name='ParkAssistActive', message_id=message['id'], start_bit=0, length_bits=1,
        byte_order='little_endian', data_type='boolean', factor=1, offset_value=0, min_value=0, max_value=1,
        semantic={'semantic_type': 'BOOLEAN'}, configuration={'semantic_type': 'BOOLEAN'})
    workflow = WorkflowStatusService(current_project_id())
    workflow.save_parameters({'industry': 'automotive', 'technology': 'can_fd', 'formats': ['universal-jsonl'],
        'bitrate': 500000, 'data_bitrate': 2000000, 'cycle_ms': 100, 'payload_bytes': 1, 'queue_size': 256,
        'warning_threshold': 60, 'critical_threshold': 75, 'overload_threshold': 90, 'target_bus_load_percent': 60,
        'networks': [{'id': 'chassis-can', 'name': 'Chassis_CAN', 'technology': 'CAN_FD', 'bitrate': 500000, 'data_bitrate': 2000000}]})
    from backend.engineering.db import flush_model_changes
    flush_model_changes(actor='fixture', reason='test fixture')
    return {'src': src, 'dst': dst, 'sf': sf, 'df': df, 'sp': sp, 'message': message, 'signal': signal}

def prepare(data):
    from backend.engineering.goal_execution import service
    return service.prepare('Verbinde ParkAssist mit DriverAssistance', data['sf']['id'], data['df']['id'])

def confirm(goal):
    from backend.engineering.goal_execution import service
    return service.answer(goal['workload_id'], goal['pending_decision']['decision_id'], [goal['strategies'][0]['id']], actor='test-user')

def test_parkassist_real_followups_and_reuse(project):
    from backend.engineering.goal_execution import service
    from backend.engineering.goal_execution.graph import ModelGraphService
    from backend.engineering.repository import get_object
    data = fixture(); goal = prepare(data)
    assert goal['status'] == 'SUSPENDED_FOR_DECISION', goal
    assert goal['strategies'][0]['option']['id'] == 'CREATE_AND_CONNECT_PORT'
    assert service.presentation(goal)['question']['options']
    confirm(goal)
    result = service.resume(goal['workload_id'])
    if result['status'] != 'COMPLETE':
        import json
        pytest.fail(json.dumps({'findings': result.get('findings'), 'missing': result.get('completion', {}).get('missing_conditions'),
            'preflight_findings': result.get('preflight', {}).get('findings')}, ensure_ascii=False))
    graph = ModelGraphService.load()
    assert len(graph.find_ports(data['dst']['id'])) == 1
    assert graph.find_ports(data['dst']['id'])[0]['network_ref'] == 'chassis-can'
    assert len(result['route_ids']) == 1
    assert result['completion']['evidence']['capacity_valid']
    assert result['completion']['evidence']['routing_valid']
    assert get_object('Signal', data['signal']['id'])['length_bits'] == 1
    assert len(graph.find_functions_on_hardware(data['dst']['id'])) == 1
    again = prepare(data)
    assert again['strategies'][0]['option']['id'] == 'REUSE'

def test_unapproved_plan_cannot_mutate(project):
    from backend.engineering.goal_execution.executor import execute
    from backend.engineering.goal_execution.graph import ModelGraphService
    data = fixture(); goal = prepare(data); before = ModelGraphService.load().revision
    with pytest.raises(PermissionError): execute(goal['workload_id'])
    assert ModelGraphService.load().revision == before


def hardware_fact_payload(data, owner, graph):
    return {'expected_revision': graph.revision, 'evidence': 'Geprüftes Hardwaredatenblatt Revision 3',
        'capability': {'id': 'cap-' + owner, 'hardware_node_ref': owner, 'technology': 'CAN_FD', 'supported': True,
            'controller_count': 1, 'max_channels': 2, 'max_ports': 2, 'supported_bitrates': [500000]},
        'controllers': [{'id': 'controller-' + owner, 'hardware_node_ref': owner, 'technology': 'CAN_FD', 'max_channels': 2}],
        'assignments': [{'interface_ref': i['id'], 'controller_ref': 'controller-' + owner, 'channel_index': i.get('channel_index') or 1}
            for i in graph.find_hardware_interfaces(owner) if i['technology'] == 'CAN_FD']}


def test_missing_hardware_facts_captured_and_same_goal_completes(project):
    from backend.engineering.goal_execution import service, hardware_facts
    from backend.engineering.goal_execution.graph import ModelGraphService
    from backend.engineering.db import get_connection
    from backend.engineering.repository import update_object, get_object
    data = fixture()
    with get_connection() as conn:
        conn.execute("DELETE FROM engineering_communication_resources WHERE project_id=%s", (project,))
    update_object('HardwareNetworkInterface', data['sp']['id'], {'controller_ref': None})
    goal = prepare(data)
    assert goal['status'] == 'BLOCKED'
    assert service.presentation(goal)['metadata']['hardware_facts_required']
    inventory = hardware_facts.inspect(goal['workload_id'])
    assert {h['id'] for h in inventory['hardware']} == {data['src']['id'], data['dst']['id']}
    for owner in (data['src']['id'], data['dst']['id']):
        graph = ModelGraphService.load()
        hardware_facts.record(goal['workload_id'], hardware_fact_payload(data, owner, graph), actor='human-test')
    reassessed = service.resume(goal['workload_id'])
    assert reassessed['workload_id'] == goal['workload_id']
    assert reassessed['status'] == 'SUSPENDED_FOR_DECISION', reassessed.get('findings')
    confirm(reassessed)
    result = service.resume(goal['workload_id'])
    assert result['status'] == 'COMPLETE', result.get('findings')
    original = get_object('HardwareNetworkInterface', data['sp']['id'])
    assert original['physical_port_ref'] == data['sp']['physical_port_ref']
    assert original['network_ref'] == data['sp']['network_ref']
    assert len([e for e in result['journal'] if e['kind'] == 'HARDWARE_FACTS_CONFIRMED']) == 2


def test_existing_hni_channel_is_completed_without_second_interface(project):
    from backend.engineering.repository import create_object
    from backend.engineering.goal_execution import service
    from backend.engineering.goal_execution.graph import ModelGraphService
    data = fixture()
    hni = create_object('HardwareNetworkInterface', {'name': 'ADAS CAN Controller Channel', 'hardware_node_id': data['dst']['id'],
        'technology': 'CAN_FD', 'controller_ref': 'controller-' + data['dst']['id'], 'channel_index': 1})
    goal = prepare(data)
    assert goal['status'] == 'SUSPENDED_FOR_DECISION', goal.get('findings')
    assert goal['strategies'][0]['option']['hardware_interface_ref'] == str(hni['id'])
    confirm(goal); result = service.resume(goal['workload_id'])
    assert result['status'] == 'COMPLETE', result.get('findings')
    interfaces = ModelGraphService.load().find_hardware_interfaces(data['dst']['id'])
    assert [i['id'] for i in interfaces] == [str(hni['id'])]
    assert interfaces[0]['physical_port_ref'] and interfaces[0]['network_ref'] == 'chassis-can'


def test_hardware_fact_batch_revision_limits_and_no_silent_replug(project):
    from backend.engineering.goal_execution import hardware_facts
    from backend.engineering.goal_execution.graph import ModelGraphService
    from backend.engineering.db import ConcurrentUpdateError
    data = fixture(); goal = prepare(data); graph = ModelGraphService.load()
    facts = hardware_fact_payload(data, data['src']['id'], graph)
    facts['expected_revision'] = 'stale'
    with pytest.raises(ConcurrentUpdateError): hardware_facts.record(goal['workload_id'], facts, actor='human-test')
    facts['expected_revision'] = graph.revision
    facts['capability']['max_ports'] = 0
    with pytest.raises(ValueError, match='Hardwaregrenzen'): hardware_facts.record(goal['workload_id'], facts, actor='human-test')
    facts['capability']['max_ports'] = 2
    facts['assignments'][0]['channel_index'] = 2
    with pytest.raises(ValueError, match='umgehängt'): hardware_facts.record(goal['workload_id'], facts, actor='human-test')
    assert ModelGraphService.load().revision == graph.revision


def test_hardware_fact_batch_rolls_back_on_write_failure(project, monkeypatch):
    from backend.engineering.goal_execution import hardware_facts
    from backend.engineering.goal_execution.graph import ModelGraphService
    from backend.engineering import repository
    data = fixture(); goal = prepare(data); graph = ModelGraphService.load()
    facts = hardware_fact_payload(data, data['src']['id'], graph)
    def fail(*args, **kwargs): raise RuntimeError('Injected fact write failure')
    monkeypatch.setattr(repository, 'update_object', fail)
    with pytest.raises(RuntimeError, match='Injected'): hardware_facts.record(goal['workload_id'], facts, actor='human-test')
    assert ModelGraphService.load().revision == graph.revision

def test_revision_change_invalidates_authority(project):
    from backend.engineering.goal_execution import service
    from backend.engineering.repository import update_object
    data = fixture(); goal = prepare(data); confirm(goal)
    update_object('HardwareNode', data['dst']['id'], {'description': 'Concurrent hardware change'})
    result = service.resume(goal['workload_id'])
    assert result['status'] == 'PLAN_STALE'
    assert result['authorization'] is None

def test_partial_failure_rolls_back_entire_canonical_batch(project, monkeypatch):
    from backend.engineering.goal_execution import service, commands
    from backend.engineering.goal_execution.graph import ModelGraphService
    data = fixture(); goal = prepare(data); confirm(goal); before = ModelGraphService.load().revision
    def fail(*args): raise RuntimeError('Injected route failure')
    monkeypatch.setattr(commands, 'ensure_routes', fail)
    result = service.resume(goal['workload_id'])
    assert result['status'] == 'FAILED', result.get('findings')
    assert ModelGraphService.load().revision == before
    assert result['journal'][-1]['kind'] == 'CANONICAL_BATCH_ROLLED_BACK'

def test_preview_is_read_only_and_capacity_blocks_before_choice(project):
    from backend.engineering.goal_execution.graph import ModelGraphService
    from backend.engineering.workflow.service import WorkflowStatusService
    data = fixture(); before = ModelGraphService.load().revision
    goal = prepare(data)
    assert ModelGraphService.load().revision == before
    assert goal['strategies'][0]['technical_preview']['persisted'] is False
    workflow = WorkflowStatusService(project)
    parameters = workflow.get()['parameters']; parameters['target_bus_load_percent'] = 0.000001
    workflow.save_parameters(parameters)
    rejected = prepare(data)
    assert rejected['status'] == 'BLOCKED'
    assert not rejected['strategies']
    assert 'NETWORK_CAPACITY_EXCEEDED' in {f['code'] for f in rejected['findings']}

def test_concurrent_matching_port_is_reused_after_answer(project):
    from backend.engineering.goal_execution import service
    from backend.engineering.repository import create_object
    from backend.engineering.goal_execution.graph import ModelGraphService
    data = fixture(); goal = prepare(data)
    port = create_object('HardwareNetworkInterface', {'name': 'Added concurrently', 'hardware_node_id': data['dst']['id'],
        'technology': 'CAN_FD', 'controller_ref': 'controller-' + data['dst']['id'], 'channel_index': 1,
        'physical_port_ref': 'concurrent-connector', 'network_ref': 'chassis-can', 'bitrate': 500000, 'data_bitrate': 2000000})
    answered = confirm(goal)
    assert answered['status'] == 'READY'
    selected = next(s for s in answered['strategies'] if s['id'] == answered['authorization']['approved_strategy'])
    assert selected['option']['id'] == 'REUSE'
    result = service.resume(goal['workload_id'])
    assert result['status'] in {'COMPLETE', 'READY_FOR_REVIEW'}, result.get('findings')
    assert [p['hardware_interface_ref'] for p in ModelGraphService.load().find_ports(data['dst']['id'])] == [str(port['id'])]

def test_chat_affirmative_continues_same_goal_without_navigation(project):
    import asyncio
    from backend.engineering.agent_tools import conversation
    from backend.engineering.agent_tools.services import TOOLS
    from backend.agent_core.api.tool_contract import ToolResult
    from backend.agent_core.context.agent_context import AgentContext
    from backend.agent_core.core.engineering_agent import EngineeringAgent
    data = fixture()
    class Client:
        async def call(self, name, args=None):
            normalized = TOOLS[name].input_model.model_validate(args or {}).model_dump()
            return ToolResult(data=TOOLS[name].handler(normalized))
    prompt = 'Verbinde ParkAssist mit DriverAssistance'
    context = AgentContext(active_project_id=project)
    started = conversation.begin(prompt, context)
    first = asyncio.run(EngineeringAgent(Client()).run(started['prompt'], AgentContext.model_validate(started['context']),
        emit=lambda event: conversation.record_event(started['run_id'], event)))
    assert first['status'] == 'SUSPENDED_FOR_DECISION', first
    conversation.finish(started['run_id'])
    continued = conversation.begin('Ja', context)
    same_id = continued['context']['current_workload']
    second = asyncio.run(EngineeringAgent(Client()).run(continued['prompt'], AgentContext.model_validate(continued['context']),
        emit=lambda event: conversation.record_event(continued['run_id'], event)))
    assert second['status'] in {'COMPLETE', 'READY_FOR_REVIEW'}, second
    assert second['context']['current_workload'] == same_id
    assert [t['tool'] for t in second['trace']] == ['continue_engineering_goal']
    assert not any(e.get('actions') for e in second['events'])
    conversation.finish(continued['run_id'])

def test_goal_is_not_available_in_another_project(project):
    from backend.engineering.project_context import activate_project, reset_project
    from backend.engineering.goal_execution.store import get_goal
    data = fixture(); goal = prepare(data)
    token = activate_project('other-goal-project-' + uuid4().hex)
    try:
        with pytest.raises(LookupError): get_goal(goal['workload_id'])
    finally: reset_project(token)

def test_real_mcp_protocol_executes_authorized_plan_and_streams_progress(project):
    import asyncio
    from backend.engineering.db import _request_unit
    from backend.engineering.agent_tools.runtime import ToolAuthority, execute
    from backend.agent_core.api.tool_contract import Permission
    from backend.agent_core.api.mcp_client import EngineeringMCPClient
    from backend.simulator_engineering_mcp.server import create_server
    from backend.engineering.goal_execution import service
    from backend.engineering.project_bundle import ProjectBundleService
    data = fixture(); _request_unit.get().finish(True)
    progress = []
    authority = ToolAuthority(project, progress_callback=progress.append)
    async def run():
        async with EngineeringMCPClient(create_server(authority)) as client:
            tools = await client.tools()
            assert 'continue_engineering_goal' in {t['name'] for t in tools}
            assert not any('authorize' in t['name'] for t in tools)
            planned = await client.call('prepare_engineering_connection', {'goal': 'Verbinde ParkAssist mit DriverAssistance',
                'source_ref': data['sf']['id'], 'target_ref': data['df']['id']})
            assert planned.success, planned
            assert not progress, 'Rolled-back technical previews must not appear as actual execution progress'
            wid = planned.data['workload_id']; question = planned.data['agent_response']['question']
            human = execute(ToolAuthority(project, 'conversation-user'), 'test_human_answer', Permission.READ_MODEL, {},
                lambda _: service.answer(wid, question['id'], [question['options'][0]['id']], actor='conversation-user'))
            assert human.success, human
            forbidden = await client.call('continue_engineering_goal', {'workload_id': wid, 'authorization': {'authorized_by': 'model'}})
            assert not forbidden.success
            finished = await client.call('continue_engineering_goal', {'workload_id': wid})
            assert finished.success, finished
            assert finished.data['status'] == 'COMPLETE', finished.data
            outputs = finished.data['agent_response']['outputs']
            assert {item['output_type'] for item in outputs} == {'VISUALIZATION', 'VALIDATION'}
            assert all(item['project_ref'] == project for item in outputs)
            assert {'ParkAssist', 'DriverAssistance', 'Chassis_CAN'} <= {node['label'] for node in outputs[0]['visualization']['nodes']}
            assert len(progress) == 23
            repeated = await client.call('continue_engineering_goal', {'workload_id': wid})
            assert repeated.data['status'] == 'COMPLETE'
            assert len(progress) == 23, 'A completed workload must not execute again'
    try: asyncio.run(run())
    finally:
        ProjectBundleService().reset_workspace(project)
        _request_unit.get().finish(True)


def test_real_chat_connection_stream_keeps_every_response_valid(project, tmp_path):
    import json
    import subprocess
    from pathlib import Path
    from backend.app import create_app
    from backend.engineering.db import _request_unit
    from backend.agent_core.api.agent_response import AgentResponse
    fixture(); _request_unit.get().finish(True)
    _request_unit.get().close()
    client = create_app(testing=True).test_client()
    headers = {'X-Project-ID': project}
    def send(body):
        response = client.post('/api/engineering/agent/chat', headers=headers, json=body)
        assert response.status_code == 200, response.data
        events = [json.loads(line) for line in response.data.decode().splitlines()]
        for event in events:
            if event['type'] not in {'CONTEXT', 'HEARTBEAT'}:
                assert not event.get('metadata', {}).get('contract_error'), event
                AgentResponse.model_validate(event)
        return events
    first = send({'prompt': 'Verbinde ParkAssist mit DriverAssistance', 'context': {}})
    question = next(e['question'] for e in first if e.get('question'))
    second = send({'prompt': '', 'context': {}, 'input': {'type': 'QUESTION_ANSWER',
        'question_id': question['id'], 'selected_options': [question['options'][0]['id']]}})
    assert any(e.get('status') == 'COMPLETE' for e in second)
    payload = tmp_path / 'responses.json'
    payload.write_text(json.dumps([e for e in first + second if e['type'] not in {'CONTEXT', 'HEARTBEAT'}]), encoding='utf8')
    root = Path(__file__).resolve().parents[2]
    code = "import fs from 'node:fs'; import {agentResponseSchema} from './src/lib/agent/agent-response.ts'; for(const e of JSON.parse(fs.readFileSync(process.argv[1],'utf8'))) agentResponseSchema.parse(e);"
    subprocess.run(['node', '--experimental-strip-types', '--input-type=module', '-e', code, str(payload)], cwd=root/'frontend', check=True)

def test_missing_functional_requirement_is_not_reported_as_complete(project):
    from backend.engineering.repository import update_object
    from backend.engineering.goal_execution import service
    data = fixture()
    config = data['message']['configuration']; config['communication_contract']['transmission'].pop('functional_requirements')
    update_object('Message', data['message']['id'], {'configuration': config})
    goal = prepare(data); confirm(goal)
    result = service.resume(goal['workload_id'])
    assert result['status'] == 'READY_FOR_REVIEW'
    assert result['completion']['missing_conditions'] == ['timing_valid']
    assert result['completion']['evidence']['capacity_valid']

def test_missing_frame_parameters_are_generated_without_changing_signals(project):
    from backend.engineering.repository import update_object, get_object
    from backend.engineering.goal_execution import service
    data = fixture()
    update_object('Message', data['message']['id'], {'message_id_hex': None, 'dlc': None})
    before = dict(get_object('Signal', data['signal']['id']))
    goal = prepare(data); assert goal['status'] == 'SUSPENDED_FOR_DECISION', goal.get('findings')
    confirm(goal); result = service.resume(goal['workload_id'])
    assert result['status'] == 'COMPLETE', result.get('findings')
    message = get_object('Message', data['message']['id'])
    assert message['dlc'] == 1 and message['message_id_hex'] == '0x100'
    assert get_object('Signal', data['signal']['id']) == before

def test_human_hardware_fact_cannot_move_controller_to_another_device(project):
    from backend.engineering.goal_execution.graph import ModelGraphService
    from backend.engineering.goal_execution.resources import record_hardware_fact
    data = fixture(); graph = ModelGraphService.load()
    controller = graph.find_communication_controllers(data['src']['id'])[0]
    controller['hardware_node_ref'] = data['dst']['id']
    with pytest.raises(ValueError, match='übertragen'):
        record_hardware_fact('CommunicationController', controller, graph.revision)

def test_pure_input_port_is_not_offered_for_a_sender(project):
    from backend.engineering.goal_execution.store import save_resource
    data = fixture(); port = data['sp']
    save_resource('PhysicalPort', {'id': port['physical_port_ref'], 'hardware_node_ref': data['src']['id'],
        'controller_ref': port['controller_ref'], 'hardware_interface_ref': port['id'], 'technology': 'CAN_FD',
        'channel_index': 1, 'network_ref': 'chassis-can', 'connection_status': 'CONNECTED', 'direction': 'INPUT'})
    goal = prepare(data)
    assert goal['status'] == 'BLOCKED'
    assert any(f['code'] == 'PORT_DIRECTION_MISMATCH' for f in goal['findings'])

def test_explicit_event_contract_is_preserved_without_fallback_cycle(project):
    from backend.engineering.repository import update_object, get_object
    from backend.engineering.goal_execution import service
    data = fixture(); config = data['message']['configuration']
    config['communication_contract']['transmission'].update(mode='EVENT', trigger='explicit', minimum_interval_ms=100, release_times_ms=[0, 200])
    config['communication_contract']['transmission'].pop('period_ms')
    update_object('Message', data['message']['id'], {'configuration': config, 'cycle_ms': None})
    goal = prepare(data)
    assert goal['status'] == 'SUSPENDED_FOR_DECISION', goal.get('findings')
    confirm(goal); result = service.resume(goal['workload_id'])
    assert result['status'] in {'COMPLETE', 'READY_FOR_REVIEW'}, result.get('findings')
    assert result['completion']['evidence']['capacity_valid']
    assert result['status'] == 'COMPLETE', result.get('preflight', {}).get('findings')
    message = get_object('Message', data['message']['id'])
    assert message['cycle_ms'] is None
    assert message['configuration']['communication_contract']['transmission'] == config['communication_contract']['transmission']

def test_import_preserves_resources_but_never_execution_authority(project):
    from backend.engineering.project_bundle import ProjectBundleService
    from backend.engineering.goal_execution.store import get_goal, resources
    from backend.engineering.project_context import activate_project, reset_project
    from backend.engineering.db import RequestUnit
    data = fixture(); goal = prepare(data); confirm(goal)
    target = project + '-import'
    bundle = ProjectBundleService().export(project, target_project_id=target)
    assert bundle['bundle_version'] == 4
    assert bundle['source_data']['engineering_communication_resources']
    token = activate_project(target); unit = RequestUnit(target)
    try:
        ProjectBundleService().import_bundle(bundle, target_project_id=target)
        imported = get_goal(goal['workload_id'])
        assert imported['status'] == 'PLAN_STALE' and imported['authorization'] is None
        assert imported['pending_decision'] is None
        assert resources()['CommunicationController']
        assert all(c['hardware_node_ref'] not in {data['src']['id'], data['dst']['id']} for c in resources()['CommunicationController'])
    finally:
        unit.finish(False); unit.close(); reset_project(token)

def test_derived_repair_is_bounded_and_does_not_claim_completion(project, monkeypatch):
    from backend.engineering.goal_execution import service
    from backend.engineering.capacity.service import PreflightService
    data = fixture(); goal = prepare(data); confirm(goal)
    calls = []
    def unavailable(_):
        calls.append(True)
        return {'ready_for_simulation': False, 'findings': [{'code': 'WORKFLOW_STEP_NOT_READY', 'severity': 'ERROR', 'message': 'Injected stale projection'}]}
    monkeypatch.setattr(PreflightService, 'run', unavailable)
    result = service.resume(goal['workload_id'])
    assert result['status'] == 'READY_FOR_REVIEW'
    assert result['completion']['missing_conditions'] == ['preflight_valid']
    assert len(calls) == 2, 'Stop when derived repair makes no progress'
    assert any(e['kind'] == 'DERIVED_REPAIR_EVALUATED' for e in result['journal'])

@pytest.mark.parametrize('trace_status,expected', [('transmitted', 'COMPLETE'), ('corrupted', 'INCOMPLETE')])
def test_requested_simulation_runs_after_commit_and_requires_route_evidence(project, monkeypatch, trace_status, expected):
    from backend.engineering.goal_execution import service
    from backend.engineering.goal_execution.store import get_goal
    from backend.engineering.db import _request_unit
    from backend.engineering.agent_tools import simulation_gateway
    from backend.engineering.agent_tools.runtime import ToolAuthority, execute
    from backend.engineering.agent_tools.services import TOOLS
    from backend.engineering.workflow.service import WorkflowStatusService
    from backend.engineering.project_bundle import ProjectBundleService
    data = fixture()
    goal = service.prepare('Verbinde ParkAssist mit DriverAssistance und simuliere die Kommunikation', data['sf']['id'], data['df']['id'])
    assert 'simulieren' in goal['pending_decision']['question']
    confirm(goal)
    _request_unit.get().finish(True)
    starts, frames = [], []
    def start(snapshot_id):
        assert _request_unit.get().connection is None, 'Job dispatch must happen after the canonical transaction commits'
        workflow = WorkflowStatusService(project)
        snapshot = workflow.claim_simulation_snapshot(snapshot_id)
        starts.append(snapshot_id)
        assert snapshot['configuration']['communications']
        route_ids = get_goal(goal['workload_id'])['route_ids']
        frames.extend({'status': trace_status, 'route_ref': rid, 'final_segment': True, 'traffic_type': 'DATA'} for rid in route_ids)
        workflow.update_simulation_snapshot(snapshot_id, status='COMPLETED', job_id='test-goal-job', result={'status': 'completed'})
        return {'id': 'test-goal-job', 'status': 'completed'}
    monkeypatch.setattr(simulation_gateway, 'start', start)
    monkeypatch.setattr(simulation_gateway, 'iter_trace', lambda _: iter(frames))
    definition = TOOLS['continue_engineering_goal']
    try:
        result = execute(ToolAuthority(project), definition.name, definition.permission, {'workload_id': goal['workload_id']}, definition.handler)
        assert result.success, result
        assert result.data['status'] == expected, result.data
        final = get_goal(goal['workload_id'])
        assert final['completion']['evidence']['simulation_complete']
        assert final['completion']['evidence']['communication_observed'] == (trace_status == 'transmitted')
        assert final['followup']['snapshot_id'] == starts[0]
        assert final['followup']['trace_sha256']
        assert final['followup_authorization'] is None
    finally:
        ProjectBundleService().reset_workspace(project)
        _request_unit.get().finish(True)

def test_explicit_connection_request_reuses_existing_ports_without_extra_question(project):
    from backend.engineering.repository import create_object
    from backend.engineering.goal_execution import service
    from backend.engineering.agent_tools import conversation
    from backend.agent_core.context.agent_context import AgentContext
    data = fixture()
    create_object('HardwareNetworkInterface', {'name': 'Existing ADAS CAN', 'hardware_node_id': data['dst']['id'],
        'technology': 'CAN_FD', 'controller_ref': 'controller-' + data['dst']['id'], 'channel_index': 1,
        'physical_port_ref': 'existing-adas-can', 'network_ref': 'chassis-can', 'bitrate': 500000, 'data_bitrate': 2000000})
    prompt = 'Verbinde die Funktion ParkAssist mit der Funktion DriverAssistance'
    started = conversation.begin(prompt, AgentContext(active_project_id=project))
    result = service.prepare(prompt, data['sf']['id'], data['df']['id'])
    assert result['status'] == 'COMPLETE', result.get('findings')
    assert result['pending_decision'] is None
    assert any(e['kind'] == 'DECISION_AUTHORIZED' and e['authorization']['decision_id'] == 'explicit-user-connection-request' for e in result['journal'])
    conversation.finish(started['run_id'])


def test_background_resumes_same_simulation_and_publishes_once(project, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from backend.engineering.goal_execution import service, background
    from backend.engineering.goal_execution.store import get_goal
    from backend.engineering.db import _request_unit
    from backend.engineering.agent_tools import simulation_gateway, conversation
    from backend.engineering.workflow.service import WorkflowStatusService
    from backend.engineering.project_bundle import ProjectBundleService
    data = fixture()
    goal = service.prepare('Verbinde ParkAssist mit DriverAssistance und simuliere die Kommunikation', data['sf']['id'], data['df']['id'])
    confirm(goal); goal = service.resume(goal['workload_id'])
    assert goal['status'] == 'FOLLOWUP_PENDING'
    _request_unit.get().finish(True)
    starts, reads = [], []
    def start(snapshot_id):
        assert _request_unit.get().connection is None
        workflow = WorkflowStatusService(project)
        workflow.claim_simulation_snapshot(snapshot_id)
        workflow.update_simulation_snapshot(snapshot_id, status='RUNNING', job_id='durable-job', result={'status': 'running'})
        starts.append(snapshot_id)
        return {'id': 'durable-job', 'status': 'running'}
    def job(job_id):
        assert _request_unit.get().connection is None
        reads.append(job_id)
        WorkflowStatusService(project).update_simulation_snapshot(starts[0], status='COMPLETED', job_id=job_id, result={'status': 'completed'})
        return {'id': job_id, 'status': 'completed'}
    monkeypatch.setattr(simulation_gateway, 'start', start)
    monkeypatch.setattr(simulation_gateway, 'job', job)
    monkeypatch.setattr(simulation_gateway, 'iter_trace', lambda _: iter([{'status': 'transmitted', 'route_ref': rid} for rid in goal['route_ids']]))
    now = datetime.now(timezone.utc)
    try:
        first = background.tick(project, goal['workload_id'], now=now)
        assert first.success and first.data['status'] == 'SIMULATION_RUNNING', first
        duplicate = background.tick(project, goal['workload_id'], now=now)
        assert duplicate.success and duplicate.data['claimed'] is False
        assert len(starts) == 1 and not reads
        completed = background.tick(project, goal['workload_id'], now=now + timedelta(seconds=11))
        assert completed.success and completed.data['status'] == 'COMPLETE', completed
        assert reads == ['durable-job']
        final = get_goal(goal['workload_id'])
        assert final['background']['published_status'] == 'COMPLETE'
        messages = conversation.history()['messages']
        assert len([m for m in messages if m['id'] == goal['workload_id'] + '-complete']) == 1
        assert background.publish(goal['workload_id']) == {'published': False}
        assert not [row for row in background.pending() if row['workload_id'] == goal['workload_id']]
    finally:
        ProjectBundleService().reset_workspace(project)
        _request_unit.get().finish(True)


def test_background_claim_is_bounded_and_requires_saved_authority(project):
    from backend.engineering.goal_execution import service, background
    from backend.engineering.goal_execution.store import get_goal, save_goal
    data = fixture(); goal = prepare(data)
    assert background.claim(goal['workload_id']) == {'claimed': False}
    goal.update(status='SIMULATION_RUNNING', followup_authorization=None)
    save_goal(goal)
    assert background.claim(goal['workload_id']) == {'claimed': False}
    goal.update(followup_authorization={'goal': goal['goal']}, background={'checks': 720})
    save_goal(goal)
    assert background.claim(goal['workload_id']) == {'claimed': False, 'publish': True}
    assert get_goal(goal['workload_id'])['status'] == 'BACKGROUND_PAUSED'
    resumed = service.resume(goal['workload_id'])
    assert resumed['background'] == {} and resumed['status'] == 'SIMULATION_RUNNING'


def test_connection_to_real_simulation_engine_and_trace_artifact(project, monkeypatch, tmp_path):
    """Only HTTP transport is in-process; canonical API, job, engine and trace are real."""
    import importlib
    import io
    from urllib.parse import urlsplit
    from backend.app import create_app
    from backend.app.job_service import JobService
    from backend.app.trace_storage import TraceStorage
    from backend.engineering.goal_execution import service
    from backend.engineering.goal_execution.store import get_goal
    from backend.engineering.db import _request_unit
    from backend.engineering.agent_tools import simulation_gateway
    from backend.engineering.agent_tools.runtime import ToolAuthority, execute
    from backend.engineering.agent_tools.services import TOOLS
    from backend.engineering.project_bundle import ProjectBundleService
    jobs = JobService(synchronous=True, persist=False, storage=TraceStorage(default_root=tmp_path, settings_path=tmp_path / 'storage.json'))
    monkeypatch.setattr(importlib.import_module('backend.app.api'), 'JOBS', jobs)
    client = create_app(testing=True).test_client()
    def local_http(request, timeout=None):
        url = urlsplit(request.full_url)
        response = client.open(url.path + ('?' + url.query if url.query else ''), method=request.get_method(), data=request.data, headers=dict(request.header_items()))
        assert response.status_code < 400, response.get_data(as_text=True)
        return io.BytesIO(response.data)
    monkeypatch.setattr(simulation_gateway, 'urlopen', local_http)
    data = fixture()
    goal = service.prepare('Verbinde ParkAssist mit DriverAssistance und simuliere für 1 s', data['sf']['id'], data['df']['id'])
    confirm(goal); _request_unit.get().finish(True)
    definition = TOOLS['continue_engineering_goal']
    try:
        result = execute(ToolAuthority(project), definition.name, definition.permission, {'workload_id': goal['workload_id']}, definition.handler)
        assert result.success, result
        final = get_goal(goal['workload_id'])
        assert final['status'] == 'COMPLETE', {'result': result.data, 'jobs': jobs.list(project), 'findings': final.get('findings')}
        assert final['followup']['event_count'] > 0
        assert set(final['route_ids']) <= set(final['followup']['observed_routes'])
        job = jobs.get(final['followup']['job_id'], project)
        assert job['status'] == 'completed'
        assert any(str(path).endswith('universal_trace.jsonl') for path in job['result']['artifacts'])
    finally:
        ProjectBundleService().reset_workspace(project)
        _request_unit.get().finish(True)
