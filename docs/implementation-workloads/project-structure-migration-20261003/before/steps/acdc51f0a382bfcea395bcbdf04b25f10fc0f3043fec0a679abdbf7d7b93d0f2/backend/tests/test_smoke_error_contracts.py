"""Invalid requests and fresh projects remain usable without hiding server bugs."""
from uuid import uuid4

import pytest

from backend.app import create_app
from backend.engineering.goal_execution.store import save_goal
from backend.engineering.project_context import activate_project, reset_project


@pytest.fixture
def client():
    result = create_app(testing=True).test_client()
    result.environ_base['HTTP_X_PROJECT_ID'] = 'pytest-smoke-' + uuid4().hex
    return result


@pytest.mark.parametrize('method,path,payload,expected', [
    ('put', '/communication-resources/unknown-kind', {}, 400),
    ('put', '/communication-resources/CommunicationController', [], 400),
    ('put', '/communication-resources/CommunicationController', {'resource': []}, 400),
    ('get', '/execution-goals/missing-workload', None, 404),
    ('post', '/workflow/communication-repair/review', {}, 400),
    ('post', '/workflow/communication-repair/review', {'workload_id': []}, 400),
    ('post', '/workflow/communication-repair/review', {'workload_id': 'repair-missing'}, 404),
    ('post', '/structure/transfer/analyze', {}, 400),
    ('post', '/structure/transfer/analyze', {'source_hardware_id': 'missing'}, 400),
    ('post', '/workflow/spatial-zoning/preview', {}, 400),
    ('put', '/workflow/spatial-zoning', {}, 400),
])
def test_invalid_input_has_domain_response_and_next_request_still_works(client, method, path, payload, expected):
    before = client.get('/api/engineering/workflow').get_json()
    response = getattr(client, method)('/api/engineering' + path, **({'json': payload} if method != 'get' else {}))
    assert response.status_code == expected, response.get_data(as_text=True)
    assert response.is_json and response.get_json()['error']
    after = client.get('/api/engineering/workflow')
    assert after.status_code == 200
    assert after.get_json()['topology'] == before['topology']
    assert after.get_json()['versions'] == before['versions']


def test_existing_goal_is_visible_only_in_its_own_project(client):
    project = client.environ_base['HTTP_X_PROJECT_ID']
    token = activate_project(project)
    try:
        save_goal({'workload_id': 'repair-owned', 'status': 'WAITING_FOR_USER'})
    finally:
        reset_project(token)
    response = client.get('/api/engineering/execution-goals/repair-owned')
    assert response.status_code == 200
    assert response.get_json()['workload_id'] == 'repair-owned'
    assert client.get('/api/engineering/execution-goals/repair-owned',
                      headers={'X-Project-ID': project + '-other'}).status_code == 404


def test_hardware_revision_conflict_still_returns_409(client):
    response = client.put('/api/engineering/communication-resources/CommunicationController',
                          json={'resource': {}, 'expected_revision': 'stale'})
    assert response.status_code == 409


def test_programming_error_is_not_relabelled_as_input_error(client, monkeypatch):
    from backend.engineering.goal_execution import resources
    def broken(*_args):
        raise KeyError('unexpected internal defect')
    monkeypatch.setattr(resources, 'record_hardware_fact', broken)
    with pytest.raises(KeyError, match='unexpected internal defect'):
        client.put('/api/engineering/communication-resources/CommunicationController', json={})
