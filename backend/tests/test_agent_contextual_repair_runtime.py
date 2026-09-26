"""Contextual repair uses a real prior finding and the existing review boundary."""
import asyncio
from copy import deepcopy
from uuid import uuid4

import pytest

from backend.agent_core.runtime.goal_resolver import (
    RECIPIENT_REPAIR_OUTCOMES, contextual_repair_intent, recipient_repair_followup,
)
from backend.tests.test_agent_recipient_repair_runtime import PROMPT, sql_seed, scoped, invoke

FOLLOWUP = 'Dann weißt du ja, was du zu tun hast, Fehleranalyse und Korrektur.'


def saved_context():
    finding = {'code': 'SIGNAL_DECLARED_RECIPIENT_UNROUTED', 'status': 'REPAIRABLE',
               'review_required': False, 'signal_id': 'signal', 'message_id': 'message'}
    return {'active_project_id': 'project', 'active_workload': {
        'workload_id': 'goal', 'project_id': 'project', 'status': 'READY_FOR_REVIEW',
        'goal': {'goal_id': 'goal', 'goal_type': 'REPAIR', 'original_request': PROMPT,
                 'required_outcomes': RECIPIENT_REPAIR_OUTCOMES},
        'recipient_repair': {'project_id': 'project', 'proposal_id': 'proposal',
            'model_revision': 'revision', 'findings': [finding],
            'repairable_signal_ids': ['signal'], 'review_required_signal_ids': []}}}


@pytest.mark.parametrize('text', [FOLLOWUP, FOLLOWUP.lower(), 'Bitte ' + FOLLOWUP.lower(),
    FOLLOWUP.replace('weißt', 'weisst')])
def test_contextual_repair_preserves_original_scope_and_actual_followup(text):
    context = saved_context(); before = deepcopy(context)
    resumed = recipient_repair_followup(text, context)
    assert resumed['source_workload_id'] == 'goal'
    assert resumed['original_request'] == PROMPT and resumed['request'] == text
    assert context == before


@pytest.mark.parametrize('text', [FOLLOWUP + ' Lösche die anderen.',
    FOLLOWUP.replace('Korrektur', 'keine Korrektur'), 'Was bedeutet Fehleranalyse und Korrektur?',
    'Repariere alles.', FOLLOWUP.replace('Dann', 'Nicht')])
def test_mixed_negated_and_other_inputs_do_not_authorize_context_repair(text):
    assert not contextual_repair_intent(text)
    assert recipient_repair_followup(text, saved_context()) is None


@pytest.mark.parametrize('case', ['foreign-project', 'foreign-scan', 'closed', 'missing-goal',
    'other-goal', 'wrong-outcomes', 'no-proposal', 'no-revision', 'multiple-findings',
    'unknown-finding', 'review-required', 'expanded-scope', 'open-question', 'wizard'])
def test_ambiguous_or_inconsistent_context_is_not_resumed(case):
    c = saved_context(); w = c['active_workload']; scan = w['recipient_repair']
    if case == 'foreign-project': c['active_project_id'] = 'other'
    if case == 'foreign-scan': scan['project_id'] = 'other'
    if case == 'closed': w['status'] = 'COMPLETED'
    if case == 'missing-goal': w['goal']['goal_id'] = 'other'
    if case == 'other-goal': w['goal']['goal_type'] = 'DIAGNOSE'
    if case == 'wrong-outcomes': w['goal']['required_outcomes'] = ['anything']
    if case == 'no-proposal': scan['proposal_id'] = None
    if case == 'no-revision': scan['model_revision'] = None
    if case == 'multiple-findings': scan['findings'] *= 2
    if case == 'unknown-finding': scan['findings'][0]['code'] = 'UNKNOWN'
    if case == 'review-required': scan['findings'][0]['review_required'] = True
    if case == 'expanded-scope': scan['repairable_signal_ids'].append('other')
    if case == 'open-question': c['pending_decisions'] = [{'status': 'OPEN'}]
    if case == 'wizard': c['wizard_request'] = {'target': 'routing'}
    assert recipient_repair_followup(FOLLOWUP, c) is None


def unique_seed():
    from backend.engineering.repository import delete_object
    from backend.engineering.agent_tools import conversation
    authority, ids = sql_seed()
    def remove_unknown():
        delete_object('Signal', ids['unknown-signal'])
        delete_object('Message', ids['unknown-message'])
    scoped(authority, remove_unknown)
    first = invoke(authority)
    assert first['runtime']['status'] == 'READY_FOR_REVIEW'
    def persist_events():
        run_id = conversation.read()['run_id']
        for event in first['events']:
            conversation.record_event(run_id, event)
        conversation.finish(run_id)
    scoped(authority, persist_events)
    return authority, ids, first


def followup(authority, *, saved=None):
    from backend.agent_core.api.mcp_client import EngineeringMCPClient
    from backend.agent_core.context.agent_context import AgentContext
    from backend.agent_core.runtime.service import EngineeringAssistantService
    from backend.engineering.agent_tools import conversation
    from backend.simulator_engineering_mcp.server import create_server
    started = scoped(authority, lambda: conversation.begin(FOLLOWUP, AgentContext(active_project_id=authority.project_id)))
    state = scoped(authority, conversation.read) if saved is None else saved
    run_id = started['run_id']
    assert scoped(authority, conversation.read)['active_proposal'] is None
    class NoReasoner:
        async def next(self, *args):
            raise AssertionError('A bounded contextual repair must not be reinterpreted by a reasoner.')
    def persist(row):
        scoped(authority, lambda: conversation.save_runtime_workload(run_id, row))
    async def run():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAssistantService(client, reasoner=NoReasoner(), persist=persist).execute(
                FOLLOWUP, AgentContext.model_validate(started['context']), saved_state=state)
    return asyncio.run(run())


def test_sql_original_followup_reuses_workload_proposal_and_revalidates_actual_apply():
    from backend.engineering.agent_tools import conversation, model, proposal_service
    authority, ids, first = unique_seed()
    before = scoped(authority, model.model)
    result = followup(authority)
    assert result['runtime']['status'] == 'READY_FOR_REVIEW', result['events']
    assert result['runtime']['workload_id'] == first['runtime']['workload_id']
    proposal = result['proposals'][0]
    assert proposal['proposal_id'] == first['proposals'][0]['proposal_id']
    assert not any(event['type'] == 'QUESTION' for event in result['events'])
    assert scoped(authority, model.model) == before
    state = scoped(authority, conversation.read)
    assert len(state['engineering_workloads']) == 1
    context = state['engineering_workloads'][result['runtime']['workload_id']]['result']['contextual_repair']
    assert context['finding']['signal_id'] == ids['signal'] and context['request'] == FOLLOWUP
    assert context['proposal_id'] == proposal['proposal_id']
    def apply():
        proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='human-test', trace_id=uuid4().hex)
        applied = proposal_service.apply(proposal['proposal_id'], actor='human-test', trace_id=uuid4().hex)
        assert conversation.reconcile_runtime_model_apply(applied)
        return applied
    applied = scoped(authority, apply)
    work = scoped(authority, conversation.read)['engineering_workloads'][result['runtime']['workload_id']]
    assert work['status'] == 'COMPLETED'
    assert work['result']['contextual_repair'] == context
    assert work['result']['recipient_revalidation']['repairable_signal_ids'] == []
    assert work['result']['dependent_results']['capacity_snapshot_id']
    assert work['result']['dependent_results']['preflight_snapshot_id']
    assert len(scoped(authority, model.routes)) == 1
    scoped(authority, lambda: proposal_service.apply(applied['proposal_id'], actor='human-test', trace_id=uuid4().hex))
    assert len(scoped(authority, model.routes)) == 1


@pytest.mark.parametrize('case', ['stale-model', 'review-candidate-withdrawn', 'ambiguous-context', 'foreign-context'])
def test_sql_followup_never_executes_changed_or_foreign_scope(case):
    from backend.engineering.agent_tools import conversation, model
    from backend.engineering.repository import update_object
    authority, ids, _ = unique_seed()
    saved = scoped(authority, conversation.read)
    work = saved['engineering_workloads'][saved['active_engineering_workload_id']]
    if case == 'stale-model':
        scoped(authority, lambda: update_object('Signal', ids['signal'], {'name': 'Changed after finding'}))
    elif case == 'review-candidate-withdrawn':
        def change():
            state = conversation.read(); state['pending_approvals'] = []; conversation.write(state)
        scoped(authority, change)
    elif case == 'ambiguous-context':
        work['recipient_repair']['findings'] *= 2
    elif case == 'foreign-context':
        work['project_id'] = 'other-project'
    before = scoped(authority, model.model)
    result = followup(authority, saved=saved)
    assert result['runtime']['status'] not in {'READY_FOR_REVIEW', 'COMPLETED'}
    assert not result['proposals']
    assert scoped(authority, model.model) == before
