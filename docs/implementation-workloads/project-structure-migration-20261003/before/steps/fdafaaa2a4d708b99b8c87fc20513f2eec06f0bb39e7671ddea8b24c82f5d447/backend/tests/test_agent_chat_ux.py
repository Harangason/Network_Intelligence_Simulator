"""Contract and real database regressions for structured conversation decisions."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import time
from uuid import uuid4
import httpx
import pytest
from backend.agent_core.api.agent_response import AgentResponse, InteractiveQuestion, validate_response
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.core.engineering_agent import EngineeringAgent, reasoning_workload_progress
from backend.agent_core.orchestration.local_reasoner import LocalEngineeringReasoner, _context_for_reasoning, _is_semantic_fast_request, _is_structured_wizard_request, _no_think_messages
from backend.agent_core.api.mcp_client import EngineeringMCPClient
from backend.agent_core.api.tool_contract import ToolResult
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.agent_core.api.tool_contract import Permission
from backend.engineering.agent_tools import conversation, proposal_service
from backend.engineering.agent_tools.run_status import WizardExecutionTracker, extract_wizard_run_id, recover_interrupted_wizard_runs, restore_wizard_continuation_prompt
from backend.engineering.workflow.service import WorkflowStatusService


def test_large_tool_output_cannot_evict_the_user_query():
    from backend.agent_core.orchestration.local_reasoner import _reasoning_messages
    content = json.dumps({'success': True, 'data': {'signals': [{'id': str(i), 'name': 'Signal' * 100} for i in range(500)]}})
    original = [{'role': 'user', 'content': 'Routing fortsetzen.'},
                {'role': 'tool', 'tool_call_id': 'call-1', 'content': content}]
    prepared = _reasoning_messages(original)
    assert prepared[0]['content'].startswith('Routing fortsetzen.')
    assert len(prepared[1]['content']) < 5000
    assert json.loads(prepared[1]['content'])['truncated'] is True
    assert original[1]['content'] == content


def test_problem_inventory_reads_facts_before_optional_ai_explanation():
    from backend.agent_core.orchestration.capability_intent import problem_report_question

    assert problem_report_question('Zeige mir die Probleme') == 'LIST'
    assert problem_report_question('Warum?', 'Zeige mir die Probleme') == 'EXPLAIN'
    assert problem_report_question('Repariere die Probleme') is None

    class FactsClient:
        def __init__(self):
            self.calls = []

        async def call(self, name, arguments=None):
            self.calls.append(name)
            assert name == 'inspect_findings'
            return ToolResult(data={
                'status': 'WARNING',
                'findings': [{'code': 'MISSING_SCHEDULE', 'severity': 'WARNING', 'status': 'OPEN',
                              'category': 'Timing', 'problem': 'I2C-Zeitnachweis fehlt.',
                              'detected_cause': 'Clock-Stretching-Grenze fehlt.',
                              'recommendation': 'Grenze festlegen und erneut prüfen.'}],
                'results': {'assessment_mode': 'DIAGNOSTIC'},
                'provenance': {'calculation_service': 'IntelligenceService',
                               'timestamp': '2026-09-24T12:00:00Z'},
            })

    class ExplainOnlyReasoner:
        def __init__(self):
            self.explanations = []

        async def next(self, *_args):
            raise AssertionError('Befundfragen dürfen keine Toolplanung durch das Modell starten')

        async def explain_findings(self, question, findings, provenance):
            self.explanations.append((question, findings, provenance))
            return 'Die Grenze ist für den Zeitnachweis erforderlich.'

    client, reasoner = FactsClient(), ExplainOnlyReasoner()
    first = asyncio.run(EngineeringAgent(client, reasoner=reasoner).run(
        'Zeige mir die Probleme', AgentContext(active_project_id='findings-project')))
    assert client.calls == ['inspect_findings']
    assert not reasoner.explanations
    assert first['status'] == 'ANSWERED'
    assert any(event.get('type') == 'FINDING' and 'I2C-Zeitnachweis' in event.get('text', '')
               for event in first['events'])
    assert 'diagnostisch' in first['text']

    second = asyncio.run(EngineeringAgent(client, reasoner=reasoner).run(
        'Warum?', AgentContext(active_project_id='findings-project',
                               current_requirement='Warum?'),
        history=[{'role': 'user', 'content': 'Zeige mir die Probleme'},
                 {'role': 'assistant', 'content': first['text']}]))
    assert client.calls == ['inspect_findings', 'inspect_findings']
    assert second['status'] == 'ANSWERED'
    assert 'KI-Einordnung' in second['text']
    assert reasoner.explanations[0][1][0]['detected_cause'] == 'Clock-Stretching-Grenze fehlt.'


def test_local_finding_explanation_uses_bounded_facts_without_tool_planning(monkeypatch):
    monkeypatch.setenv('LOCAL_AI_MODEL', 'qwen3.8:27b')
    captured = {}

    def respond(request):
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={'message': {'content': 'Der I2C-Nachweis benötigt eine Grenze.'}})

    async def invoke():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()
        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        try:
            return await reasoner.explain_findings('Warum?', [
                {'code': 'MISSING_SCHEDULE', 'problem': 'I2C-Zeitnachweis fehlt.',
                 'detected_cause': 'Clock-Stretching-Grenze fehlt.'}],
                {'source': 'IntelligenceService', 'calculated_at': '2026-09-24T12:00:00Z'})
        finally:
            await reasoner.close()

    assert 'I2C' in asyncio.run(invoke())
    assert captured['model'] == 'qwen3.8:27b'
    assert 'tools' not in captured
    assert captured['options']['num_predict'] <= 420
    assert 'Clock-Stretching-Grenze fehlt.' in captured['messages'][1]['content']
from backend.simulator_engineering_mcp.server import create_server


def run(authority, operation):
    return execute(authority, 'chat_ux_test', Permission.READ_MODEL, {}, lambda _: operation())


@pytest.mark.parametrize('kind', ['TEXT', 'RECOMMENDATION', 'FINDING', 'PROGRESS', 'RESULT', 'APPROVAL', 'ERROR'])
def test_response_types(kind):
    event = validate_response({'type': kind, 'text':'<script>alert(1)</script>'})
    assert event['type'] == kind  # plain data, never executable UI
    assert event['id'] and event['created_at']


def test_invalid_contract_falls_back():
    for invalid in ({'type':'HTML','html':'<script/>'}, {'type':'QUESTION'}, {'type':'TEXT','jsx':'<button/>'}):
        assert validate_response(invalid)['metadata']['contract_error']
    with pytest.raises(ValueError):
        InteractiveQuestion(question='Q', options=[{'id':'a','label':'A'}, {'id':'a','label':'B'}])


def test_local_reasoner_disables_hidden_thinking_without_mutating_history():
    messages = [{'role':'assistant', 'content':'Vorher'}, {'role':'user', 'content':'Werkzeug wählen'}]
    prepared = _no_think_messages(messages)
    assert prepared[-1]['content'] == 'Werkzeug wählen\n/no_think'
    assert messages[-1]['content'] == 'Werkzeug wählen'


def test_structured_wizard_request_uses_fast_orchestration_path():
    messages = [{'role': 'user', 'content': (
        'Strukturierte Vorgaben fuer den Engineering-Agenten:\n'
        '- Systemcluster-Graph: []\n'
        '- Netzarchitektur-ID: gateway_ecu_segments'
    )}]
    assert _is_structured_wizard_request(messages) is True
    assert _is_structured_wizard_request([{'role': 'user', 'content': 'Analysiere das Routing'}]) is False
    assert _is_semantic_fast_request([{'role': 'user', 'content': 'Ordne Sensoren den ECU-Controllern semantisch zu'}]) is True
    assert _is_semantic_fast_request([{'role': 'user', 'content': 'Schreibe eine umfassende Systemarchitektur'}]) is False


@pytest.mark.parametrize('prompt,fast', [
    ('Prüfe das aktuelle Engineering-Modell und erkläre anhand des tatsächlichen Projektstands, welche Hardware-Knoten bereits vorhanden sind.', True),
    ('Liste die vorhandenen Gateways.', True),
    ('Erstelle 200 ECUs und konfiguriere ihre Interfaces.', False),
    ('Prüfe die Hardware und ändere danach alle Kanalbindungen.', False),
])
def test_bounded_hardware_inventory_uses_fast_model_but_mutations_keep_main_reasoner(prompt, fast):
    assert _is_semantic_fast_request([{'role': 'user', 'content': prompt}]) is fast


def test_bounded_project_intake_uses_fast_local_model_for_advisory_planning():
    assert _is_semantic_fast_request([
        {'role': 'system', 'content': (
            'Erarbeite einen fachlichen Entwurf und nutze prepare_project_request. '
            'Die Originalanforderung bleibt unverändert.'
        )},
        {'role': 'user', 'content': 'Erstelle ein Projekt mit zwei Sensoren und einem Aktor.'},
    ]) is True


def test_local_reasoner_does_not_duplicate_the_full_requirement_in_system_context():
    context = AgentContext(active_project_id='reasoner-context', current_requirement='X' * 20_000)
    serialized = _context_for_reasoning(context)
    assert 'X' * 100 not in serialized
    assert 'reasoner-context' in serialized


def test_local_reasoner_uses_native_non_thinking_tool_contract():
    captured = {}

    def handler(request):
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={'message':{'content':'', 'tool_calls':[
            {'id':'call-1', 'function':{'name':'inspect_project', 'arguments':{}}}
        ]}})

    async def invoke():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()
        reasoner.chat_url = 'http://local.test/api/chat'
        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            return await reasoner.next(
                [{'role':'user', 'content':'Projekt prüfen'}],
                AgentContext(active_project_id='native-reasoner'),
                [{'name':'inspect_project', 'description':'Projekt prüfen', 'input_schema':{'type':'object','properties':{}}}],
            )
        finally:
            await reasoner.close()

    result = asyncio.run(invoke())
    assert captured['think'] is False and captured['stream'] is False
    assert captured['keep_alive'] == '10m'
    assert captured['messages'][-1]['content'].endswith('/no_think')
    assert result['calls'] == [{'id':'call-1', 'name':'inspect_project', 'arguments':{}}]


def test_local_reasoner_keeps_user_query_and_native_tool_result_on_second_turn(monkeypatch):
    captured = []
    monkeypatch.setenv('LOCAL_AI_CONTEXT_TOKENS', '32768')

    def handler(request):
        payload = json.loads(request.content)
        captured.append(payload)
        assert payload['options']['num_ctx'] == 32768
        assert sum(message['role'] == 'system' for message in payload['messages']) == 1
        if len(captured) == 1:
            return httpx.Response(200, json={'message': {'content': '', 'tool_calls': [
                {'function': {'name': 'inspect_project', 'arguments': {}}}]}})
        assert any(message['role'] == 'user' and 'Prüfe mein Projekt' in message['content'] for message in payload['messages'])
        tool = next(message for message in payload['messages'] if message['role'] == 'tool')
        assert tool['tool_name'] == 'inspect_project'
        assert len(tool['content']) < 5000
        return httpx.Response(200, json={'message': {'content': 'Das Projekt enthält zwei Hardwareknoten.'}})

    async def invoke():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()
        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            context = AgentContext(active_project_id='native-roundtrip')
            messages = [{'role': 'user', 'content': 'Prüfe mein Projekt'}]
            first = await reasoner.next(messages, context, [])
            messages.extend([first['assistant_message'], {'role': 'tool', 'tool_call_id': first['calls'][0]['id'],
                'content': json.dumps({'hardware': [{'name': 'Hardware' * 100} for _ in range(500)]})},
                {'role': 'system', 'content': 'Nutze die tatsächlichen Daten.'}])
            return await reasoner.next(messages, context, [])
        finally:
            await reasoner.close()
    assert asyncio.run(invoke())['text'] == 'Das Projekt enthält zwei Hardwareknoten.'


def test_native_schema_unwraps_mcp_request_and_malformed_model_arguments_are_repairable():
    from backend.agent_core.orchestration.local_reasoner import _tool_parameters
    schema = {'type': 'object', 'properties': {'request': {'$ref': '#/$defs/Input'}}, 'required': ['request'],
        '$defs': {'Input': {'type': 'object', 'properties': {'hardware_id': {'type': 'string'}}, 'required': ['hardware_id']}}}
    assert _tool_parameters(schema) == {'type': 'object', 'properties': {'hardware_id': {'type': 'string'}}, 'required': ['hardware_id']}

    async def invoke():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()
        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={'message': {
            'tool_calls': [{'function': {'name': 'inspect_hardware', 'arguments': {'request': 'please inspect the hardware'}}}]}})))
        try:
            return await reasoner.next([{'role': 'user', 'content': 'Zeige Hardware'}], AgentContext(active_project_id='bad-model-arguments'), [])
        finally:
            await reasoner.close()
    result = asyncio.run(invoke())
    assert result['calls'][0]['arguments'] == {'invalid_json_arguments': 'please inspect the hardware'}


def test_local_reasoner_keeps_fast_semantic_model_warm(monkeypatch):
    captured = {}
    monkeypatch.setenv('OLLAMA_FAST_KEEP_ALIVE', '45m')

    def handler(request):
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={'message': {'content': 'ok'}})

    async def invoke():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()
        reasoner.chat_url = 'http://local.test/api/chat'
        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            await reasoner.next(
                [{'role': 'user', 'content': 'Sensoren semantisch zuordnen'}],
                AgentContext(active_project_id='semantic-fast-model'),
                [],
            )
        finally:
            await reasoner.close()

    asyncio.run(invoke())
    assert captured['model'] == 'llama3.1:8b'
    assert captured['keep_alive'] == '45m'


def test_missing_fast_model_falls_back_to_main_local_model(monkeypatch):
    requests = []
    monkeypatch.setenv('LOCAL_AI_MODEL', 'qwen-test:latest')
    monkeypatch.setenv('LOCAL_AI_FAST_MODEL', 'llama-test:latest')

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        if payload['model'] == 'llama-test:latest':
            return httpx.Response(404, json={'error': 'model not found; pull it first'})
        return httpx.Response(200, json={'message': {'content': 'lokaler Fallback aktiv'}})

    async def invoke():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()
        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            return await reasoner.next(
                [{'role': 'user', 'content': 'Sensoren semantisch zuordnen'}],
                AgentContext(active_project_id='local-model-fallback'),
                [],
            )
        finally:
            await reasoner.close()

    result = asyncio.run(invoke())
    assert [item['model'] for item in requests] == ['llama-test:latest', 'qwen-test:latest']
    assert requests[1]['keep_alive'] == '10m'
    assert result['text'] == 'lokaler Fallback aktiv'


def test_wizard_execution_status_is_durable_and_uses_the_external_run_id():
    authority = ToolAuthority(f'wizard-execution-{uuid4()}')
    wizard_run_id = str(uuid4())
    assert extract_wizard_run_id(f'Vorgaben\n- Lauf-ID: {wizard_run_id}\nAuftrag') == wizard_run_id
    assert extract_wizard_run_id(f'Fortsetzung. Lauf-ID: {wizard_run_id}. Ziel: routing.') == wizard_run_id
    tracker = WizardExecutionTracker(authority.project_id, wizard_run_id)
    tracker.started()
    running = WorkflowStatusService(authority.project_id).get(summary=True)['context']['agent_execution']
    assert running['state'] == 'RUNNING'
    assert running['run_id'] == wizard_run_id
    tracker.event({'type':'PROGRESS', 'text':'12 von 50 geprüft.', 'workload':{'valid':12, 'requested':50}})
    progressed = WorkflowStatusService(authority.project_id).get(summary=True)['context']['agent_execution']
    assert progressed['completed'] == 12 and progressed['total'] == 50
    tracker.finished({'status':'READY_FOR_REVIEW', 'text':'Prüfung erforderlich.'})
    finished = WorkflowStatusService(authority.project_id).get(summary=True)['context']['agent_execution']
    assert finished['state'] == 'REVIEW_REQUIRED'
    assert finished['message'] == 'Prüfung erforderlich.'


@pytest.mark.parametrize('same_pid', [False, True])
def test_backend_restart_marks_only_the_old_process_wizard_as_recoverable(monkeypatch, same_pid):
    authority = ToolAuthority(f'chat-restart-recovery-{uuid4()}')
    run_id = 'wizard-restart-12345678'
    tracker = WizardExecutionTracker(authority.project_id, run_id)
    tracker.started()
    before = WorkflowStatusService(authority.project_id).get(summary=True)['context']['agent_execution']
    assert before['state'] == 'RUNNING'
    assert before['recoverable'] is False
    assert recover_interrupted_wizard_runs(authority.project_id) == 0

    if same_pid:
        monkeypatch.setattr('backend.engineering.agent_tools.run_status.SERVER_INSTANCE_ID', 'new-container-instance')
    else:
        monkeypatch.setattr('backend.engineering.agent_tools.run_status.os.getpid', lambda: before['server_pid'] + 1)
    assert recover_interrupted_wizard_runs(authority.project_id) == 1

    recovered = WorkflowStatusService(authority.project_id).get(summary=True)['context']['agent_execution']
    assert recovered['state'] == 'BLOCKED'
    assert recovered['recoverable'] is True
    assert recovered['run_id'] == run_id
    assert 'neu gestartet' in recovered['message']
    assert recover_interrupted_wizard_runs(authority.project_id) == 0


def test_reasoning_iterations_emit_bounded_structured_progress():
    assert reasoning_workload_progress(0, 12) == {'completed': 1, 'total': 12}
    assert reasoning_workload_progress(4, 12) == {'completed': 5, 'total': 12}
    assert reasoning_workload_progress(99, 12) == {'completed': 12, 'total': 12}
    assert reasoning_workload_progress(0, 0) == {'completed': 1, 'total': 1}


def test_engineering_agent_emits_structured_progress_after_each_reasoning_step():
    class OneToolReasoner:
        def __init__(self):
            self.turn = 0

        async def next(self, messages, context, tools):
            self.turn += 1
            if self.turn == 1:
                return {
                    'calls': [{'id': 'call-progress', 'name': 'inspect_project', 'arguments': {}}],
                    'assistant_message': {'role': 'assistant', 'content': '', 'tool_calls': []},
                }
            return {'text': 'Prüfung beendet.', 'calls': [], 'assistant_message': {}}

    authority = ToolAuthority(f'wizard-progress-{uuid4()}')
    emitted = []

    async def invoke():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAgent(client, reasoner=OneToolReasoner(), max_steps=3).run(
                'Prüfe Routing und Pfade.',
                AgentContext(active_project_id=authority.project_id),
                emit=emitted.append,
            )

    asyncio.run(invoke())
    progress = next(event for event in emitted if event.get('text') == 'Arbeitsschritt 1 geprüft.')
    assert progress['workload'] == {'completed': 1, 'total': 3}


def test_compact_wizard_continuation_restores_the_confirmed_request():
    run_id = str(uuid4())
    original = (
        'Strukturierte Vorgaben fuer den Engineering-Agenten:\n'
        f'- Lauf-ID: {run_id}\n'
        '- Hardware-Sollwerte: {"ecus": 2}\n'
        'Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:\n'
        'Erzeuge das Modell.'
    )
    compact = f'Setze den bestaetigten Engineering-Auftrag fort. Lauf-ID: {run_id}. Ziel: routing.'
    restored = restore_wizard_continuation_prompt(compact, {'run_id': run_id, 'agent_prompt': original})
    assert restored.startswith(original)
    assert restored.endswith(compact)
    assert restore_wizard_continuation_prompt(original, {'run_id': run_id, 'agent_prompt': original}) == original
    assert restore_wizard_continuation_prompt(compact, {'run_id': 'other-run', 'agent_prompt': original}) == compact
    assert len(restore_wizard_continuation_prompt(compact, {'run_id': run_id, 'agent_prompt': original}, 180)) <= 180


def test_conversation_heartbeat_only_renews_matching_run():
    authority = ToolAuthority(f'chat-heartbeat-{uuid4()}')
    context = AgentContext(active_project_id=authority.project_id)
    started = run(authority, lambda: conversation.begin('Analysiere das Projekt.', context)).data

    def add_marker_and_renew():
        state = conversation.read()
        state['heartbeat_marker'] = {'preserve': True}
        conversation.write(state)
        before = conversation.read()['lease_until']
        assert conversation.renew(started['run_id'], seconds=600)
        after = conversation.read()
        assert after['heartbeat_marker'] == {'preserve': True}
        assert after['lease_until'] > before
        assert not conversation.renew(str(uuid4()), seconds=600)

    run(authority, add_marker_and_renew)
    run(authority, lambda: conversation.finish(started['run_id']))


def test_chat_worker_survives_disconnected_stream(monkeypatch):
    from backend.app import create_app
    from backend.engineering.agent_tools import api as agent_api_module

    authority = ToolAuthority(f'chat-disconnect-{uuid4()}')
    wizard_run_id = str(uuid4())

    class DelayedAgent:
        def __init__(self, client, reasoner=None):
            pass

        async def run(self, prompt, context, *, emit, history):
            emit({'type':'PROGRESS', 'text':'Analyse gestartet.', 'workload':{'valid':1, 'requested':2}})
            await asyncio.sleep(0.15)
            emit({'type':'RESULT', 'status':'COMPLETED', 'text':'Analyse vollständig abgeschlossen.'})
            return {'status':'COMPLETED', 'text':'Analyse vollständig abgeschlossen.', 'context':context.model_dump()}

    monkeypatch.setattr(agent_api_module, 'EngineeringAgent', DelayedAgent)
    client = create_app(testing=True).test_client()
    response = client.post(
        '/api/engineering/agent/chat',
        headers={'X-Project-ID':authority.project_id},
        json={'prompt':f'Vorgaben\n- Lauf-ID: {wizard_run_id}\nAnalysiere vollständig.', 'context':{}},
        buffered=False,
    )
    assert response.status_code == 200
    response.close()

    deadline = time.monotonic() + 3
    execution = None
    while time.monotonic() < deadline:
        execution = WorkflowStatusService(authority.project_id).get(summary=True)['context'].get('agent_execution')
        if execution and execution.get('state') == 'COMPLETED':
            break
        time.sleep(0.05)
    assert execution and execution['run_id'] == wizard_run_id
    assert execution['state'] == 'COMPLETED'
    assert execution['message'] == 'Analyse vollständig abgeschlossen.'


def test_wizard_run_cannot_report_creation_without_a_tool_call():
    class HallucinatingReasoner:
        async def next(self, messages, context, tools):
            return {'text':'Alle 251 Geräte wurden erfolgreich angelegt.', 'calls':[], 'assistant_message':{}}

    authority = ToolAuthority(f'wizard-no-tool-{uuid4()}')
    prompt = ('Strukturierte Vorgaben fuer den Engineering-Agenten:\n'
              '- Lauf-ID: 12345678-abcd\n'
              'Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:\n'
              'Erzeuge 100 Sensoren und 50 ECUs.')

    async def invoke():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAgent(client, reasoner=HallucinatingReasoner()).run(
                prompt, AgentContext(active_project_id=authority.project_id)
            )

    result = asyncio.run(invoke())
    assert result['status'] == 'INCOMPLETE'
    assert 'kanonische Projektstand ist unverändert' in result['text']
    assert 'erfolgreich angelegt' not in result['text']


def setup_question():
    authority = ToolAuthority(f'chat-ux-{uuid4()}')
    context = AgentContext(active_project_id=authority.project_id, active_view='/studio')
    start = run(authority, lambda: conversation.begin('Plane eine Kamera zur Umfelderkennung', context)).data
    question = InteractiveQuestion(question='Auswahl?', options=[{'id':'a','label':'A','recommended':True}, {'id':'b','label':'B','disabled':True}]).model_dump()
    event = AgentResponse(type='SINGLE_SELECT', question=question).model_dump(mode='json')
    assert run(authority, lambda: conversation.record_event(start['run_id'], event)).success
    run(authority, lambda: conversation.finish(start['run_id']))
    return authority, context, question


def test_structured_answer_atomic_and_persistent():
    authority, context, question = setup_question()
    for options in ([], ['b'], ['a','a'], ['missing']):
        assert not run(authority, lambda: conversation.begin('', context, {'question_id':question['id'], 'selected_options':options})).success
    def answer():
        return run(authority, lambda: conversation.begin('', context, {'question_id':question['id'], 'selected_options':['a']}))
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _:answer(), range(2)))
    assert sum(result.success for result in results) == 1
    state = run(authority, conversation.inspect).data
    assert state['questions'][question['id']]['status'] == 'ANSWERED'
    assert state['answered_questions'][question['id']]['selected_options'] == ['a']
    assert 'Kamera' in state['current_requirement']


def test_question_context_change_rejected():
    authority, context, question = setup_question()
    result = run(authority, lambda: conversation.begin('', context.model_copy(update={'active_view':'/studio/routing'}), {'question_id':question['id'], 'selected_options':['a']}))
    assert result.status == 'CONFLICT'


def test_camera_dialog_to_approved_model():
    authority = ToolAuthority(f'camera-dialog-{uuid4()}')
    context = AgentContext(active_project_id=authority.project_id)
    prompt = 'Erstelle eine Kamerafunktion zur Überwachung der Umgebung'
    answer = None
    proposal = None
    async def turn(start):
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAgent(client).run(start['prompt'], AgentContext.model_validate(start['context']),
                emit=lambda event: assert_saved(run(authority, lambda: conversation.record_event(start['run_id'], event))))
    for _ in range(5):
        started = run(authority, lambda: conversation.begin(prompt, context, answer))
        assert started.success, started
        result = asyncio.run(turn(started.data))
        run(authority, lambda: conversation.finish(started.data['run_id']))
        questions = [event['question'] for event in result['events'] if event.get('question')]
        if questions:
            question = questions[-1]
            answer = {'question_id':question['id'], 'selected_options':question['recommended_options']}
        else:
            proposal = result['proposals'][0]
            break
    assert proposal and proposal['status'] == 'VALIDATED', proposal
    assert proposal['validation_result']['capacity_status'] == 'UNVERIFIED'
    assert any(item.get('code') == 'CAPACITY_UNVERIFIED' and item['severity'] == 'OPEN'
               for item in proposal['validation_result']['findings'])
    approved = run(authority, lambda: proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='human-test', trace_id=str(uuid4())))
    assert approved.success, approved
    applied = run(authority, lambda: proposal_service.apply(proposal['proposal_id'], actor='human-test', trace_id=str(uuid4())))
    assert applied.success, applied
    assert applied.data['status'] == 'APPLIED'
    assert len([c for c in proposal['changes'] if c['object_type']=='HardwareNode']) == 5


def assert_saved(result):
    assert result.success, result


def test_expiry_model_change_and_risk_review():
    authority, context, question = setup_question()
    start = run(authority, lambda: conversation.begin('Kapazität bewerten', context)).data
    finding = AgentResponse(type='FINDING', title='Kapazität offen', text='Die maximale Rohbildrate ist noch nicht dimensioniert.', severity='WARNING').model_dump(mode='json', exclude_none=True)
    run(authority, lambda: conversation.record_event(start['run_id'], finding))
    run(authority, lambda: conversation.finish(start['run_id']))
    assert not run(authority, lambda: conversation.decide(finding['id'], 'ACCEPTED_RISK', '', True)).success
    assert run(authority, lambda: conversation.decide(finding['id'], 'ACCEPTED_RISK', 'Für den Strukturentwurf bewusst zurückgestellt.', True)).success
    from backend.engineering.repository import create_object
    assert run(authority, lambda: create_object('HardwareNode', {'name':'Review change', 'device_type':'ECU'})).success
    state = run(authority, conversation.inspect).data
    assert state['decisions'][finding['id']]['status'] == 'NEEDS_REVIEW'
    assert state['questions'][question['id']]['status'] == 'OUTDATED'
    authority, context, question = setup_question()
    def expire():
        state = conversation.read()
        state['questions'][question['id']]['expires_at'] = '2000-01-01T00:00:00+00:00'
        conversation.write(state)
    run(authority, expire)
    assert run(authority, conversation.inspect).data['questions'][question['id']]['status'] == 'EXPIRED'


def test_history_merge_recovery_and_project_isolation():
    authority, context, question = setup_question()
    restored = run(authority, conversation.history).data
    assert restored['messages'][0]['parts'][0]['data']['question']['id'] == question['id']
    a = {'id':'browser-a','role':'user','parts':[{'type':'text','text':'Browser A'}]}
    b = {'id':'browser-b','role':'user','parts':[{'type':'text','text':'Browser B'}]}
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda message:run(authority, lambda: conversation.history([message])), [a,b]))
    assert all(result.success for result in results)
    merged = run(authority, conversation.history).data['messages']
    assert {'browser-a','browser-b'} <= {m['id'] for m in merged}
    other = ToolAuthority(f'other-chat-{uuid4()}')
    assert run(other, conversation.history).data['messages'] == []
    assert not run(other, lambda: conversation.response_detail(question['id'])).success


def test_large_response_is_loaded_in_workspace():
    authority = ToolAuthority(f'chat-details-{uuid4()}')
    context = AgentContext(active_project_id=authority.project_id)
    start = run(authority, lambda: conversation.begin('Analyse',context)).data
    event = AgentResponse(type='RESULT',text='Analyse '*200,metadata={'details':{'rows':list(range(1000))}}).model_dump(mode='json',exclude_none=True)
    compact = run(authority, lambda: conversation.record_event(start['run_id'], event)).data
    assert len(compact['text']) == 700
    assert 'details' not in compact['metadata']
    detail = run(authority, lambda: conversation.response_detail(compact['metadata']['detail_id'])).data
    assert detail == event
    run(authority, lambda: conversation.finish(start['run_id']))


def test_answer_preserves_workload_and_finding_action_is_structured():
    authority, context, question = setup_question()
    def workload_state():
        state = conversation.read()
        state['active_workload'] = 'existing-workload'
        conversation.write(state)
    run(authority, workload_state)
    started = run(authority, lambda: conversation.begin('', context, {'question_id':question['id'], 'selected_options':['a']})).data
    assert started['context']['current_workload'] == 'existing-workload'
    finding = AgentResponse(type='FINDING', text='Empfänger fehlt.').model_dump(mode='json',exclude_none=True)
    run(authority, lambda: conversation.record_event(started['run_id'], finding))
    run(authority, lambda: conversation.finish(started['run_id']))
    action = run(authority, lambda: conversation.begin('', context, {'type':'FINDING_ACTION', 'finding_id':finding['id']}))
    assert action.success and 'Empfänger fehlt.' in action.data['prompt']
    run(authority, lambda: conversation.finish(action.data['run_id']))


def test_human_edit_creates_new_validated_revision_and_survives_reload():
    from backend.app import create_app
    from backend.engineering.agent_tools.services import TOOLS
    authority = ToolAuthority(f'chat-edit-{uuid4()}')
    made = execute(authority,'generate_functions',Permission.GENERATE_PROPOSAL,{'prompt':'Erzeuge eine Funktion zur Temperaturüberwachung.',
        'new_hardware': {'name': 'ThermalController', 'device_type': 'EmbeddedController'},
        'status_technology': 'Ethernet', 'status_cycle_ms': 100},TOOLS['generate_functions'].handler)
    assert made.success, made
    proposal = run(authority, lambda: proposal_service.validate(made.data['proposal_id'])).data
    function = next(change for change in proposal['changes'] if change['object_type']=='Function')
    client = create_app(testing=True).test_client()
    headers = {'X-Project-ID':authority.project_id}
    path = f"/api/engineering/agent/proposals/{proposal['proposal_id']}"
    payload = {'revision':proposal['revision'], 'names':{function['local_ref']:'Geprüfte Temperaturfunktion'}, 'rationale':'Benennung präzisiert.'}
    assert client.post(path+'/revise',headers=headers,json=payload).status_code == 403
    csrf = client.get('/api/engineering/agent/review-session').json['csrf_token']
    headers.update({'X-Review-CSRF':csrf, 'X-Human-Review':'confirmed'})
    revised = client.post(path+'/revise',headers=headers,json=payload)
    assert revised.status_code == 200, revised.json
    assert revised.json['data']['status'] == 'VALIDATED'
    assert revised.json['data']['validation_result']['validation_scope'] == 'MODEL_STRUCTURE'
    assert revised.json['data']['validation_result']['capacity_status'] == 'UNVERIFIED'
    assert revised.json['data']['proposal_id'] != proposal['proposal_id']
    assert client.get(path,headers=headers).json['data']['proposal_id'] == revised.json['data']['proposal_id']
    assert client.post(path+'/review',headers=headers,json={'revision':proposal['revision'],'decision':'approve'}).status_code == 409


def test_explicit_single_function_keeps_quantity_and_generator_workflow():
    from backend.engineering.repository import create_object
    authority = ToolAuthority(f'chat-function-count-{uuid4()}')
    hardware = run(authority, lambda: create_object('HardwareNode', {
        'name': 'VisionController', 'device_type': 'EmbeddedController'})).data
    async def generate():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAgent(client).run('Erzeuge 1 Funktion für eine 360 Grad Kamera.',
                AgentContext(active_project_id=authority.project_id,
                             selected_object_refs=[{'object_type': 'HardwareNode', 'id': str(hardware['id'])}]))
    result = asyncio.run(generate())
    assert result['status'] == 'READY_FOR_REVIEW'
    assert not any(event.get('question') for event in result['events'])
    assert len([change for change in result['proposals'][0]['changes'] if change['object_type']=='Function']) == 1


def test_function_without_controller_exposes_concrete_missing_assignment():
    authority = ToolAuthority(f'chat-function-no-controller-{uuid4()}')
    prompt = 'Erzeuge 1 Funktion für eine 360 Grad Kamera.'
    async def generate():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAgent(client).run(prompt, AgentContext(active_project_id=authority.project_id))
    result = asyncio.run(generate())
    assert result['status'] == 'INCOMPLETE'
    assert not result['proposals']
    finding = next(event for event in result['events'] if event['type'] == 'FINDING')
    assert finding['metadata']['missing_fields'] == ['hardware_id']
    assert finding['metadata']['requirement'] == prompt
    assert finding['actions'][0]['capability_id'] == 'hardware'
    assert not any(trace['tool'] == 'generate_functions' for trace in result['trace'])


def test_optional_mcp_question_can_be_skipped_and_resumed():
    from backend.engineering.agent_tools.services import TOOLS
    authority = ToolAuthority(f'optional-question-{uuid4()}')
    context = AgentContext(active_project_id=authority.project_id)
    started = run(authority, lambda: conversation.begin('Optionale Darstellung',context)).data
    args = {'question_id':'format', 'question':'Welche Darstellung?', 'multiple':False,
        'required':False, 'engineering_impact':'OPTIONAL', 'options':[{'id':'short','label':'Kurz'},{'id':'detailed','label':'Ausführlich'}]}
    asked = execute(authority,'ask_engineering_question',Permission.READ_MODEL,args,TOOLS['ask_engineering_question'].handler)
    assert asked.success, asked
    event = asked.data['agent_response']
    run(authority, lambda: conversation.record_event(started['run_id'], event))
    run(authority, lambda: conversation.finish(started['run_id']))
    resumed = run(authority, lambda: conversation.begin('',context,{'type':'SKIP_QUESTION','question_id':event['question']['id']}))
    assert resumed.success, resumed
    assert resumed.data['context']['answered_questions']['format']['status'] == 'SKIPPED'
    run(authority, lambda: conversation.finish(resumed.data['run_id']))
