"""Independent cached-wire counterexamples; no native or Original acceptance."""
from copy import deepcopy
import pytest

from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.tests.test_reference_reasoner import effective_reference_context


def authored_anchor(context, padding=0):
    messages, _, _ = reasoner._reference_context_messages([], None, context, 'system', 131072)
    return ([*messages, {'role': 'assistant',
                        'content': ' \n' + ' ' * padding + '{"authored_reply":true}\n '}],
            deepcopy(context))


def wire_bytes(messages):
    return sum(len(row['content'].encode('utf8')) for row in messages)


@pytest.mark.parametrize('source', ['Original\r\n' + 's' * 30000,
                                  'Quelle µ 🦾 /~\n' * 1200], ids=['ascii', 'unicode'])
def test_fitting_cached_history_survives_a_smaller_old_anchor(source):
    first = {'original_source': source, 'current_candidate': {'notes': ''},
             'typed': [False, 0, 0.0, None]}
    anchor = authored_anchor(first)
    previous = deepcopy(first)
    previous['current_candidate']['notes'] = 'g' * 10000
    before, _, _ = reasoner._reference_context_messages(
        anchor[0], first, previous, 'system', 131072, anchor=anchor)
    history = [*before, {'role': 'assistant', 'content': ' \n{"page":1}\n ' + ' ' * 8000}]
    current = deepcopy(previous)
    current['planning_stage'] = 'Next source-bound physical port'
    original = deepcopy((history, previous, current, anchor))

    messages, fallback, rebased = reasoner._reference_context_messages(
        history, previous, current, 'system', 131072, anchor=anchor)

    assert reasoner._reference_context_window(messages, 131072) == 131072
    assert wire_bytes(fallback) < wire_bytes(messages), 'Counterexample must include a smaller fallback'
    assert not rebased, 'A fitting exact current cache prefix was discarded for fewer total bytes'
    assert messages[:-1] == history
    assert effective_reference_context(messages) == current
    assert effective_reference_context(fallback) == current
    assert (history, previous, current, anchor) == original


def test_successive_port_pages_reuse_the_exact_immediately_preceding_wire():
    initial = {'original_source': 'Complete original µ 🦾\r\n' + 's' * 20000,
               'current_candidate': {'ports': []}, 'typed': [False, 0, None]}
    anchor = authored_anchor(initial)
    history, previous = deepcopy(anchor[0]), deepcopy(initial)
    for ordinal in range(1, 30):
        current = deepcopy(previous)
        # Identical parallel physical records remain distinct; this is a cache
        # preservation test and must not silently deduplicate real ports.
        current['current_candidate']['ports'].append({
            'id': f'port-{ordinal}', 'device_id': 'same-owner', 'technology': 'can',
            'role': 'LOCAL', 'parameters': {}, 'rationale': 'Authored physical occurrence',
            'source_fact_ids': ['original-source-fact']})
        messages, _, rebased = reasoner._reference_context_messages(
            history, previous, current, 'system', 131072, anchor=anchor)
        assert not rebased and messages[:-1] == history, f'Cache prefix lost on page {ordinal}'
        assert effective_reference_context(messages) == current
        assert len(effective_reference_context(messages)['current_candidate']['ports']) == ordinal
        assert reasoner._reference_context_window(messages, 131072) == 131072
        history = [*messages, {'role': 'assistant', 'content': f' \n{{"page":{ordinal}}}\n '}]
        previous = current


def test_overflow_fallback_keeps_longer_matching_native_prefix_not_smaller_old_anchor():
    early = {'original_source': 'Original\r\n' + 's' * 20000,
             'current_candidate': {'notes': ''}, 'typed': [False, 0, None]}
    older = authored_anchor(early)
    previous = deepcopy(early)
    previous['current_candidate']['notes'] = 'n' * 50000
    newer = authored_anchor(previous, padding=4000)
    history = deepcopy(newer[0])
    for _ in range(9):
        history.extend([{'role': 'user', 'content': '{"nis_context_patch":[]}'},
                        {'role': 'assistant', 'content': ' ' * 7000 + '{"authored_reply":true}'}])
    current = deepcopy(previous)
    current['planning_stage'] = 'Next bounded decision'
    with pytest.raises(ValueError, match='keine Quelle gekürzt'):
        reasoner._reference_context_window(history, 131072)

    messages, fallback, rebased = reasoner._reference_context_messages(
        history, previous, current, 'system', 131072, anchor=newer, anchors=(older,))
    assert rebased and messages == fallback
    assert messages[:len(newer[0])] == newer[0], 'Longer reusable native prefix discarded'
    assert effective_reference_context(messages) == current
    assert reasoner._reference_context_window(messages, 131072) == 131072


@pytest.mark.parametrize('multiplier', [1, 2])
def test_no_cached_prefix_can_accept_oversized_complete_source(multiplier):
    original = {'original_source': 'small', 'current_candidate': {'ports': []}}
    anchor = authored_anchor(original)
    current = deepcopy(original)
    current['original_source'] = '🦾' * (131072 * multiplier // 4)
    with pytest.raises(ValueError, match='keine Quelle gekürzt'):
        reasoner._reference_context_messages(
            anchor[0], original, current, 'system', 131072, anchor=anchor)


def test_foreign_protocol_anchor_remains_rejected_even_with_fitting_history():
    current = {'original_source': 'Original', 'current_candidate': {'ports': []}}
    anchor = authored_anchor(current)
    foreign = deepcopy(anchor)
    foreign[0][0]['content'] = 'foreign protocol'
    with pytest.raises(ValueError, match='Planungsprotokoll'):
        reasoner._reference_context_messages(
            anchor[0], current, current, 'system', 131072, anchor=foreign)


def test_initial_complete_snapshot_is_not_misreported_as_a_rebase():
    current = {'original_source': 'Original µ 🦾\r\n', 'current_candidate': {'ports': []}}
    messages, fallback, rebased = reasoner._reference_context_messages(
        [], None, current, 'system', 131072)
    assert not rebased and messages == fallback
    assert effective_reference_context(messages) == current
