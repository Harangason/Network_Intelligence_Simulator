"""The low-load CAN-FD branch must still honor its confirmed jitter budget."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from backend.engineering.capacity.dimensioning import bus_schedule, policy_for, unique_streams
from backend.engineering.intelligence.network_planning import plan_network_distribution
from backend.engineering.routing.validation import PROTOCOL_CAPACITY


def fixture():
    return json.loads((Path(__file__).parent / 'fixtures/capacity_can_jitter.json').read_text(encoding='utf8'))


def plan(data, hard_limits=None):
    return plan_network_distribution(data['capacity'], data['hardware'], {},
        parameters=data['parameters'], resource_policy={'mode': 'AUTO_SIZE', 'hard_limits': hard_limits or {}})


def test_captured_low_load_can_branch_splits_to_meet_unchanged_jitter_bounds():
    data = fixture()
    before = deepcopy(data)
    rows = data['capacity']['results']['routes']
    assert len(rows) == 22
    original = bus_schedule(unique_streams(rows), policy_for(data['parameters']))
    assert original['status'] == 'CONSTRAINT_VIOLATION'
    assert all('Jittergrenze' in reason for reason in original['reasons'])
    result = plan(data)
    assert data == before, 'Do not reduce DLC/cycles/identifiers/jitter or alter the wire-time formula.'
    assert len(result['networks']) == 1
    network = result['networks'][0]
    assert network['current_load_percent'] < 15
    assert network['decision'] == 'SPLIT_CURRENT_TECHNOLOGY'
    assert network['selected_protocol'] == 'CAN_FD'
    assert network['proposed_segments'] > 1
    memberships = [identifier for segment in network['segments'] for identifier in segment['route_ids']]
    assert sorted(memberships) == sorted(row['route_id'] for row in rows)
    for segment in network['segments']:
        members = [row for row in rows if row['route_id'] in segment['route_ids']]
        check = bus_schedule(unique_streams(members), policy_for(data['parameters']))
        assert check['status'] == 'FEASIBLE_UNDER_ASSUMPTIONS', check
        assert segment['timing_status'] == 'VERIFIED_UNDER_ASSUMPTIONS'


def test_hard_can_inventory_still_blocks_the_timing_split():
    result = plan(fixture(), {'CAN_FD': 1})
    assert len(result['networks']) == 1
    assert result['networks'][0]['decision'] == 'UNRESOLVED_CAPACITY_CONSTRAINT'


def test_missing_can_identifiers_never_claim_a_verified_schedule():
    data = fixture()
    for row in data['capacity']['results']['routes']:
        row['arbitration_id'] = None
    result = plan(data)
    assert result['schedule_assessments'][0]['timing_status'] == 'UNVERIFIED'
    assert result['schedule_assessments'][0]['communication_schedule']['status'] == 'PROFILE_INCOMPLETE'
    assert result['networks'] == [], 'Missing identifiers do not justify an invented timing repair.'


def test_direct_gpio_line_is_not_split_as_a_shared_bus():
    data = fixture()
    row = deepcopy(data['capacity']['results']['routes'][0])
    row.update(protocol='GPIO', average_load_percent=80, peak_load_percent=92,
               burst_load_percent=120, segment_transmission_latency_ms=20)
    data['capacity']['results']['routes'] = [row]
    result = plan(data)
    assert result['networks'] == []
    assert result['schedule_assessments'][0]['timing_status'] == 'UNVERIFIED'


@pytest.mark.parametrize('protocol', sorted(set(PROTOCOL_CAPACITY) - {'LIN', 'CAN', 'CAN_FD'}))
def test_protocols_without_complete_scheduler_remain_unverified(protocol):
    data = fixture()
    row = deepcopy(data['capacity']['results']['routes'][0])
    row['protocol'] = protocol
    data['capacity']['results']['routes'] = [row]
    check = plan(data)['schedule_assessments'][0]
    assert check['protocol'] == protocol
    if protocol in {'ETHERNET', 'AUTOMOTIVE_ETHERNET'}:
        assert check['timing_status'] == 'UNVERIFIED'
        assert check['communication_schedule']['status'] == 'PROFILE_INCOMPLETE'
    else:
        assert check['timing_status'] == 'UNVERIFIED'
        assert check['communication_schedule']['status'] == 'UNVERIFIED'


@pytest.mark.parametrize('protocol', ['CAN', 'CAN_FD'])
def test_complete_can_frame_has_a_checked_single_bus_response_bound(protocol):
    data = fixture()
    row = deepcopy(data['capacity']['results']['routes'][0])
    row['protocol'] = protocol
    data['capacity']['results']['routes'] = [row]
    check = plan(data)['schedule_assessments'][0]
    assert check['timing_status'] == 'VERIFIED_UNDER_ASSUMPTIONS'
    assert check['communication_schedule']['status'] == 'FEASIBLE_UNDER_ASSUMPTIONS'


def test_complete_ethernet_port_has_a_checked_fifo_response_bound():
    data = fixture()
    row = deepcopy(data['capacity']['results']['routes'][0])
    row.update(protocol='ETHERNET', bitrate=100_000_000, segment_transmission_latency_ms=.01,
               queue_policy='FIFO', load_basis='BUSIEST_FULL_DUPLEX_PORT',
               calculation_model='ETHERNET_WIRE_ESTIMATE')
    data['capacity']['results']['routes'] = [row]

    result = plan(data)
    check = result['schedule_assessments'][0]

    assert check['timing_status'] == 'VERIFIED_UNDER_ASSUMPTIONS'
    assert check['communication_schedule']['model'] == 'ETHERNET_FULL_DUPLEX_FIFO_RESPONSE_BOUND_V1'


def test_mixed_physical_protocols_never_certify_only_the_lin_subset():
    data = json.loads((Path(__file__).parent / 'fixtures/capacity_remaining_lin.json').read_text(encoding='utf8'))
    lin = deepcopy(data['capacity']['results']['routes'][0])
    can = {**deepcopy(lin), 'protocol': 'CAN', 'bitrate': 500000,
           'frame_time_bound_ms': 0.2, 'segment_transmission_latency_ms': 0.15,
           'arbitration_id': 12, 'average_load_percent': 1.5, 'peak_load_percent': 1.725, 'burst_load_percent': 2.25,
           'route_id': 'different-can-route', 'message_id': 'different-can-message', 'stream_id': 'different-can-stream'}
    data['capacity']['results']['routes'] = [lin, can]
    result = plan(data)
    check = result['schedule_assessments'][0]
    assert check['timing_status'] == 'FAILED'
    assert check['communication_schedule']['status'] == 'MODEL_INCONSISTENT'
    assert result['networks'][0]['decision'] == 'UNRESOLVED_CAPACITY_CONSTRAINT'
    assert result['networks'][0]['timing_status'] == 'FAILED'
    assert result['networks'][0]['segments'] == []
    assert result['networks'][0]['technology_candidates'] == []
    assert any('widerspr' in issue for issue in result['unresolved'])
