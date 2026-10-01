"""Physical LIN feasibility and a missed planning reserve are distinct results."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from backend.engineering.capacity.dimensioning import unique_streams, bus_schedule, policy_for
from backend.engineering.capacity.calculators import estimate_frame, utilization_percent
from backend.engineering.intelligence.network_planning import plan_network_distribution


def fixture():
    return json.loads((Path(__file__).parent / 'fixtures/capacity_remaining_lin.json').read_text(encoding='utf8'))


def plan(data, *, hard_limits=None):
    return plan_network_distribution(data['capacity'], data['hardware'], {},
        parameters=data['parameters'], available_protocol_counts={'LIN': 2, 'SOME_IP': 1},
        resource_policy={'mode': 'AUTO_SIZE', 'hard_limits': hard_limits or {}},
        physical_interfaces=data['physical_interfaces'])


def test_captured_remaining_lin_branches_split_without_changing_their_communication_contracts():
    data = fixture()
    before = deepcopy(data)
    result = plan(data)
    assert data == before
    assert result['target_load_percent'] == 60
    assert len(result['networks']) == 2
    for network in result['networks']:
        assert network['decision'] == 'SPLIT_CURRENT_TECHNOLOGY'
        assert network['selected_protocol'] == 'LIN'
        assert network['target_status'] == 'EXCEEDED'
        assert network['warnings']
        rows = [r for r in data['capacity']['results']['routes'] if r['network_id'] == network['network_id']]
        streams = unique_streams(rows)
        expected = sum(r['burst_load_percent'] for r in streams)
        assert network['current_load_percent'] == pytest.approx(expected, abs=0.0001)
        memberships = [rid for segment in network['segments'] for rid in segment['route_ids']]
        assert sorted(memberships) == sorted(r['route_id'] for r in rows)
        for stream in streams:
            assert sum(set(stream['route_ids']).issubset(segment['route_ids']) for segment in network['segments']) == 1
        for segment in network['segments']:
            members = [r for r in streams if r['route_id'] in segment['route_ids']]
            checked = bus_schedule(members, policy_for(data['parameters']))
            assert checked['status'] == 'FEASIBLE_UNDER_ASSUMPTIONS', checked
            assert checked['nominal_load_percent'] < 100
            assert segment['projected_load_percent'] < 90
            if segment['projected_load_percent'] > 60:
                assert len(members) == 1
                assert segment['projected_load_percent'] == pytest.approx(65.625)
                assert segment['warnings'][0]['code'] == 'CAPACITY_TARGET_RESERVE_UNMET'
    assert result['requires_human_approval'] is True


def test_explicit_segment_limit_still_blocks_the_reserve_split():
    result = plan(fixture(), hard_limits={'LIN': 2, 'SOME_IP': 0})
    assert all(n['decision'] not in {'SPLIT_CURRENT_TECHNOLOGY', 'KEEP_CURRENT_WITH_RESERVE_WARNING'} for n in result['networks'])


def test_explicit_hardware_channel_load_limit_is_not_replaced_by_a_reserve_warning():
    data = fixture()
    for port in data['physical_interfaces']:
        port['hard_load_limit'] = 60
    result = plan(data)
    assert all(n['decision'] not in {'SPLIT_CURRENT_TECHNOLOGY', 'KEEP_CURRENT_WITH_RESERVE_WARNING'} for n in result['networks'])


@pytest.mark.parametrize('requirement', ['SOFT', 'HARD'])
def test_slot_reserve_is_distinct_from_a_met_stress_target(requirement):
    data = fixture()
    data['parameters']['communication_sizing']['reserve_requirement'] = requirement
    frame = estimate_frame('LIN', 3, {'bitrate': 19200})
    nominal = utilization_percent(frame.transmission_time_s, 10)
    rows = []
    for index in range(2):
        row = deepcopy(data['capacity']['results']['routes'][0])
        row.update(message_id=f'three-byte-frame-{index}', route_id=f'three-byte-route-{index}',
                   payload_bytes=3, frame_bits=frame.frame_bits,
                   segment_transmission_latency_ms=frame.transmission_time_s * 1000,
                   average_load_percent=nominal, peak_load_percent=nominal * 1.15, burst_load_percent=nominal * 1.5)
        rows.append(row)
    data['capacity']['results']['routes'] = rows
    result = plan(data)
    network = result['networks'][0]
    if requirement == 'HARD':
        assert network['decision'] not in {'SPLIT_CURRENT_TECHNOLOGY', 'KEEP_CURRENT_WITH_RESERVE_WARNING'}
    else:
        assert network['decision'] == 'SPLIT_CURRENT_TECHNOLOGY'
        assert network['proposed_segments'] == 2
        assert network['target_status'] == 'PASS'
        assert len(network['warnings']) == 2
        assert all(w['code'] == 'LIN_SCHEDULE_RESERVE_UNMET' for w in network['warnings'])
        assert all(w['slot_load_percent'] == 100 for w in network['warnings'])


def test_multicast_keeps_the_strictest_receiver_hardware_limit():
    data = fixture()
    rows = data['capacity']['results']['routes'][:2]
    assert rows[0]['message_id'] == rows[1]['message_id']
    for port in data['physical_interfaces']:
        port['hard_load_limit'] = 40 if port['id'] == rows[1]['physical_target']['hardware_interface_id'] else 90
    data['capacity']['results']['routes'] = rows
    result = plan(data)
    assert result['networks'][0]['decision'] not in {'SPLIT_CURRENT_TECHNOLOGY', 'KEEP_CURRENT_WITH_RESERVE_WARNING'}


def test_already_isolated_message_is_a_reserve_warning_without_another_topology_change():
    data = fixture()
    data['capacity']['results']['routes'] = [data['capacity']['results']['routes'][0]]
    result = plan(data)
    network = result['networks'][0]
    assert network['decision'] == 'KEEP_CURRENT_WITH_RESERVE_WARNING'
    assert network['additional_segments'] == 0
    assert {w['code'] for w in network['warnings']} == {'CAPACITY_TARGET_RESERVE_UNMET', 'LIN_SCHEDULE_RESERVE_UNMET'}


@pytest.mark.parametrize('change', [
    {'payload_bytes': 9},
    {'average_load_percent': 100, 'peak_load_percent': 115, 'burst_load_percent': 150,
     'segment_transmission_latency_ms': 10},
    {'cycle_ms': 5, 'max_latency_ms': 4},
])
def test_a_reserve_warning_never_releases_an_impossible_frame_or_schedule(change):
    data = fixture()
    row = deepcopy(data['capacity']['results']['routes'][0])
    row.update(change)
    data['capacity']['results']['routes'] = [row]
    result = plan(data, hard_limits={'SOME_IP': 0})
    assert result['networks'][0]['decision'] not in {'SPLIT_CURRENT_TECHNOLOGY', 'KEEP_CURRENT_WITH_RESERVE_WARNING'}
