"""S37: changes to signals/states/routes must count as real deviations."""
import pytest
from backend.engineering.agent_tools.analysis import compare


def test_gateway_segments_match_independently_of_arrival_order():
    from backend.engineering.reasoning.correlation import FirstDivergenceAnalyzer
    golden = [{'route_id': 'route', 'message_id': 'message', 'sequence': 600, 'segment_index': hop,
               'time_s': time, 'network': network, 'signals': {'temperature': 34}}
              for hop, time, network in [(0, 12.0, 'CAN_FD'), (1, 12.002, 'Ethernet')]]
    actual = [{**golden[1], 'time_s': 12.102}, golden[0]]
    result = compare({'events': actual, 'golden_events': golden})
    assert result['deviation_count'] == 1
    assert result['first_divergence']['segment'] == '1'
    assert result['value_comparison'][0]['matched_samples'] == 2
    assert result['value_comparison'][0]['max_absolute_error'] == 0
    reasoning = FirstDivergenceAnalyzer.analyze(actual, golden)
    assert len(reasoning['ordered_divergences']) == 1
    assert reasoning['first_divergence']['types'] == ['TIMING_DEVIATION']


@pytest.mark.parametrize('change', [
    {'signals': {'temperature': {'value': 100, 'physical_value': 11}}},
    {'network_id': 'other-network'}, {'route_ref': 'other-route'}, {'route_refs': ['other-route']},
])
def test_reasoning_first_divergence_preserves_physical_and_route_changes(change):
    from backend.engineering.reasoning.correlation import FirstDivergenceAnalyzer
    event = {'time_s': 12, 'sequence': 1, 'message_id': 'temperature-message',
             'signals': {'temperature': {'value': 100, 'physical_value': 10}},
             'network_id': 'network', 'route_ref': 'route', 'route_refs': ['route']}
    result = FirstDivergenceAnalyzer.analyze([{**event, **change}], [event])
    assert result['deviation_count'] == 1
    assert result['first_divergence']['timestamp'] == 12
    assert len(result['ordered_divergences']) == 1


@pytest.mark.parametrize('change', [
    {'signals': {'temperature': 99}}, {'signals': {'state': 'FAILED'}},
    {'route_ref': 'other-route'}, {'network_id': 'other-network'}, {'faults': ['DELAY']},
])
def test_value_and_path_only_change_is_counted(change):
    event = {'route_id': 'route', 'sequence': 1, 'time_s': 2,
             'signals': {'temperature': 20}, 'route_ref': 'route', 'network_id': 'net', 'faults': []}
    result = compare({'events': [{**event, **change}], 'golden_events': [event]})
    assert result['deviation_count'] == 1
    assert result['first_divergence']['time_s'] == 2
    assert result['first_divergence']['type'] == 'EVENT_DEVIATION'


def test_first_divergence_is_temporal_not_route_name_order():
    golden = [{'route_id': name, 'sequence': 1, 'time_s': time, 'status': 'OK'}
              for name, time in [('a-late', 20), ('z-early', 2)]]
    result = compare({'events': [{**event, 'status': 'FAIL'} for event in golden], 'golden_events': golden})
    assert result['first_divergence']['route_id'] == 'z-early'


@pytest.mark.parametrize('events', [
    [{'route_id': 'r'}], [{'time_s': float('nan')}],
    [{'route_id': 'r', 'sequence': 1, 'time_s': 0}, {'route_id': 'r', 'sequence': 1, 'time_s': 1}],
])
def test_no_invented_time_or_silently_overwritten_duplicate(events):
    with pytest.raises(ValueError):
        compare({'events': events, 'golden_events': [{'time_s': 0}]})


@pytest.mark.parametrize('basis', ['utc', 'unknown', 'unavailable'])
def test_incompatible_or_unknown_clocks_are_not_compared(basis):
    with pytest.raises(ValueError, match='Zeitbasis'):
        compare({'events': [{'time_s': 1, 'time_basis': basis}],
                 'golden_events': [{'time_s': 1, 'time_basis': 'relative'}]})


def test_additional_missing_and_delayed_events_remain_distinct():
    golden = [{'route_id': 'r', 'sequence': i, 'time_s': i} for i in (1, 2, 3)]
    actual = [{'route_id': 'r', 'sequence': i, 'time_s': i + .1} for i in (1, 3, 4)]
    result = compare({'events': actual, 'golden_events': golden})
    assert result['deviation_count'] == 4
    assert [event['type'] for event in result['event_deviations']] == [
        'EVENT_DEVIATION', 'MISSING_EVENT', 'EVENT_DEVIATION', 'ADDITIONAL_EVENT']
    assert result['first_divergence']['timing_delta_s'] == pytest.approx(.1)


def test_delayed_window_boundary_is_not_an_additional_or_missing_event():
    from backend.engineering.reasoning.correlation import complete_window_counterparts, FirstDivergenceAnalyzer
    golden = [{'route_id': 'r', 'sequence': i, 'time_s': time} for i, time in [(1, 11.95), (2, 12.4)]]
    actual = [{**event, 'time_s': event['time_s'] + .1} for event in golden]
    # Arrival-time window [12, 12.45] contains opposite halves of the same transmissions.
    a, b = complete_window_counterparts(actual[:1], golden[1:], lambda: iter(actual), lambda: iter(golden))
    result = FirstDivergenceAnalyzer.analyze(a, b)
    assert len(result['ordered_divergences']) == 2
    assert all(item['types'] == ['TIMING_DEVIATION'] for item in result['ordered_divergences'])
    assert result['first_divergence']['timestamp'] == 11.95


def test_counterpart_search_budget_never_proves_missing_events():
    from backend.engineering.reasoning.correlation import complete_window_counterparts
    event = {'route_id': 'r', 'sequence': 1, 'time_s': 1}
    with pytest.raises(ValueError, match='GOLDEN_ALIGNMENT_INCOMPLETE'):
        complete_window_counterparts([event], [], lambda: iter([]), lambda: iter([event, event]), max_scan=1)
