"""Authored private-context capacity checks, never native Original acceptance."""
from copy import deepcopy
import hashlib
import json

import pytest

from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.tests.test_reference_reasoner import effective_reference_context


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def authored_context(size=147, source_lines=800):
    devices = [{
        'id': f'authored-device-{i:03}', 'name': f'Independent device {i:03} µ',
        'kind': ('CONTROLLER' if i < 50 else 'GATEWAY' if i == 50 else
                 'SENSOR' if i < 151 else 'ACTUATOR'),
        'quantity': 1, 'source_fact_ids': [f'F{i % 3}'],
        'source_member_bindings': {f'F{i % 3}': f'independent member {i % 13}'},
        'owner_device_id': None,
        'purpose': 'Independently authored purpose, not original evidence.',
        'rationale': 'Complete authored source-preserving inventory decision.',
        'context_kind': None, 'contained_device_ids': [], 'field_references': {},
    } for i in range(size)]
    return {
        'original_source': ''.join(
            f'Unchanged authored source line {i:04}: full quantities, requirements and literal values.\n'
            for i in range(source_lines)),
        'planning_stage': 'Independent inventory counter',
        'inventory_target_for_this_stage': {
            'fact_id': 'F-counter', 'member': None, 'names': ['next'],
            'minimum_rows': 1, 'max_rows': 1},
        'derivation_fact_ids_for_this_stage': None,
        'current_candidate': {'devices': devices},
        'existing_inventory_for_this_stage': [
            {key: row[key] for key in ('id', 'name', 'kind')} for row in devices],
    }


def read_selection(value):
    """Independent reader of the existing literal/table vocabulary."""
    inventory = value['existing_inventory']
    if isinstance(inventory, list):
        return deepcopy(inventory)
    assert set(inventory) == {'columns', 'constants', 'rows'}
    assert len(inventory['columns']) == len(set(inventory['columns']))
    return [{**deepcopy(inventory['constants']),
             **dict(zip(inventory['columns'], row, strict=True))}
            for row in inventory['rows']]


def expected_selection(context):
    return [{key: deepcopy(row[key]) for key in
             ('id', 'name', 'kind', 'source_fact_ids', 'source_member_bindings')}
            for row in context['current_candidate']['devices']]


@pytest.mark.parametrize(('size', 'source_lines'), [(147, 800), (251, 500)])
def test_complete_large_inventory_and_direct_view_fit_without_relaxing_context(size, source_lines):
    current = authored_context(size, source_lines)
    before = encoded(current)
    messages, _, _ = reasoner._reference_context_messages(
        [], None, current, 'Independent counter only', 131072)
    assert encoded(effective_reference_context(messages)) == before
    selection = json.loads(messages[-1]['content'])['nis_current_selection']
    assert encoded(read_selection(selection)) == encoded(expected_selection(current))
    assert isinstance(selection['existing_inventory'], dict)
    assert len(read_selection(selection)) == size
    assert encoded(current) == before
    required = sum(len(row['content'].encode('utf-8')) for row in messages) + 8192 + 2048
    assert required <= 131072
    assert reasoner._reference_context_window(messages, 131072) == 131072
    with pytest.raises(ValueError, match='keine Quelle gekürzt'):
        reasoner._reference_context_window(messages, required - 1)


def test_latest_selection_preserves_every_binding_order_and_literal_after_cached_prefix():
    first = authored_context(20, 5)
    messages, _, _ = reasoner._reference_context_messages([], None, first, 'Independent', 131072)
    history = [*messages, {'role': 'assistant', 'content': '{"authored_counter":true}'}]
    current = deepcopy(first)
    current['inventory_target_for_this_stage']['member'] = 'next member µ /~'
    # Private transport must preserve all JSON values; these are serializer
    # adversarial data, not a claim that typed hardware bindings accept numbers.
    current['current_candidate']['devices'][7]['source_member_bindings'] = {
        'a/b~c': [False, 0, 0.0, -0.0, None, '0'], '': 'literal'}
    wire, _, _ = reasoner._reference_context_messages(
        history, first, current, 'Independent', 131072, anchor=(history, first))
    assert wire[:2] == messages
    assert encoded(effective_reference_context(wire)) == encoded(current)
    selection = json.loads(wire[-1]['content'])['nis_current_selection']
    assert selection['inventory_target'] == current['inventory_target_for_this_stage']
    assert encoded(read_selection(selection)) == encoded(expected_selection(current))
    assert isinstance(selection['existing_inventory'], dict)


def test_oversized_complete_input_still_has_bounded_diagnostic_with_exact_context_hash(caplog):
    current = authored_context(251, 800)
    before = encoded(current)
    with pytest.raises(ValueError, match='keine Quelle gekürzt'):
        reasoner._reference_context_messages([], None, current, 'Independent counter only', 131072)
    diagnostic = next(json.loads(row.message.split('Native reference context guard rejected complete input: ', 1)[1])
                      for row in caplog.records if 'Native reference context guard rejected complete input: ' in row.message)
    assert diagnostic['complete_context_sha256'] == hashlib.sha256(before.encode('utf-8')).hexdigest()
    assert 'complete_context' not in diagnostic
    assert current['original_source'][:60] not in caplog.text
    assert diagnostic['required_utf8_upper_bound'] > diagnostic['maximum'] == 131072
    assert encoded(current) == before
