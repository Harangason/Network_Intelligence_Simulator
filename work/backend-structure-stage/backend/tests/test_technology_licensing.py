from datetime import date, timedelta
import pytest

from backend.nis.app import create_app
from backend.nis.simulation.service import SimulationService
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as REGISTRY
from backend.nis.communication.services import licensing as module


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(module, '_root', lambda: tmp_path / 'licenses')


def submit(project='project-a', technology='nmea2000', **extra):
    return module.submit_evidence(project, technology, {'technology': technology,
        'issuer': 'Test issuer', 'reference': 'fixture-contract-ref',
        'scope_description': 'Synthetic test authorization for NIS simulation only', **extra})


def states(project='project-a'):
    return module.license_states(project, [REGISTRY.profile('nmea2000'), REGISTRY.profile('ethernet'), REGISTRY.profile('i3c')])


def test_pending_reference_never_unlocks_or_spreads_to_other_project():
    row = submit()
    assert row['status'] == 'PENDING'
    assert states()['nmea2000']['blocked']
    assert states('project-b')['nmea2000']['status'] == 'MISSING'
    assert not states()['ethernet']['blocked']
    assert not states()['i3c']['blocked']  # I3C Basic is not full MIPI CSI/DSI.
    with pytest.raises(ValueError, match='TECHNOLOGY_LICENSE_REQUIRED'):
        module.assert_technology_clearance('project-a', {'nmea2000', 'ethernet'}, REGISTRY)


def test_operator_review_requires_evidence_and_revoke_restores_block(tmp_path):
    row = submit()
    with pytest.raises(ValueError, match='Nachweis'):
        module.review_evidence('project-a', row['id'], reviewer='operator', evidence=None, approve=True, rationale='Synthetic review')
    evidence = tmp_path / 'test-evidence.txt'
    evidence.write_text('Synthetic license fixture, not a real license.', encoding='utf-8')
    module.review_evidence('project-a', row['id'], reviewer='operator', evidence=evidence, approve=True, rationale='Reviewed synthetic fixture scope')
    assert not states()['nmea2000']['blocked']
    assert states('project-b')['nmea2000']['blocked']
    module.assert_technology_clearance('project-a', {'nmea2000'}, REGISTRY)
    module.review_evidence('project-a', row['id'], reviewer='operator', evidence=None, approve=False, rationale='Fixture revoked')
    assert states()['nmea2000']['blocked']


def test_expiry_and_policy_revision_cannot_reuse_old_clearance(tmp_path):
    tomorrow = date.today() + timedelta(days=1)
    row = submit(expires_on=tomorrow.isoformat())
    evidence = tmp_path / 'evidence'; evidence.write_text('fixture')
    module.review_evidence('project-a', row['id'], reviewer='operator', evidence=evidence, approve=True, rationale='Fixture checked')
    assert module.license_states('project-a', [REGISTRY.profile('nmea2000')], today=tomorrow + timedelta(days=1))['nmea2000']['blocked']
    profile = REGISTRY.profile('nmea2000')
    profile['licensing_policy']['revision'] = 'new-policy'
    assert module.license_states('project-a', [profile])['nmea2000']['blocked']


def test_self_approval_unknown_tech_and_foreign_record_rejected():
    with pytest.raises(ValueError, match='Lizenzfreigabe'):
        submit(status='APPROVED', confirmed=True)
    with pytest.raises(ValueError, match='registriert'):
        submit(technology='ethernet')
    row = submit()
    with pytest.raises(ValueError, match='nicht gefunden'):
        module.review_evidence('project-b', row['id'], reviewer='operator', evidence=None, approve=False, rationale='Test')


def test_api_cannot_approve_or_choose_implicit_default_project():
    client = create_app(testing=True).test_client()
    assert client.get('/api/technology-licenses').status_code == 400
    payload = {'technology': 'nmea2000', 'issuer': 'Fixture', 'reference': 'Fixture', 'scope_description': 'Fixture'}
    response = client.post('/api/technology-licenses', json=payload, headers={'X-Project-ID': 'project-a'})
    assert response.status_code == 201
    assert client.post('/api/technology-licenses', json={**payload, 'status': 'APPROVED'}, headers={'X-Project-ID': 'project-a'}).status_code == 400
    assert client.get('/api/technology-licenses', headers={'X-Project-ID': 'project-a'}).get_json()['licenses']['nmea2000']['blocked']


@pytest.mark.parametrize('payload', [
    {'technology': 'nmea2000', 'license_confirmed': True},
    {'config': {'buses': [{'type': 'NMEA2000'}, {'type': 'ETHERNET'}]}},
    {'config': {'routes': [{'technology_stack': ['ethernet', 'mipi_csi2']}]}},
])
def test_standalone_and_raw_mixed_config_cannot_bypass_execution_lock(payload, tmp_path):
    with pytest.raises(ValueError, match='TECHNOLOGY_LICENSE_REQUIRED'):
        SimulationService().prepare_config({'project_id': 'project-a', **payload}, tmp_path)


def test_topology_and_interface_identity_are_checked_without_industry_inference():
    values = {'industry': 'marine', 'interfaces': [{'properties': {'technology_id': 'mipi_dsi'}}],
              'edges': [{'bus': 'NMEA2000'}]}
    ids = module.declared_technology_ids(values, REGISTRY)
    assert ids == {'mipi_dsi', 'nmea2000'}
