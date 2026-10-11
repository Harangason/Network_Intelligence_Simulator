import os
import pytest
from backend.engineering import project_refresh as service


def test_refresh_checks_all_current_routes_and_passes_fresh_findings(monkeypatch):
    rows = [{'id': str(i), 'status': 'READY_FOR_REVIEW', 'name': f'Route {i}', 'route_code': f'RT-{i}'} for i in range(502)]
    rows.append({'id': 'old', 'status': 'SUPERSEDED'})
    monkeypatch.setattr(service, 'list_routes', lambda limit=500, offset=0: rows[offset:offset + limit])
    monkeypatch.setattr(service, 'load_plan', lambda: (object(), {}))
    monkeypatch.setattr(service, 'current_project_id', lambda: 'test-project')
    calls = []
    class Workflow:
        def __init__(self, *a): pass
        def refresh_source_status(self, step, **kwargs): calls.append(step)
        def get(self, **kwargs): return {'context': {'engineering_wizard_settings': {'project_name': 'Testprojekt'}}}
    class Validator:
        def __init__(self, *a, **kwargs): pass
        def validate_table(self, routes):
            assert len(routes) == 502
            return {'table_errors': [], 'results': [{'errors': [{'code': 'BROKEN', 'message': 'Weg fehlt'}] if route['id'] == '501' else [], 'warnings': []} for route in routes]}
    class Capacity:
        def __init__(self, *a): pass
        def calculate(self): calls.append('capacity'); return {'snapshot_id': 'capacity'}
    class Preflight:
        def __init__(self, *a): pass
        def run(self, *, routing_findings):
            calls.append('preflight')
            assert routing_findings[0]['object_id'] == '501'
            return {'error_count': len(routing_findings), 'findings': routing_findings}
    for key, value in [('WorkflowStatusService', Workflow), ('RoutingValidator', Validator), ('CapacityTimingService', Capacity), ('PreflightService', Preflight)]:
        monkeypatch.setattr(service, key, value)
    result = service.refresh_project()
    assert result['checked_routes'] == 502 and result['error_count'] == 1
    assert result['project_name'] == 'Testprojekt'
    assert calls == ['engineering_model', 'routing', 'network_editor', 'parameters', 'capacity', 'preflight']


@pytest.mark.skipif(not os.environ.get('ENGINEERING_TEST_DATABASE_URL'), reason='isolated database required')
def test_refresh_persists_checks_but_preserves_model_routes_and_approvals():
    from backend.tests.test_communication_repair import sql_sample
    client, ids = sql_sample()
    paths = ['/api/engineering/messages/' + ids['message'], '/api/engineering/routing/' + ids['route']]
    before = [client.get(path).get_json() for path in paths]
    response = client.post('/api/engineering/workflow/refresh-project', json={})
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    assert result['checked_routes'] == 1 and result['error_count'] > 0
    assert any(item.get('object_id') == ids['route'] for item in result['findings'])
    assert result['capacity_snapshot_id'] and result['snapshot_id']
    assert [client.get(path).get_json() for path in paths] == before
    stored = client.get('/api/engineering/preflight').get_json()
    assert stored['findings'] == result['findings']
