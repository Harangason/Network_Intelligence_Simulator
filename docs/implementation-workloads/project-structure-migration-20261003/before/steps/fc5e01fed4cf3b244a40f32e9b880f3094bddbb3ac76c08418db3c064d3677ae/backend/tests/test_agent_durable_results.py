from uuid import uuid4

from backend.agent_core.api.agent_response import AgentResponse
from backend.agent_core.api.tool_contract import Permission
from backend.agent_core.context.agent_context import AgentContext
from backend.engineering.agent_tools import conversation
from backend.engineering.agent_tools.runtime import ToolAuthority, execute


def test_disconnected_result_reloads_once_and_stays_project_scoped():
    authority = ToolAuthority('durable-result-' + uuid4().hex)
    def call(fn):
        result = execute(authority, 'durable-result-test', Permission.READ_MODEL, {}, lambda _: fn())
        assert result.success, result.findings
        return result.data
    started = call(lambda: conversation.begin('Projekt prüfen', AgentContext(active_project_id=authority.project_id)))
    event = AgentResponse(type='RESULT', status='INCOMPLETE', text='Offene Angaben bleiben erhalten.').model_dump(mode='json')
    call(lambda: conversation.record_event(started['run_id'], event))
    call(lambda: conversation.finish(started['run_id']))
    restored = call(conversation.history)['messages']
    assert len(restored) == 1
    assert restored[0]['parts'][0]['data']['id'] == event['id']
    call(lambda: conversation.history(restored))
    original = {'id': 'stream-message', 'role': 'assistant', 'parts': [{'type': 'data-engineering', 'data': event}]}
    merged = call(lambda: conversation.history([original]))['messages']
    assert len(merged) == 1 and merged[0]['id'] == 'stream-message'
    other = ToolAuthority('other-' + uuid4().hex)
    assert execute(other, 'read', Permission.READ_MODEL, {}, lambda _: conversation.history()).data['messages'] == []
    assert call(lambda: conversation.history(clear=True))['messages'] == []
    assert call(conversation.history)['messages'] == []
