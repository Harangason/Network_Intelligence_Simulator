"""Unavailable wire-time evidence must not turn into free capacity or a trace."""
import pytest

from backend.engineering.agent_tools import services
from backend.engineering.intelligence.network_planning import plan_network_distribution
from backend.tests.test_network_distribution import capacity, hardware
from backend.tests.test_model_based_simulation import simulation_config
from hardware_profile import normalize_hardware_config
from universal_trace import generate_universal_events


@pytest.mark.parametrize('rates', [{}, {'bitrate': 500000}, {'data_bitrate': 2000000}])
def test_simulation_requires_both_explicit_can_fd_phases(tmp_path, rates):
    config = simulation_config(tmp_path)
    for network in config['networks']:
        for key in ('bitrate', 'arbitration_bitrate', 'data_bitrate'):
            network.pop(key, None)
        network.update(rates)
    with pytest.raises(ValueError, match='TIMING_UNVERIFIED'):
        generate_universal_events(config, normalize_hardware_config(config), start_utc=1700000000)


def test_agent_load_without_rates_is_unverified_instead_of_zero():
    result = services._load({'technology': 'can_fd', 'payload_bytes': 8, 'cycle_ms': 10})
    assert result['status'] == 'UNVERIFIED'
    assert result['load_percent'] is None and result['transmission_time_s'] is None
    assert result['valid'] is False
    confirmed = services._load({'technology': 'can_fd', 'payload_bytes': 8, 'cycle_ms': 10,
                               'parameters': {'bitrate': 500000, 'data_bitrate': 2000000}})
    assert confirmed['status'] == 'VERIFIED' and confirmed['load_percent'] > 0


def test_agent_network_without_metrics_is_not_available_capacity(monkeypatch):
    monkeypatch.setattr(services.access, 'networks', lambda: [{'id': 'n', 'technology': 'can_fd'}])
    monkeypatch.setattr(services, '_capacity', lambda _: {'results': {'networks': []}, 'findings': []})
    result = services._network_capacity({'network_id': 'n'})
    assert result['status'] == 'UNVERIFIED' and result['capacity_verified'] is False
    assert result['average_load_percent'] is None and result['capacity_margin_percent'] is None
    assert services._available({'required_load_percent': 1})['candidates'] == []


def test_agent_excludes_unverified_capacity_even_with_legacy_numeric_preview(monkeypatch):
    monkeypatch.setattr(services.access, 'networks', lambda: [{'id': 'n', 'technology': 'can_fd'}])
    monkeypatch.setattr(services, '_capacity', lambda _: {'results': {'networks': [{
        'network_id': 'n', 'average_load_percent': 0, 'target_margin_percent': 60,
        'capacity_verified': False}]}, 'findings': []})
    assert services._available({'required_load_percent': 1})['candidates'] == []


def test_migration_cannot_recommend_target_technology_without_explicit_rates():
    result = plan_network_distribution(capacity((120, 20, 20)), hardware(), {},
                                       allowed_protocols=['LIN', 'CAN_FD'])
    assert result['status'] == 'RESIDUAL_CONSTRAINTS'
    assert result['networks'][0]['decision'] == 'UNRESOLVED_CAPACITY_CONSTRAINT'


@pytest.mark.parametrize('parameters', [{}, {'bitrate': 500000}, {'data_bitrate': 2000000}])
def test_standalone_api_requires_explicit_phase_rates(tmp_path, parameters):
    from backend.app.simulation_service import SimulationService
    with pytest.raises(ValueError, match='Technology-Validierung'):
        SimulationService().prepare_config({'technology': 'can_fd', **parameters}, tmp_path)


def test_standalone_options_keep_absent_rates_and_preserve_explicit_phases(tmp_path):
    from standalone_cli import StandaloneSimulationOptions
    base = dict(technology='can_fd', industry='automotive', output_dir=tmp_path)
    missing = StandaloneSimulationOptions(**base).to_config()['networks'][0]
    assert 'bitrate' not in missing and 'data_bitrate' not in missing
    provided = StandaloneSimulationOptions(**base, arbitration_bitrate=500000, data_bitrate=2000000).to_config()['networks'][0]
    assert provided['arbitration_bitrate'] == 500000 and provided['data_bitrate'] == 2000000
