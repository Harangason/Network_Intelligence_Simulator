from backend.engineering.capacity.lin_schedule import lin_schedule_check
from backend.engineering.intelligence.network_planning import plan_network_distribution


def rows(count, cycle=100, latency=20, jitter=5):
    return [{'route_id': f'r{i}', 'producer': 'ecu', 'name': f'Message{i}', 'network_id': 'LIN1', 'protocol': 'LIN',
             'average_load_percent': 3 / cycle * 100, 'peak_load_percent': 3 / cycle * 100,
             'burst_load_percent': 3 / cycle * 100, 'segment_transmission_latency_ms': 3,
             'cycle_ms': cycle, 'max_latency_ms': latency, 'jitter_budget_ms': jitter} for i in range(count)]


def test_low_average_load_does_not_hide_simultaneous_lin_deadline_misses():
    traffic = rows(12, cycle=1000)
    assert sum(r['average_load_percent'] for r in traffic) < 4
    assert lin_schedule_check(traffic)['status'] == 'FAIL'
    plan = plan_network_distribution({'results': {'overview': {'target_bus_load_percent': 60}, 'routes': traffic}},
        [{'id': 'ecu', 'name': 'ECU', 'device_type': 'ECU'}], {}, resource_policy={'mode': 'AUTO_SIZE'})
    assert plan['networks'][0]['decision'] == 'SPLIT_CURRENT_TECHNOLOGY'
    assert plan['networks'][0]['proposed_segments'] == 2
    assert all(segment['lin_schedule']['status'] == 'PASS' for segment in plan['networks'][0]['segments'])


def test_fast_lin_poll_requires_a_bound_for_non_preemptive_jitter():
    traffic = rows(6, cycle=100)
    traffic[0]['cycle_ms'] = 10
    assert lin_schedule_check(traffic)['status'] == 'FAIL'
    assert lin_schedule_check(traffic[:4])['status'] == 'PASS'


def test_more_than_fifty_slow_lin_participants_are_allowed_when_timing_fits():
    assert lin_schedule_check(rows(100, cycle=10000, latency=1000, jitter=100))['status'] == 'PASS'
