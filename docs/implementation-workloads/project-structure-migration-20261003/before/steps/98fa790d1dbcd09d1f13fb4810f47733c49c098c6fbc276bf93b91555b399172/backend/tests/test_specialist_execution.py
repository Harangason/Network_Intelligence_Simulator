"""Real execution boundary, constrained inference, isolation and visible failure."""
import json
import os
from copy import deepcopy

import pytest
import httpx

from backend.engineering.agent_tools import specialist


@pytest.fixture
def model(monkeypatch):
    records, requests = [], []
    monkeypatch.setattr(specialist, 'current_project_id', lambda: 'project-a')
    monkeypatch.setattr(specialist, 'record', lambda *args: records.append(args))
    real_client = httpx.Client
    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        candidates = json.loads(payload['messages'][1]['content'].removesuffix('\n/no_think'))['candidates']
        return httpx.Response(200, json={'message': {'content': json.dumps({'decisions': [
            {'id': str(item['id']), 'recommended': True, 'reason': 'Die expliziten Partner bleiben erhalten.'}
            for item in candidates], 'gaps': []})}})
    monkeypatch.setattr(specialist.httpx, 'Client', lambda **kwargs: real_client(transport=httpx.MockTransport(respond)))
    return requests, records


def test_model_reviews_all_candidates_with_project_context_and_audit(model):
    requests, records = model
    result = specialist.review_candidates('Kommunikation', [{'id': str(index)} for index in range(25)])
    assert len(requests) == 3 and len(result['decisions']) == 25
    assert result['status'] == 'REVIEWED' and result['model']
    assert all('project-a' in item['messages'][1]['content'] for item in requests)
    assert records[-1][2] == 'MODEL_REVIEW'


def test_duplicate_ids_never_reach_model(model):
    with pytest.raises(ValueError):
        specialist.review_candidates('test', [{'id': 'a'}, {'id': 'a'}])
    assert not model[0]


def test_large_candidates_split_without_losing_data():
    candidates = [{'id': str(index), 'evidence': 'x' * 21000} for index in range(3)]
    batches = list(specialist.candidate_batches(candidates))
    assert len(batches) == 3 and [item for batch in batches for item in batch] == candidates
    with pytest.raises(ValueError):
        list(specialist.candidate_batches([{'id': 'large', 'evidence': 'x' * 41000}]))


def test_unknown_model_ids_are_rejected_and_not_disguised_as_ai(model, monkeypatch):
    monkeypatch.setattr(specialist.SpecialistDecision, 'model_validate_json', lambda _: specialist.SpecialistDecision(
        decisions=[specialist.CandidateDecision(id='invented', recommended=True, reason='invented')]))
    result = specialist.review_or_report('test', [{'id': 'real'}])
    assert result['status'] == 'UNAVAILABLE' and result['model'] is None and not result['decisions']


SQL = pytest.mark.skipif(not os.environ.get('ENGINEERING_TEST_DATABASE_URL'), reason='Isolated database required')


def test_contract_repair_uses_declared_consumers_without_previous_route():
    from backend.tests.test_communication_repair import sample
    from backend.engineering.communication_repair import RepairPlanner, complete_plan
    state, objects, _, history = sample()
    message = objects['Message'][0]
    message['configuration'] = {'communication_contract': {'scope': 'FUNCTION_OUTPUT', 'consumer_refs': ['receiver-function']}}
    plan = complete_plan(RepairPlanner(state, objects, [], history))
    group = plan['groups'][0]
    option = next(o for o in group['options'] if o.get('create_routes'))
    assert option['create_routes'][0]['data']['destinations'][0]['node_id'] == 'receiver'
    assert option['create_routes'][0]['data']['payload']['message_ids'] == [message['id']]
    message['configuration']['communication_contract']['consumer_refs'] = ['missing-consumer']
    blocked = complete_plan(RepairPlanner(state, objects, [], history))
    assert not blocked['groups'][0]['options']
    assert 'missing-consumer' in blocked['groups'][0]['reason']


@SQL
def test_contract_repair_creates_validated_route_with_original_payload(monkeypatch):
    from backend.tests.test_communication_repair import sql_sample
    from backend.engineering.repository import update_object
    from backend.engineering.routing.repository import delete_route
    from backend.engineering.project_context import activate_project
    client, ids = sql_sample()
    activate_project(client.environ_base['HTTP_X_PROJECT_ID'])
    delete_route(ids['route'])
    update_object('Message', ids['message'], {'configuration': {'communication_contract': {
        'scope': 'FUNCTION_OUTPUT', 'consumer_refs': [ids['receiver-function']]}}})
    base = '/api/engineering/workflow/communication-repair/'
    plan = client.post(base + 'preview', json={}).get_json()
    group = next(g for g in plan['groups'] if g['options'])
    response = client.post(base + 'apply', json={'workload_id': plan['workload_id'], 'token': plan['token'],
        'choices': {group['id']: group['options'][0]['id']}})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['applied'][0]['routes'] == 1
    assert response.get_json()['followup']['scope'] == 'INCLUDING_DRAFT_ROUTES'
    assert response.get_json()['followup']['provenance']['inputs']['routing_entries'] == 1
    from backend.engineering.routing.repository import list_routes
    active = [row for row in list_routes(limit=100) if row['status'] not in {'DEPRECATED', 'REJECTED', 'SUPERSEDED'}]
    assert len(active) == 1 and active[0]['validation']['valid']
    assert active[0]['payload']['message_ids'] == [ids['message']]
    assert active[0]['approval_state'] == 'PENDING'


@SQL
def test_repair_requires_human_choice_executes_and_is_idempotent(monkeypatch):
    from backend.tests.test_communication_repair import sql_sample
    from backend.engineering.agent_tools import repair_execution
    from backend.engineering.agent_tools.runtime import ToolAuthority
    from backend.engineering.agent_tools.services import TOOLS
    from backend.engineering.agent_tools.runtime import execute
    from backend.engineering.goal_execution.store import get_goal
    from backend.engineering.project_context import activate_project, reset_project
    monkeypatch.setattr(repair_execution, 'review_or_report', lambda *a: {'status': 'REVIEWED', 'model': 'test', 'decisions': [], 'gaps': []})
    client, ids = sql_sample()
    base = '/api/engineering/workflow/communication-repair/'
    plan = client.post(base + 'preview', json={}).get_json()
    tool = TOOLS['continue_communication_repair']
    authority = ToolAuthority(client.environ_base['HTTP_X_PROJECT_ID'])
    result = execute(authority, tool.name, tool.permission, {'workload_id': plan['workload_id']}, tool.handler)
    assert not result.success and result.status.value == 'PERMISSION_DENIED'
    group = plan['groups'][0]
    body = {'workload_id': plan['workload_id'], 'token': plan['token'], 'choices': {group['id']: group['options'][0]['id']}}
    response = client.post(base + 'apply', json=body)
    assert response.status_code == 200, response.get_json()
    applied = response.get_json()
    assert applied['applied']
    repeated = execute(authority, tool.name, tool.permission, {'workload_id': plan['workload_id']}, tool.handler)
    assert repeated.success and repeated.data == applied
    token = activate_project(authority.project_id)
    try:
        goal = get_goal(plan['workload_id'])
        assert goal['status'] == 'COMPLETE' and len(goal['journal']) == 1
    finally:
        reset_project(token)
    wrong = execute(ToolAuthority('other-project'), tool.name, tool.permission, {'workload_id': plan['workload_id']}, tool.handler)
    assert not wrong.success


@SQL
def test_repair_validation_failure_rolls_back_authority_and_writes(monkeypatch):
    from backend.tests.test_communication_repair import sql_sample
    from backend.engineering.agent_tools import repair_execution
    from backend.engineering.routing.validation import RoutingValidator
    monkeypatch.setattr(repair_execution, 'review_or_report', lambda *a: {'status': 'REVIEWED', 'model': 'test', 'decisions': [], 'gaps': []})
    client, ids = sql_sample()
    base = '/api/engineering/workflow/communication-repair/'
    plan = client.post(base + 'preview', json={}).get_json()
    before = client.get('/api/engineering/messages/' + ids['message']).get_json()
    group = plan['groups'][0]
    monkeypatch.setattr(RoutingValidator, 'validate', lambda *a, **k: {'valid': False, 'errors': [{'message': 'test failure'}]})
    result = client.post(base + 'apply', json={'workload_id': plan['workload_id'], 'token': plan['token'], 'choices': {group['id']: group['options'][0]['id']}})
    assert result.status_code == 400, result.get_json()
    assert client.get('/api/engineering/messages/' + ids['message']).get_json() == before
    restored = client.post(base + 'preview', json={'workload_id': plan['workload_id']}).get_json()
    assert restored['token'] == plan['token']


@SQL
def test_large_repair_review_resumes_saved_batches_without_repeating_model(monkeypatch):
    from backend.tests.test_communication_repair import sql_sample
    from backend.engineering.agent_tools import repair_execution as repair
    from backend.engineering.project_context import activate_project
    client, _ = sql_sample()
    activate_project(client.environ_base['HTTP_X_PROJECT_ID'])
    plan = repair.prepare({'defer_review': True})
    original = plan['groups'][0]
    plan['groups'] = [{**deepcopy(original), 'id': f'group-{index}'} for index in range(14)]
    saved = repair.store_plan(plan)
    calls = []
    def review(task, candidates):
        calls.append(candidates)
        return {'status': 'REVIEWED', 'trace_id': str(len(calls)), 'model': 'fixture', 'gaps': [],
                'decisions': [{'id': item['id'], 'recommended': True, 'reason': 'checked'} for item in candidates]}
    monkeypatch.setattr(repair, 'review_or_report', review)
    first = repair.review_saved({'workload_id': saved['workload_id']})
    assert first['agent_review']['status'] == 'REVIEWING'
    assert len(first['agent_review']['decisions']) == 12
    result = repair.review_saved({'workload_id': saved['workload_id']})
    assert result['agent_review']['status'] == 'REVIEWED'
    assert len(result['agent_review']['decisions']) == 14
    repeated = repair.review_saved({'workload_id': saved['workload_id']})
    assert repeated['agent_review'] == result['agent_review'] and len(calls) == 2
