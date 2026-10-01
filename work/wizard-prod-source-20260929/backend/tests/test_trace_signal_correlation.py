"""No fabricated t=0, mixed clocks or overwritten samples in MCP correlation."""
import pytest
from backend.engineering.agent_tools.analysis import correlate


@pytest.mark.parametrize('time', [None, -1, True, float('nan'), 'invalid'])
def test_invalid_time_is_not_a_sample_at_zero(time):
    event = {'signals': {'a': 1, 'b': 2}}
    if time is not None:
        event['time_s'] = time
    with pytest.raises(ValueError):
        correlate({'events': [event]})


@pytest.mark.parametrize('bases', [('device-a', 'device-b'), ('unknown', 'unknown')])
def test_unaligned_clock_domains_are_not_correlated(bases):
    with pytest.raises(ValueError):
        correlate({'events': [{'time_s': 1, 'time_basis': base, 'signals': {'a': 1}} for base in bases]})


def test_conflicting_samples_do_not_silently_overwrite():
    with pytest.raises(ValueError):
        correlate({'events': [{'time_s': 1, 'signals': {'a': value}} for value in [1, 2]]})


def test_physical_samples_join_by_timestamp_and_ignore_boolean_states():
    events = [{'time_s': t, 'signals': {'a': {'physical_value': t, 'value': t * 10}, 'state': True}}
              for t in [1, 2, 3, 4]]
    events += [{'timestamp_s': t, 'signals': {'b': 2 * t}} for t in [4, 3, 2, 7]]
    result = correlate({'events': events})
    assert result['correlations'] == [{'left': 'a', 'right': 'b', 'samples': 3, 'pearson_r': 1.0}]
    assert result['causality_proven'] is False
