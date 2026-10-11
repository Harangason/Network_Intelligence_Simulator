"""Executable cross-industry acceptance cases from the product target (A–E)."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from backend.tests.test_model_based_simulation import simulation_config
from communication_simulator import run_simulation
from hardware_profile import normalize_hardware_config
from universal_trace import generate_universal_events
from backend.engineering.agent_tools.analysis import root_cause, compare
from backend.engineering.capacity.calculators import estimate_frame


def case_config(path, technologies):
    config = simulation_config(path)
    config['networks'] = [{'id': f'network-{i}', 'technology': tech, 'bitrate': 100_000_000 if tech != 'can_fd' else 500_000,
                           **({'arbitration_bitrate': 500_000, 'data_bitrate': 2_000_000} if tech == 'can_fd' else {})}
                          for i, tech in enumerate(technologies)]
    config['hardware']['devices'] = []
    for i in range(len(technologies) + 1):
        ports = []
        for segment in (i - 1, i):
            if 0 <= segment < len(technologies):
                tech = technologies[segment]
                ports.append({'id': f'port-{i}-{segment}', 'physical_type': 'can' if tech == 'can_fd' else 'ethernet',
                              'network_interfaces': [{'id': f'if-{i}-{segment}', 'technology': tech, 'network': f'network-{segment}'}]})
        config['hardware']['devices'].append({'id': f'node-{i}', 'name': f'Controller {i}',
            'type': 'gateway' if 0 < i < len(technologies) else 'ecu',
            'logical_node_address': i + 1, 'formatted_logical_node_address': f'0x{i + 1:04X}', 'ports': ports})
    config['communications'] = [{
        'id': f'route-{i}', 'sender_interface': f'if-{i}-{i}',
        'receiver_interfaces': [f'if-{i + 1}-{i}'], 'network': f'network-{i}',
        'technology': tech, 'cycle_ms': 10, 'payload_bytes': 8,
        'message_ids': ['msg-1'], 'signal_ids': ['sig-temperature'],
    } for i, tech in enumerate(technologies)]
    return config


def assert_timing_model_unavailable(config, technologies):
    """Negative capability evidence only; this does not accept an architecture."""
    for technology in technologies:
        network = next(item for item in config['networks'] if item['technology'] == technology)
        frame = estimate_frame(technology, 8, network)
        assert frame.to_dict()['transmission_time_s'] is None
        assert not frame.transmission_time_available
    with pytest.raises(ValueError, match='TIMING_UNVERIFIED'):
        generate_universal_events(config, normalize_hardware_config(config), start_utc=1_700_000_000)


@pytest.mark.parametrize('case,technologies,fault', [
    ('A-CAN-FD-gateway', ['can_fd', 'can_fd'], {'scope': 'NETWORK', 'type': 'GATEWAY_DROP', 'target': {'id': 'node-1'}}),
    ('B-industrial', ['profinet', 'modbus_tcp'], {'scope': 'SIGNAL', 'type': 'SIGNAL_OFFSET', 'target': {'id': 'sig-temperature'}, 'magnitude': 12}),
    ('C-DDS', ['dds_rtps'], {'scope': 'MESSAGE', 'type': 'MESSAGE_LOSS', 'target': {'id': 'route-0'}}),
    ('D-mixed-gateway', ['can_fd', 'ethernet'], {'scope': 'NETWORK', 'type': 'GATEWAY_DELAY', 'target': {'id': 'node-1'}, 'delay_ms': 5}),
    ('modeled-Ethernet-offset', ['ethernet'], {'scope': 'SIGNAL', 'type': 'SIGNAL_OFFSET', 'target': {'id': 'sig-temperature'}, 'magnitude': 12}),
    ('modeled-Ethernet-loss', ['ethernet'], {'scope': 'MESSAGE', 'type': 'MESSAGE_LOSS', 'target': {'id': 'route-0'}}),
])
def test_cross_industry_trace_and_root_cause_or_explicit_model_gap(tmp_path, case, technologies, fault):
    normal = case_config(tmp_path / 'normal', technologies)
    if case in {'B-industrial', 'C-DDS'}:
        assert_timing_model_unavailable(normal, technologies)
        changed = deepcopy(normal)
        changed['scenario'] = {'mode': 'USER_DEFINED_FAULT', 'faults': [{**fault, 'start_s': .02, 'end_s': .05}]}
        assert_timing_model_unavailable(changed, technologies)
        return
    profile = normalize_hardware_config(normal)
    _, baseline = generate_universal_events(normal, profile, start_utc=1_700_000_000)
    _, replay = generate_universal_events(normal, profile, start_utc=1_700_000_000)
    assert baseline == replay
    assert {item['network'] for item in baseline} == {f'network-{i}' for i in range(len(technologies))}
    assert all(item['signals'] and item['source_logical_address'] and item['destination_logical_addresses'] for item in baseline)
    for item in baseline:
        network = next(n for n in normal['networks'] if n['id'] == item['network'])
        expected = estimate_frame(item['technology'], item['payload_bytes'], network)
        if item.get('ethernet'):
            from ethernet_transport import wire_bytes
            assert item['transmission_latency_ms'] == pytest.approx(wire_bytes(item['ethernet'], item['payload_bytes']) * 8 / network['bitrate'] * 2000)
        else:
            assert item['transmission_latency_ms'] == pytest.approx(expected.transmission_time_s * 1000)
    changed = deepcopy(normal)
    changed['output_dir'] = str(tmp_path / 'fault')
    changed['scenario'] = {'mode': 'USER_DEFINED_FAULT', 'faults': [{**fault, 'start_s': 0.02, 'end_s': 0.05}]}
    result = run_simulation(changed)
    trace_path = next(Path(p) for p in result['artifacts'] if str(p).endswith('universal_trace.jsonl'))
    actual = [json.loads(line) for line in trace_path.read_text(encoding='utf-8').splitlines()]
    affected = [item for item in actual if item['faults']]
    assert affected, (case, result)
    assert all(0.02 <= item['scheduled_time_s'] <= 0.05 for item in affected)
    analysis = root_cause({'events': actual, 'configuration': changed})
    assert analysis['hypotheses'] and not analysis['causality_proven']
    assert analysis['hypotheses'][0]['affected_objects']['route_id']
    comparison = compare({'events': actual, 'golden_events': baseline})
    assert comparison['findings'], comparison
    if fault['type'] == 'GATEWAY_DELAY':
        assert any(item.get('timing_delta_s', 0) >= 0.0049 for item in comparison['event_deviations'])


def test_golden_comparison_aligns_delayed_frames_and_preserves_evidence():
    golden = [{'route_id': 'route', 'sequence': i, 'time_s': i / 10, 'status': 'transmitted',
               'network': 'network', 'signals': {'temperature': i}, 'faults': []} for i in range(4)]
    changed = [{**event, 'time_s': event['time_s'] + 0.05, 'signals': {'temperature': i + 3},
                'faults': ['GATEWAY_DELAY']} for i, event in enumerate(golden)]
    comparison = compare({'events': changed, 'golden_events': golden})
    assert comparison['value_comparison'][0]['matched_samples'] == 4
    assert comparison['value_comparison'][0]['rmse'] == 3
    assert comparison['deviation_count'] == 4
    assert all(item['evidence'] for item in comparison['findings'])
