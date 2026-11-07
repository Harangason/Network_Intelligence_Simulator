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


def authored_cohort_context(size=251, source_lines=500):
    """Mixed authored cohorts, not recovered native decisions or a source model."""
    current = authored_context(size, source_lines)
    for row in current['current_candidate']['devices']:
        cohort = row['kind']
        row['source_fact_ids'] = ['Authored-' + cohort]
        row['source_member_bindings'] = {}
        row['purpose'] = 'Independently authored ' + cohort + ' task without technical assumptions.'
        row['rationale'] = ('This independent authored ' + cohort
                            + ' record preserves its declared quantity and distinct physical identity.')
    return current


@pytest.mark.parametrize('size', [175, 251])
def test_mixed_cohort_inventory_preserves_full_source_within_unchanged_capacity(size):
    current = authored_cohort_context(size)
    original = encoded(current)
    messages, _, _ = reasoner._reference_context_messages([], None, current, 'Authored counter', 131072)
    assert encoded(effective_reference_context(messages)) == original
    assert encoded(current) == original
    selection = json.loads(messages[-1]['content'])['nis_current_selection']
    assert encoded(read_selection(selection)) == encoded(expected_selection(current))
    required = sum(len(row['content'].encode('utf-8')) for row in messages) + 8192 + 2048
    assert required <= 131072
    with pytest.raises(ValueError, match='keine Quelle gekürzt'):
        reasoner._reference_context_window(messages, required - 1)


def test_cohort_tables_keep_key_order_scalar_spellings_and_nested_pointers():
    from backend.tests.test_reference_context_delta_capacity import decode_wire
    from backend.tests.test_reference_planning_throughput import unpack_context_message
    keys = ['', 'a/b~c', 'µ 🦾', *[f'key-{i}' for i in range(29)]]
    original = {'a/b~c': {'': {key: {
        'id': f'row-{i}', 'physical_literal': [-0.0, 0.0, False, None][i // 8],
        'complete_literal': ('Unchanged independently authored group ' + str(i // 8) + ' µ ') * 12,
        'members': ['exact', i // 8],
    } for i, key in enumerate(keys)}}}
    wire = reasoner._reference_context_snapshot(original)
    assert encoded(decode_wire(wire)) == encoded(original)
    assert encoded(unpack_context_message(wire)) == encoded(original)
    assert list(decode_wire(wire)['a/b~c']['']) == keys
    # Long repeated cohort fields should be recorded once per contiguous cohort,
    # not repeated literals or one reconstruction operation per repeated field.
    assert len(encoded(wire).encode('utf-8')) < len(encoded(original).encode('utf-8')) // 3


def test_cached_cohort_context_retains_later_binding_change_without_mutation():
    first = authored_cohort_context(175, 20)
    messages, _, _ = reasoner._reference_context_messages([], None, first, 'Authored counter', 131072)
    current = deepcopy(first)
    current['current_candidate']['devices'][80]['source_member_bindings'] = {'a/b~c': 'new literal µ'}
    current['inventory_target_for_this_stage']['names'] = ['different requested identity']
    history = [*messages, {'role': 'assistant', 'content': '{"authored_only":true}'}]
    result, _, _ = reasoner._reference_context_messages(
        history, first, current, 'Authored counter', 131072, anchor=(messages, first))
    assert encoded(effective_reference_context(result)) == encoded(current)
    assert first['current_candidate']['devices'][80]['source_member_bindings'] == {}
    selection = json.loads(result[-1]['content'])['nis_current_selection']
    assert encoded(read_selection(selection)) == encoded(expected_selection(current))


def authored_many_cohort_context(size=251):
    """Independent small groups, not reconstructed native Original output."""
    current = authored_cohort_context(size, 500)
    for index, device in enumerate(current['current_candidate']['devices']):
        device['purpose'] = (f'Independently authored group {index // 8:02}: preserve measurement '
                             'processing and actuator feedback in the named functional group.')
        device['rationale'] = (f'Authored decision {index // 8:02}: this physical participant retains '
                               'its own original identity, source binding and explicit qualified limits.')
    return current


@pytest.mark.parametrize('size', [191, 251])
def test_many_small_cohorts_fit_complete_context_without_source_or_guard_changes(size):
    from backend.tests.test_reference_context_delta_capacity import decode_wire
    from backend.tests.test_reference_planning_throughput import unpack_context_message
    current = authored_many_cohort_context(size)
    before = encoded(current)
    packed = reasoner._reference_context_snapshot(current)
    assert encoded(decode_wire(packed)) == before
    assert encoded(unpack_context_message(packed)) == before
    messages, _, _ = reasoner._reference_context_messages(
        [], None, current, 'Authored capacity counter', 131072)
    assert encoded(effective_reference_context(messages)) == before
    assert encoded(read_selection(json.loads(messages[-1]['content'])['nis_current_selection'])) == encoded(expected_selection(current))
    assert encoded(current) == before
    required = sum(len(row['content'].encode('utf8')) for row in messages) + 8192 + 2048
    assert required <= 131072
    with pytest.raises(ValueError, match='keine Quelle gekürzt'):
        reasoner._reference_context_window(messages, required - 1)


def test_many_cohorts_keep_late_overrides_and_literal_boundaries():
    from backend.tests.test_reference_context_delta_capacity import decode_wire
    from backend.tests.test_reference_planning_throughput import unpack_context_message
    current = authored_many_cohort_context()
    rows = current['current_candidate']['devices']
    for index, row in enumerate(rows):
        row['field_references'] = {'a/b~c': [False, 0, 0.0, -0.0, None, '0'][index % 6]}
    rows[248]['purpose'] = 'Distinct late override only for participant248, never inherited by249.'
    before = encoded(current)
    packed = reasoner._reference_context_snapshot(current)
    assert encoded(decode_wire(packed)) == before
    assert encoded(unpack_context_message(packed)) == before
    assert encoded(current) == before
    decoded = decode_wire(packed)['current_candidate']['devices']
    assert len(decoded) == 251
    assert decoded[248]['purpose'] != decoded[249]['purpose']
    assert [row['id'] for row in decoded] == [row['id'] for row in rows]
