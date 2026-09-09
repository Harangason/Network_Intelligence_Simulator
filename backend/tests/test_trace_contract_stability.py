from pathlib import Path

import pytest

from backend.tests.test_model_based_simulation import simulation_config
from backend.engineering.simulation import validate_scenario
from backend.engineering.models import EngineeringValidationError
from model_based_simulation import ModelBasedSimulationEngine
from hardware_profile import normalize_hardware_config
from universal_trace import generate_universal_events


def test_seed_zero_is_not_silently_replaced_by_default(tmp_path: Path):
    config = {**simulation_config(tmp_path), 'seed': 0}
    engine = ModelBasedSimulationEngine(config)
    assert engine.seed == engine.behavior.seed == engine.faults.seed == 0


def test_trace_keeps_canonical_route_ref_and_explicit_zero_jitter(tmp_path: Path):
    config = simulation_config(tmp_path)
    for item in config['communications']:
        item.update(routing_entry_id='canonical-route', routing_entry_ids=['canonical-route'], jitter_ratio=0)
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1_700_000_000)
    assert events
    assert all(event['route_ref'] == 'canonical-route' and event['route_refs'] == ['canonical-route'] for event in events)
    assert all(event['injected_jitter_ms'] == 0 for event in events)


def test_gateway_fault_targets_are_validated_against_canonical_nodes():
    model = {'nodes': [{'id': 'gateway', 'device_type': 'Gateway'}, {'id': 'ecu', 'device_type': 'ECU'}],
             'routes': [{'source': {'network_id': 'bus'}}]}
    scenario = {'mode': 'USER_DEFINED_FAULT', 'faults': [{'scope': 'NETWORK', 'type': 'GATEWAY_DELAY',
                 'target': {'id': 'gateway'}, 'start_s': 0.01, 'end_s': 0.05, 'delay_ms': 5}]}
    assert validate_scenario(scenario, model)['faults'][0]['target']['id'] == 'gateway'
    scenario['faults'][0]['target']['id'] = 'ecu'
    with pytest.raises(EngineeringValidationError, match='kein vorhandenes NETWORK-Ziel'):
        validate_scenario(scenario, model)
    scenario['faults'][0]['target']['id'] = 'missing'
    with pytest.raises(EngineeringValidationError):
        validate_scenario(scenario, {})


def test_jitter_budget_does_not_inject_a_disturbance(tmp_path: Path):
    config = simulation_config(tmp_path)
    config['jitter_ms'] = 50  # Acceptance budget; not a source disturbance.
    for route in config['communications']:
        route.pop('jitter_ratio', None)
        route['jitter_ms'] = 50
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1_700_000_000)
    assert events and all(event['injected_jitter_ms'] == 0 for event in events)
    config['source_jitter_ms'] = 2
    _, disturbed = generate_universal_events(config, normalize_hardware_config(config), start_utc=1_700_000_000)
    assert any(event['injected_jitter_ms'] != 0 for event in disturbed)
    assert all(abs(event['injected_jitter_ms']) <= 2 for event in disturbed)


@pytest.mark.parametrize('fast_id,slow_id', [('z-fast', 'a-slow'), ('a-fast', 'z-slow')])
def test_lin_poll_order_does_not_depend_on_random_route_ids(tmp_path: Path, fast_id, slow_id):
    from backend.app.runtime_analysis import analyze_runtime_trace
    config = simulation_config(tmp_path)
    config.update(duration_s=0.3, engineering_model={})
    config['networks'][0].update(technology='lin', bitrate=19200)
    for device in config['hardware']['devices']:
        device['ports'][0]['physical_type'] = 'lin'
        device['ports'][0]['network_interfaces'][0]['technology'] = 'lin'
    base = {**config['communications'][0], 'technology': 'lin', 'signal_ids': [], 'jitter_limit_ms': 5}
    config['communications'] = [
        {**base, 'id': slow_id, 'cycle_ms': 100, 'payload_bytes': 8},
        {**base, 'id': fast_id, 'cycle_ms': 10, 'payload_bytes': 2},
    ]
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1_700_000_000)
    metrics = analyze_runtime_trace({'model_simulation': {'frames': events}}, config)
    fast = next(row for row in metrics['routes'] if row['route_id'] == fast_id)
    assert fast['maximum_jitter_ms'] < 0.001
    assert fast['jitter_violations'] == 0
