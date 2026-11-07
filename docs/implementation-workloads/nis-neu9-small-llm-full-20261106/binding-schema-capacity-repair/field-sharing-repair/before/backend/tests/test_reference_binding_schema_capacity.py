"""Authored large-inventory decoder checks; never Original acceptance."""
from copy import deepcopy
import json

import pytest
from jsonschema import Draft202012Validator, ValidationError

from backend.nis.agent.orchestration import local_reasoner as r
from backend.tests.test_reference_planning_throughput import existing_batch_fixture
from backend.tests.test_reference_reasoner import native_existing_bindings


def large_binding_case(count=251):
    prepared, known, fact, _, _, base = existing_batch_fixture()
    known = [dict(deepcopy(known[0]), id=f'authored-{i:03}', name=f'Authored controller {i}')
             for i in range(count)]
    choices = [dict(choice_kind='EXISTING', device_id=row['id'], source_fact_ids=[fact],
                    rationale='Independent source-bound counter', field_references={}) for row in known]
    schema = r._reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=[fact], existing_devices=known)
    return prepared, known, fact, choices, schema, base


def test_large_binding_schema_has_bounded_transport_size_and_growth():
    sizes = [len(json.dumps(large_binding_case(count)[4], separators=(',', ':')).encode())
             for count in (32, 64, 251)]
    assert sizes[1] < sizes[0] * 2.5
    assert sizes[2] < 4 * 1024 * 1024


def test_large_binding_schema_preserves_first_last_and_sparse_eight_choices():
    _, known, _, choices, schema, base = large_binding_case()
    validator = Draft202012Validator(schema)
    for indices in ([0], [250], [0, 1, 17, 63, 127, 200, 249, 250]):
        rows = [choices[i] for i in indices]
        wire = native_existing_bindings(rows)
        validator.validate({**base, 'inventory_choices': [wire]})
        expanded = r._reference_expand_inventory_choices(known, [wire])
        assert [row['id'] for row in expanded] == [known[i]['id'] for i in indices]


@pytest.mark.parametrize('fault', ['nine', 'descending', 'foreign', 'already_bound'])
def test_large_binding_schema_keeps_structural_and_missing_source_guards(fault):
    prepared, known, fact, choices, _, base = large_binding_case()
    if fault == 'already_bound':
        known[250]['source_fact_ids'].append(fact)
    schema = r._reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=[fact], existing_devices=known)
    rows = (choices[:9] if fault == 'nine' else [choices[250], choices[0]] if fault == 'descending'
            else [dict(choices[0], device_id='foreign')] if fault == 'foreign' else [choices[250]])
    def without_object_counts(value):
        if isinstance(value, dict):
            return {key: without_object_counts(item) for key, item in value.items()
                    if key not in {'minProperties', 'maxProperties'}}
        return [without_object_counts(item) for item in value] if isinstance(value, list) else value
    with pytest.raises(ValidationError):
        Draft202012Validator(without_object_counts(schema)).validate(
            {**base, 'inventory_choices': [native_existing_bindings(rows)]})
