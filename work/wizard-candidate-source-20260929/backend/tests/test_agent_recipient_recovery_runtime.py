"""Real MCP failure recovery, durable proposal reuse and bounded retries."""
import asyncio
from copy import deepcopy
from uuid import uuid4

import pytest

from backend.agent_core.runtime.recovery import recipient_resume, recovery_request
from backend.agent_core.runtime.goal_resolver import RECIPIENT_REPAIR_OUTCOMES, GoalResolver
from backend.tests.test_agent_recipient_repair_runtime import PROMPT, sql_seed, scoped

RESUME = 'Setze den Auftrag nach einem kontrolliert transienten MCP/Core-Fehler fort.'


def context():
    return {'active_project_id': 'project', 'active_workload': {
        'workload_id': 'goal', 'project_id': 'project', 'status': 'BLOCKED_WITH_EXPLICIT_CAUSE',
        'goal': {'goal_id': 'goal', 'goal_type': 'REPAIR', 'original_request': PROMPT,
                 'project_context': {'project_id': 'project'}, 'required_outcomes': RECIPIENT_REPAIR_OUTCOMES},
        'failure': {'code': 'ENGINEERING_EXECUTION_TIMEOUT', 'category': 'TRANSIENT_TIMEOUT', 'retryable': True},
        'result': {}}}


@pytest.mark.parametrize('text', [RESUME, RESUME.lower(), 'Bitte ' + RESUME.lower(),
                                    'Setze den Auftrag fort.', 'Setze diesen Auftrag fort.'])
def test_explicit_resume_keeps_original_goal_and_bounds_attempts(text):
    saved = context(); before = deepcopy(saved)
    result = recipient_resume(text, saved)
    assert result['source_workload_id'] == 'goal' and result['original_request'] == PROMPT
    assert result['request'] == text and result['attempt_count'] == 1
    assert result['max_attempts'] == 2 and result['blocked'] is False
    assert saved == before
    assert GoalResolver().resolve(text).goal_type.value == 'REPAIR'


@pytest.mark.parametrize('text', ['Setze den Auftrag nicht fort.', RESUME + ' Lösche alles.',
    'Wie setze ich den Auftrag fort?', 'Erkläre den Fehler.', 'Starte einen neuen Auftrag.'])
def test_other_or_negated_requests_do_not_resume(text):
    assert not recovery_request(text)
    assert recipient_resume(text, context()) is None


@pytest.mark.parametrize('case', ['foreign-project', 'foreign-goal-project', 'other-id', 'closed',
    'other-goal', 'missing-failure', 'unknown-failure', 'authorization', 'not-retryable',
    'wrong-outcomes', 'open-question', 'wizard', 'negative-count', 'boolean-count', 'foreign-counter'])
def test_invalid_or_unsupported_recovery_context_is_rejected(case):
    c = context(); w = c['active_workload']
    if case == 'foreign-project': c['active_project_id'] = 'foreign'
    if case == 'foreign-goal-project': w['goal']['project_context']['project_id'] = 'foreign'
    if case == 'other-id': w['workload_id'] = 'other'
    if case == 'closed': w['status'] = 'COMPLETED'
    if case == 'other-goal': w['goal']['goal_type'] = 'CREATE_HARDWARE'
    if case == 'missing-failure': w['failure'] = None
    if case == 'unknown-failure': w['failure']['code'] = 'UNKNOWN'
    if case == 'authorization': w['failure']['category'] = 'AUTHORIZATION'
    if case == 'not-retryable': w['failure']['retryable'] = False
    if case == 'wrong-outcomes': w['goal']['required_outcomes'] = ['anything']
    if case == 'open-question': c['pending_decisions'] = [{'status': 'OPEN'}]
    if case == 'wizard': c['wizard_request'] = {'target': 'routing'}
    if case in {'negative-count', 'boolean-count', 'foreign-counter'}:
        w['result']['recovery'] = {'attempt_count': -1 if case == 'negative-count' else True if case == 'boolean-count' else 1,
                                  'source_workload_id': 'foreign' if case == 'foreign-counter' else 'goal', 'project_id': 'project'}
    assert recipient_resume(RESUME, c) is None


def test_exhausted_recovery_retains_identity_without_increasing_limit():
    c = context(); c['active_workload']['result']['recovery'] = {
        'attempt_count': 2, 'source_workload_id': 'goal', 'project_id': 'project'}
    result = recipient_resume(RESUME, c)
    assert result['blocked'] and result['attempt_count'] == result['max_attempts'] == 2
    assert result['source_workload_id'] == 'goal'


def seed():
    from backend.engineering.repository import delete_object
    authority, ids = sql_seed()
    def unique():
        delete_object('Signal', ids['unknown-signal'])
        delete_object('Message', ids['unknown-message'])
    scoped(authority, unique)
    return authority, ids


def run(authority, request, fault=None):
    from backend.agent_core.api.mcp_client import EngineeringMCPClient
    from backend.agent_core.context.agent_context import AgentContext
    from backend.agent_core.runtime.service import EngineeringAssistantService
    from backend.engineering.agent_tools import conversation
    from backend.simulator_engineering_mcp.server import create_server
    started = scoped(authority, lambda: conversation.begin(request, AgentContext(active_project_id=authority.project_id)))
    saved = scoped(authority, conversation.read); run_id = started['run_id']; calls = []
    def persist(row): scoped(authority, lambda: conversation.save_runtime_workload(run_id, row))
    def emit(event):
        if event.get('id'): scoped(authority, lambda: conversation.record_event(run_id, event))
    class NoReasoner:
        async def next(self, *args): raise AssertionError('Registered recovery must not use a generic planner.')
    class Client:
        def __init__(self, inner): self.inner = inner; self.injected = False
        async def tools(self): return await self.inner.tools()
        async def call(self, name, arguments):
            supplied = dict(arguments)
            if fault == 'precondition' and name == 'prepare_signal_recipient_repair' and not self.injected:
                self.injected = True; supplied['expected_model_revision'] = 'controlled-stale-revision'
            response = await self.inner.call(name, supplied)
            calls.append((name, response.status.value))
            selected = ('validate_proposal' if fault == 'lost-validation-response' else
                        'prepare_signal_recipient_repair' if fault == 'lost-prepare-response' else 'inspect_signal_recipients')
            if fault in {'lost-validation-response', 'lost-prepare-response', 'lost-inspection-response'} and name == selected and not self.injected:
                assert response.success; self.injected = True
                # The actual core response was successful; its delivery is lost.
                await asyncio.wait_for(asyncio.Event().wait(), timeout=0.01)
            return response
    async def invoke():
        async with EngineeringMCPClient(create_server(authority)) as inner:
            return await EngineeringAssistantService(Client(inner), reasoner=NoReasoner(), persist=persist).execute(
                request, AgentContext.model_validate(started['context']), saved_state=saved, emit=emit)
    try:
        if fault and fault.startswith('lost-'):
            with pytest.raises((TimeoutError, ExceptionGroup)) as caught:
                asyncio.run(invoke())
            def leaves(error):
                if isinstance(error, BaseExceptionGroup):
                    return [leaf for child in error.exceptions for leaf in leaves(child)]
                return [error]
            assert all(isinstance(error, TimeoutError) for error in leaves(caught.value))
            return None, calls
        return asyncio.run(invoke()), calls
    finally:
        scoped(authority, lambda: conversation.finish(run_id))


def workload(authority):
    from backend.engineering.agent_tools import conversation
    state = scoped(authority, conversation.read)
    return state['engineering_workloads'][state['active_engineering_workload_id']]


def audit_counts(authority):
    from collections import Counter
    from backend.engineering.agent_tools import audit
    return Counter((r['tool_name'], r['status']) for r in scoped(authority, lambda: audit.events(500)) if r['event_type'] == 'TOOL_CALL')


@pytest.mark.parametrize('fault', ['lost-validation-response', 'lost-prepare-response', 'precondition'])
def test_sql_recovery_uses_real_completed_steps_and_applies_same_workload_once(fault):
    from backend.engineering.agent_tools import model, proposal_service, conversation
    authority, ids = seed(); before = scoped(authority, model.model)
    run(authority, PROMPT, fault)
    failed = workload(authority)
    assert failed['status'] == 'BLOCKED_WITH_EXPLICIT_CAUSE'
    category = 'PRECONDITION' if fault == 'precondition' else 'TRANSIENT_TIMEOUT'
    assert failed['failure']['category'] == category
    assert scoped(authority, model.model) == before
    first_counts = audit_counts(authority)
    result, calls = run(authority, RESUME)
    assert result['runtime']['status'] == 'READY_FOR_REVIEW', result['events']
    current = workload(authority); recovery = current['result']['recovery']
    assert current['workload_id'] == failed['workload_id']
    assert current['created_at'] == failed['created_at']
    assert recovery['request'] == RESUME and recovery['previous_failure']['category'] == category
    assert recovery['attempt_count'] == 1 and recovery['preconditions_rechecked'] is True
    assert recovery['precondition_repaired'] is (fault == 'precondition')
    expected = [] if fault == 'precondition' else ['prepare_signal_recipient_repair']
    if fault == 'lost-validation-response': expected.append('validate_proposal')
    assert recovery['completed_steps_reused'] == expected
    for tool in expected:
        assert tool not in [name for name, _ in calls]
        assert audit_counts(authority)[tool, 'SUCCESS'] == first_counts[tool, 'SUCCESS'] == 1
    proposal = result['proposals'][0]
    if expected: assert proposal['proposal_id'] == failed['recipient_repair']['proposal_id']
    assert scoped(authority, model.model) == before
    def apply():
        proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='human-test', trace_id=uuid4().hex)
        applied = proposal_service.apply(proposal['proposal_id'], actor='human-test', trace_id=uuid4().hex)
        assert conversation.reconcile_runtime_model_apply(applied)
    scoped(authority, apply)
    completed = workload(authority)
    assert completed['status'] == 'COMPLETED'
    assert completed['result']['recovery'] == recovery
    assert completed['result']['recipient_revalidation']['repairable_signal_ids'] == []
    assert completed['result']['dependent_results']['capacity_snapshot_id']
    assert completed['result']['dependent_results']['preflight_snapshot_id']
    assert len(scoped(authority, model.routes)) == 1


def test_sql_retry_limit_persists_and_never_repeats_completed_mutation():
    from backend.engineering.agent_tools import model
    authority, _ = seed(); run(authority, PROMPT, 'lost-validation-response')
    identifier = workload(authority)['workload_id']
    for count in [1, 2]:
        run(authority, RESUME, 'lost-inspection-response')
        assert workload(authority)['workload_id'] == identifier
        assert workload(authority)['result']['recovery']['attempt_count'] == count
    for _ in range(2):
        result, _ = run(authority, RESUME)
        assert result['runtime']['status'] == 'BLOCKED_WITH_EXPLICIT_CAUSE'
        assert workload(authority)['workload_id'] == identifier
        assert workload(authority)['result']['recovery']['attempt_count'] == 2
    counts = audit_counts(authority)
    assert counts['prepare_signal_recipient_repair', 'SUCCESS'] == counts['validate_proposal', 'SUCCESS'] == 1
    assert not scoped(authority, model.routes)


@pytest.mark.parametrize('change', ['model-revision', 'proposal-rejected', 'unknown-failure'])
def test_sql_recovery_rejects_stale_or_unsupported_saved_execution(change):
    from backend.engineering.agent_tools import model, proposal_service, conversation
    from backend.engineering.repository import update_object
    authority, ids = seed(); run(authority, PROMPT, 'lost-validation-response')
    old = workload(authority)
    def alter():
        if change == 'model-revision': update_object('Signal', ids['signal'], {'name': 'Changed scope'})
        elif change == 'proposal-rejected':
            p = proposal_service.get(old['recipient_repair']['proposal_id'])
            proposal_service.review(p['proposal_id'], revision=p['revision'], decision='reject', actor='human-test', trace_id=uuid4().hex)
        else:
            state = conversation.read(); state['engineering_workloads'][old['workload_id']]['failure']['code'] = 'UNKNOWN'; conversation.write(state)
    scoped(authority, alter)
    before = scoped(authority, model.model); counts = audit_counts(authority)
    result, _ = run(authority, RESUME)
    assert result['runtime']['status'] not in {'READY_FOR_REVIEW', 'COMPLETED'}
    assert not result['proposals']
    assert scoped(authority, model.model) == before
    assert audit_counts(authority)['prepare_signal_recipient_repair', 'SUCCESS'] == counts['prepare_signal_recipient_repair', 'SUCCESS']
