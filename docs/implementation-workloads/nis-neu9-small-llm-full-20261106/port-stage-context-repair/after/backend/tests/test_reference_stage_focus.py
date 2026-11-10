"""Current task scope must survive an inventory-to-IO/function stage boundary."""
from copy import deepcopy
import json

import pytest

from backend.nis.agent.orchestration import local_reasoner as r
from backend.tests.test_reference_reasoner import effective_reference_context


SELECTORS = ('device_ids_for_this_stage', 'port_ids_for_this_stage',
             'function_fact_ids_for_this_stage', 'producer_device_ids_for_this_stage')


def stage_change(stage, field, selector, selected):
    first = {'original_source': 'Complete authored source: communication needs physical ports; '
             'an explicitly offline controller has no network port. Preserve both cases.',
             'original_facts': {'F1': {'kind': 'REQUIREMENT', 'name': 'Full authored original'}},
             'planning_stage': 'Physical hardware inventory', 'instruction': 'Only hardware; all other arrays empty.',
             'output_fields_for_this_stage': ['devices'], 'inventory_target_for_this_stage': None,
             'derivation_fact_ids_for_this_stage': ['F1'],
             'current_candidate': {'devices': [{'id': 'controller-a', 'kind': 'CONTROLLER'},
                                               {'id': 'offline-controller', 'kind': 'CONTROLLER'}]},
             **{key: [] for key in SELECTORS}}
    initial, _, _ = r._reference_context_messages([], None, first, 'Authored stage protocol', 131072)
    history = [*initial, {'role': 'assistant', 'content': '{"inventory_choices":[],"inventory_complete":true}'}]
    current = deepcopy(first)
    current.update(planning_stage=stage, instruction='Now complete ONLY the selected '+field+' task.',
                   output_fields_for_this_stage=[field], derivation_fact_ids_for_this_stage=None)
    current[selector] = deepcopy(selected)
    return first, history, current


@pytest.mark.parametrize('stage,field,selector,selected', [
    ('Physical port demand', 'ports', SELECTORS[0], ['controller-a', 'offline-controller']),
    ('Port parameters', 'ports', SELECTORS[1], ['p1', 'p2']),
    ('Sensor measurements', 'measurements', SELECTORS[0], ['sensor-a']),
    ('Actuator commands', 'commands', SELECTORS[0], ['actuator-a']),
    ('Functional realization', 'functions', SELECTORS[2], ['F1', 'F2']),
    ('Producer communication', 'communication', SELECTORS[3], ['controller-a']),
])
def test_current_non_inventory_stage_is_literal_after_the_exact_cached_history(stage, field, selector, selected):
    first, history, current = stage_change(stage, field, selector, selected)
    before = deepcopy((first, history, current))
    messages, full, rebased = r._reference_context_messages(history, first, current, 'Authored stage protocol', 131072,
                                                          anchor=(history, first))
    assert messages[:-1] == history and not rebased
    assert effective_reference_context(messages) == current
    assert effective_reference_context(full) == current
    focus = json.loads(messages[-1]['content'])['nis_current_selection']
    assert focus['planning_stage'] == stage
    assert focus['instruction'] == current['instruction']
    assert focus['output_fields_for_this_stage'] == [field]
    assert focus[selector] == selected
    assert all(focus[key] == current[key] for key in SELECTORS)
    assert (first, history, current) == before
    assert current['original_source'] == first['original_source']
    assert r._reference_context_window(messages, 131072) == 131072
    focus[selector].clear()
    assert current[selector] == selected


def test_fresh_non_inventory_context_has_the_same_complete_literal_task_and_limits():
    _, _, current = stage_change('Physical port demand', 'ports', SELECTORS[0], ['controller-a'])
    messages, _, _ = r._reference_context_messages([], None, current, 'Authored stage protocol', 131072)
    assert effective_reference_context(messages) == current
    focus = json.loads(messages[-1]['content'])['nis_current_selection']
    assert focus['instruction'] == current['instruction']
    assert focus[SELECTORS[0]] == ['controller-a']
    required = sum(len(row['content'].encode('utf8')) for row in messages) + 8192 + 2048
    with pytest.raises(ValueError, match='keine Quelle gekürzt'):
        r._reference_context_window(messages, required-1)
