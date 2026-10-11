"""Recipient scan boundaries and real project-scoped proposal persistence."""
import asyncio
from copy import deepcopy
from uuid import uuid4

import pytest

from backend.agent_core.runtime.goal_resolver import GoalResolver, recipient_repair_intent, RECIPIENT_REPAIR_OUTCOMES
from backend.engineering.communication_repair import RepairPlanner, KINDS
from backend.engineering.communication_contract_repair import scan_signal_recipients
from backend.tests.test_communication_repair import sample

PROMPT = 'Finde alle Signale ohne Empfänger und korrigiere die eindeutigen Fälle.'


def fixture():
    state, objects, _, history = sample()
    message = objects['Message'][0]
    message['hardware_interface_id'] = 'producer-port'
    message['configuration']['communication_contract'] = {'scope': 'FUNCTION_OUTPUT', 'consumer_refs': ['receiver-function']}
    unknown = deepcopy(message)
    unknown.update(id='unknown-message', name='Unknown recipient', message_id_hex='0x101')
    unknown['configuration']['communication_contract']['consumer_refs'] = []
    objects['Message'].append(unknown)
    objects['Signal'].append({**objects['Signal'][0], 'id': 'unknown-signal', 'name': 'Unknown signal', 'message_id': unknown['id']})
    return state, objects, [], history


def scan(data):
    # This unit boundary isolates scan decisions; SQL tests use the real validator.
    return scan_signal_recipients(RepairPlanner(*data), lambda _: {'valid': True})


@pytest.mark.parametrize('text', [PROMPT, PROMPT.lower(), 'Bitte ' + PROMPT.lower(),
    PROMPT.replace('Finde', 'Suche').replace('korrigiere', 'repariere nur')])
def test_recipient_request_preserves_full_quality_outcomes(text):
    assert recipient_repair_intent(text)
    assert GoalResolver().resolve(text).required_outcomes == RECIPIENT_REPAIR_OUTCOMES


@pytest.mark.parametrize('text', [PROMPT + ' Lösche die anderen.', PROMPT.replace('korrigiere', 'korrigiere nicht'),
    PROMPT.replace('alle', 'keine'), PROMPT.replace('die eindeutigen', 'auch die mehrdeutigen'),
    'Wie finde ich Signale ohne Empfänger?', 'Repariere das Netzwerk.'])
def test_recipient_request_does_not_authorize_mixed_negated_or_generic_commands(text):
    assert not recipient_repair_intent(text)


def test_scan_all_signals_and_only_declared_unique_recipient_path_without_mutation():
    data = fixture(); before = deepcopy(data)
    result = scan(data)
    assert set(result['scanned_signal_ids']) == {'signal', 'unknown-signal'}
    assert result['repairable_signal_ids'] == ['signal']
    assert result['review_required_signal_ids'] == ['unknown-signal']
    assert len(result['changes']) == 1
    route = result['changes'][0]['data']
    assert route['payload'] == {'message_ids': ['message'], 'signal_ids': ['signal']}
    assert route['destinations'][0]['interface_id'] == 'receiver-interface'
    assert data == before


@pytest.mark.parametrize('case', ['unknown', 'foreign', 'disabled-message', 'disabled-signal', 'parallel-wire',
    'missing-wire', 'wrong-source-port', 'duplicate-interface', 'invalid-route'])
def test_uncertain_or_forbidden_recipient_never_becomes_a_repair(case):
    data = fixture(); state, objects, _, _ = data
    if case in {'unknown', 'foreign'}:
        objects['Message'][0]['configuration']['communication_contract']['consumer_refs'] = [] if case == 'unknown' else ['foreign']
    elif case.startswith('disabled'):
        objects['Message' if case.endswith('message') else 'Signal'][0].setdefault('configuration', {})['routing'] = {'enabled': False}
    elif case == 'parallel-wire':
        state['topology']['edges'].append({**state['topology']['edges'][0], 'id': 'another-wire'})
    elif case == 'missing-wire':
        state['topology']['edges'] = []
    elif case == 'wrong-source-port':
        objects['Message'][0]['hardware_interface_id'] = 'receiver-port'
    elif case == 'duplicate-interface':
        objects['Interface'].append({**objects['Interface'][1], 'id': 'receiver-other-interface'})
    if case == 'invalid-route':
        result = scan_signal_recipients(RepairPlanner(*data), lambda _: {'valid': False})
    else:
        result = scan(data)
    assert not result['changes']
    assert set(result['review_required_signal_ids']) == {'signal', 'unknown-signal'}


def test_existing_receiver_route_does_not_cover_another_declared_consumer():
    data = fixture(); state, objects, routes, history = data
    generated = scan(data)['changes'][0]['data']
    routes.append({**generated, 'id': 'existing', 'revision': 1})
    assert scan(data)['signals'][0]['status'] == 'COVERED'
    objects['Message'][0]['configuration']['communication_contract']['consumer_refs'].append('missing-consumer')
    result = scan(data)
    assert not result['changes'] and result['signals'][0]['status'] == 'REVIEW_REQUIRED'


def test_longer_alternative_path_is_not_hidden_by_shortest_path_selection():
    from backend.engineering.communication_contract_repair import _unique_path
    planner = RepairPlanner(*fixture())
    path = planner.paths('producer-port', 'receiver-port')[0]
    assert _unique_path(planner, path)
    planner.graph['producer-port'].append(('intermediate-port', 'branch-a'))
    planner.graph['intermediate-port'].append(('receiver-port', 'branch-b'))
    assert not _unique_path(planner, path)


def scoped(authority, operation, *, success=True):
    from backend.engineering.agent_tools.runtime import execute
    from backend.agent_core.api.tool_contract import Permission
    def invoke(_):
        try:
            return operation()
        except Exception:
            if success:
                import traceback
                traceback.print_exc()
            raise
    result = execute(authority, 'recipient-acceptance', Permission.GENERATE_PROPOSAL, {}, invoke)
    assert result.success is success, result.findings
    return result.data if success else result


def sql_seed():
    from backend.engineering.agent_tools.runtime import ToolAuthority
    from backend.engineering.repository import create_object
    from backend.engineering.workflow.service import WorkflowStatusService
    from backend.engineering.db import get_connection
    from psycopg.types.json import Jsonb
    authority = ToolAuthority('recipient-' + uuid4().hex)
    def seed():
        state, objects, _, _ = fixture(); ids = {}
        def mapped(value):
            if isinstance(value, dict): return {k: mapped(v) for k, v in value.items()}
            if isinstance(value, list): return [mapped(v) for v in value]
            return ids.get(value, value) if isinstance(value, str) else value
        for kind in KINDS:
            for obj in objects[kind]:
                data = mapped({k: v for k, v in obj.items() if k not in {'id', 'object_type', 'version'}})
                if kind == 'HardwareNode': data['identity'] = {}
                row = create_object(kind, data); ids[obj['id']] = str(row['id'])
        WorkflowStatusService(authority.project_id).get()
        with get_connection() as conn:
            conn.execute('UPDATE engineering_workflow_projects SET topology=%s, parameters=%s WHERE project_id=%s',
                (Jsonb(mapped(state['topology'])), Jsonb(state['parameters']), authority.project_id))
        return ids
    return authority, scoped(authority, seed)


def invoke(authority):
    from backend.agent_core.api.mcp_client import EngineeringMCPClient
    from backend.agent_core.context.agent_context import AgentContext
    from backend.agent_core.runtime.service import EngineeringAssistantService
    from backend.engineering.agent_tools import conversation
    from backend.simulator_engineering_mcp.server import create_server
    run_id = uuid4().hex
    def initialize():
        state = conversation.read(); state['run_id'] = run_id; conversation.write(state)
    scoped(authority, initialize)
    class NoReasoner:
        async def next(self, *args):
            raise AssertionError('Explicit recipient-quality request must use canonical tools.')
    def persist(row):
        scoped(authority, lambda: conversation.save_runtime_workload(run_id, row))
    async def run():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAssistantService(client, reasoner=NoReasoner(), persist=persist).execute(
                PROMPT, AgentContext(active_project_id=authority.project_id))
    return asyncio.run(run())


def test_sql_original_request_real_scan_and_reviewed_route_persistence():
    from backend.engineering.agent_tools import conversation, model, proposal_service
    authority, ids = sql_seed()
    before = scoped(authority, model.model)
    result = invoke(authority)
    assert result['runtime']['status'] == 'READY_FOR_REVIEW', result['events']
    summary = next(event for event in result['events'] if event['type'] == 'RESULT')
    assert 'Unknown signal' in summary['text'] and 'Offene Empfänger' in summary['text']
    assert any(item.get('review_required') for item in summary['findings'])
    proposal = result['proposals'][0]
    assert scoped(authority, model.routes) == []
    def apply():
        proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='human-test', trace_id=uuid4().hex)
        applied = proposal_service.apply(proposal['proposal_id'], actor='human-test', trace_id=uuid4().hex)
        assert conversation.reconcile_runtime_model_apply(applied)
        return applied
    applied = scoped(authority, apply)
    after = scoped(authority, model.model)
    assert len(after['routing']) == 1
    for key in ['hardware', 'functions', 'interfaces', 'hardware-interfaces', 'messages', 'signals']:
        assert after[key] == before[key], key
    work = scoped(authority, conversation.read)['engineering_workloads'][result['runtime']['workload_id']]
    assert work['status'] == 'COMPLETED'
    for signal in work['result']['recipient_revalidation']['signals']:
        assert len(signal['route_ids']) == len(set(signal['route_ids']))
    assert work['result']['recipient_revalidation']['review_required_signal_ids'] == [ids['unknown-signal']]
    assert work['result']['dependent_results']['preflight_snapshot_id']
    scoped(authority, lambda: proposal_service.apply(applied['proposal_id'], actor='human-test', trace_id=uuid4().hex))
    assert len(scoped(authority, model.routes)) == 1


@pytest.mark.parametrize('change', ['foreign-project', 'stale-revision', 'negated-goal', 'wrong-owner'])
def test_sql_recipient_tools_reject_wrong_scope_or_changed_request(change):
    from backend.engineering.agent_tools import conversation, repair_execution, model
    from backend.engineering.agent_tools.runtime import ToolAuthority
    authority, _ = sql_seed()
    result = invoke(authority)
    goal_id = result['runtime']['workload_id']
    def wrong():
        state = conversation.read()
        if change == 'negated-goal': state['engineering_workloads'][goal_id]['goal']['original_request'] = 'Korrigiere nichts.'
        if change == 'wrong-owner': state['run_id'] = 'other'
        conversation.write(state)
    if change in {'negated-goal', 'wrong-owner'}: scoped(authority, wrong)
    if change == 'foreign-project': authority = ToolAuthority('recipient-other-' + uuid4().hex)
    revision = 'stale' if change == 'stale-revision' else scoped(authority, model.model_revision)
    scoped(authority, lambda: repair_execution.prepare_recipients({'workload_id': goal_id, 'expected_model_revision': revision}), success=False)


def test_sql_repeat_prepare_reuses_proposal_and_keeps_canonical_model_untouched():
    from backend.engineering.agent_tools import model, repair_execution
    authority, _ = sql_seed(); result = invoke(authority)
    before = scoped(authority, model.model)
    prepared = scoped(authority, lambda: repair_execution.prepare_recipients({
        'workload_id': result['runtime']['workload_id'], 'expected_model_revision': model.model_revision()}))
    assert prepared['proposal']['proposal_id'] == result['proposals'][0]['proposal_id']
    assert scoped(authority, model.model) == before


def test_sql_changed_recipient_after_review_rejects_apply_without_canonical_mutation():
    from backend.engineering.agent_tools import model, proposal_service
    from backend.engineering.repository import get_object, update_object
    authority, ids = sql_seed(); proposal = invoke(authority)['proposals'][0]
    scoped(authority, lambda: proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='human-test', trace_id=uuid4().hex))
    def change():
        message = get_object('Message', ids['message'])
        config = deepcopy(message['configuration']); config['communication_contract']['consumer_refs'] = []
        update_object('Message', ids['message'], {'configuration': config})
    scoped(authority, change)
    before = scoped(authority, model.model)
    rejected = scoped(authority, lambda: proposal_service.apply(proposal['proposal_id'], actor='human-test', trace_id=uuid4().hex))
    assert rejected['status'] == 'OUTDATED' and not rejected['canonical_ids']
    assert scoped(authority, model.model) == before


def test_sql_forged_recipient_change_rejected_by_current_scan():
    from backend.engineering.agent_tools import repair_execution
    authority, _ = sql_seed(); proposal = invoke(authority)['proposals'][0]
    forged = deepcopy(proposal['changes']); forged[0]['data']['timing']['cycle_time_ms'] = 999
    scoped(authority, lambda: repair_execution.validate_recipient_changes(forged), success=False)


def test_sql_failed_dependent_check_rolls_back_reviewed_route_apply(monkeypatch):
    from backend.engineering.agent_tools import conversation, model, proposal_service
    from backend.engineering.capacity.service import PreflightService
    authority, _ = sql_seed(); proposal = invoke(authority)['proposals'][0]
    scoped(authority, lambda: proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='human-test', trace_id=uuid4().hex))
    before = scoped(authority, model.model)
    def fail(*args, **kwargs): raise RuntimeError('Injected assessment failure')
    monkeypatch.setattr(PreflightService, 'run', fail)
    def apply():
        applied = proposal_service.apply(proposal['proposal_id'], actor='human-test', trace_id=uuid4().hex)
        conversation.reconcile_runtime_model_apply(applied)
    scoped(authority, apply, success=False)
    assert scoped(authority, model.model) == before
    assert scoped(authority, lambda: proposal_service.get(proposal['proposal_id']))['status'] == 'APPROVED'


def test_sql_all_unknown_receivers_complete_the_scan_with_open_findings_and_no_repair():
    from backend.engineering.agent_tools import conversation, model
    from backend.engineering.repository import get_object, update_object
    authority, ids = sql_seed()
    def change():
        message = get_object('Message', ids['message'])
        config = deepcopy(message['configuration']); config['communication_contract']['consumer_refs'] = []
        update_object('Message', ids['message'], {'configuration': config})
    scoped(authority, change); before = scoped(authority, model.model)
    result = invoke(authority)
    assert result['runtime']['status'] == 'COMPLETED' and not result['proposals']
    work = scoped(authority, conversation.read)['engineering_workloads'][result['runtime']['workload_id']]
    assert set(work['recipient_repair']['review_required_signal_ids']) == {ids['signal'], ids['unknown-signal']}
    assert scoped(authority, model.model) == before
