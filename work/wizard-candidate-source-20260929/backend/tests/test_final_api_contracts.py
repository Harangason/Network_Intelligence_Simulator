"""Boundary regressions found in the deployed all-endpoint smoke test."""
import importlib

import pytest

from backend.app import create_app
from backend.app.job_service import JobService
from backend.engineering.models import EngineeringValidationError
from backend.engineering.simulation import validate_scenario
from model_based_simulation import FaultInjectionEngine


def test_cancel_alias_preserves_project_scope_and_idempotency(monkeypatch):
    api = importlib.import_module('backend.app.api')
    jobs = JobService(persist=False)
    jobs._jobs['job'] = {'id': 'job', 'project_id': 'cancel-contract', 'status': 'queued'}
    monkeypatch.setattr(api, 'JOBS', jobs)
    monkeypatch.setattr(jobs, '_update_workflow_snapshot', lambda *args: None)
    client = create_app(testing=True).test_client()
    assert client.post('/api/simulations/job', headers={'X-Project-ID': 'other'}).status_code == 404
    assert jobs.get('job')['status'] == 'queued'
    response = client.post('/api/simulations/job', headers={'X-Project-ID': 'cancel-contract'})
    assert response.status_code == 200
    assert response.get_json()['status'] == 'canceled'
    repeated = client.post('/api/simulations/job/cancel', headers={'X-Project-ID': 'cancel-contract'})
    assert repeated.get_json() == response.get_json()


def test_named_gateway_fault_resolves_canonical_id_and_changes_runtime():
    model = {'nodes': [{'id': 'gw-id', 'name': 'Zentrales Gateway', 'device_type': 'Gateway'}]}
    scenario = {'mode': 'USER_DEFINED_FAULT', 'faults': [{'scope': 'NETWORK', 'type': 'GATEWAY_DELAY',
                'target': {'name': 'Zentrales Gateway'}, 'delay_ms': 5}]}
    normalized = validate_scenario(scenario, model)
    assert normalized['faults'][0]['target']['id'] == 'gw-id'
    assert 'id' not in scenario['faults'][0]['target']
    event = {'scheduled_time_s': 0.1, 'time_s': 0.1, 'network': 'CAN', 'gateway_ids': ['gw-id']}
    assert FaultInjectionEngine(normalized['faults'], seed=0).event_faults(event) == ['GATEWAY_DELAY']
    assert event['time_s'] == pytest.approx(0.105)


def test_ambiguous_gateway_name_is_not_silently_selected():
    model = {'nodes': [{'id': gateway_id, 'name': 'Gateway', 'device_type': 'Gateway'} for gateway_id in ['a', 'b']]}
    scenario = {'mode': 'USER_DEFINED_FAULT', 'faults': [{'scope': 'NETWORK', 'type': 'GATEWAY_DROP',
                'target': {'name': 'Gateway'}}]}
    with pytest.raises(EngineeringValidationError, match='mehrdeutiges Gateway-Ziel'):
        validate_scenario(scenario, model)
