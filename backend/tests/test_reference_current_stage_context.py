"""Independent current-stage wire checks; no Original model or acceptance data."""
from copy import deepcopy
import json

import pytest

from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.tests.test_reference_inventory_context_capacity import authored_cohort_context
from backend.tests.test_reference_reasoner import effective_reference_context


def authored_port_context():
    context = authored_cohort_context(251, 50)
    context.update(inventory_target_for_this_stage=None,
                   derivation_fact_ids_for_this_stage=None,
                   planning_stage='Physical connections of selected participants',
                   output_fields_for_this_stage=['ports'],
                   device_ids_for_this_stage=['authored-device-024', 'authored-device-025'],
                   instruction='Plan all selected physical connections; no invented qualification.')
    context['current_candidate']['unresolved'] = [
        {'code': 'UNKNOWN_PHY', 'target_ref': 'authored-device-024', 'message': 'Qualification is unknown.'}]
    context['selected_port_function_context'] = {
        'authored-device-024': {'literal_function': 'Receive µ state; retain /~ identity.'}}
    return context


@pytest.mark.parametrize('transition', ['fresh', 'append', 'rebase'])
def test_selected_current_records_are_directly_readable_after_each_context_transition(transition):
    current = authored_port_context()
    early = deepcopy(current)
    early['current_candidate']['devices'] = early['current_candidate']['devices'][:51]
    early['device_ids_for_this_stage'] = ['authored-device-000']
    messages, _, _ = reasoner._reference_context_messages([], None, early, 'Independent', 131072)
    anchor = ([*messages, {'role': 'assistant', 'content': '{"authored":true}'}], early)
    history = anchor[0] if transition != 'fresh' else []
    if transition == 'rebase':
        history = [*history, {'role': 'user', 'content': 'overflow' * 17000}]
    before = deepcopy((current, early, history))
    result, _, rebased = reasoner._reference_context_messages(
        history, early if history else None, current, 'Independent', 131072,
        anchor=anchor if history else None)
    if transition == 'rebase':
        assert rebased
    selection = json.loads(result[-1]['content'])['nis_current_selection']
    actual = current['current_candidate']['devices']
    expected = [row for identity in current['device_ids_for_this_stage']
                for row in actual if row['id'] == identity]
    assert selection['selected_devices'] == expected
    assert selection['inventory_counts_by_kind'] == {
        'CONTROLLER': 50, 'GATEWAY': 1, 'SENSOR': 100, 'ACTUATOR': 100}
    assert selection['selected_port_function_context'] == current['selected_port_function_context']
    assert effective_reference_context(result) == current
    assert (current, early, history) == before
    selection['selected_devices'][0]['purpose'] = 'Do not mutate original'
    assert current == before[0]


def test_current_projection_does_not_fill_missing_members_or_resolve_real_findings():
    context = authored_port_context()
    context['current_candidate']['devices'] = context['current_candidate']['devices'][:151]
    messages, _, _ = reasoner._reference_context_messages([], None, context, 'Independent', 131072)
    selection = json.loads(messages[-1]['content'])['nis_current_selection']
    assert selection['inventory_counts_by_kind'].get('ACTUATOR', 0) == 0
    assert effective_reference_context(messages)['current_candidate']['unresolved'] == context['current_candidate']['unresolved']
    assert effective_reference_context(messages) == context
