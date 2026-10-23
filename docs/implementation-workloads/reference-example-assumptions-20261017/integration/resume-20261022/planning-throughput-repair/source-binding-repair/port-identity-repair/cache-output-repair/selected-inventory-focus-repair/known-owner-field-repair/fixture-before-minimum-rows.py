"""Authored decoder/public-field counterexamples, never original acceptance."""
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator

from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_design import fixture_request, reference
from backend.tests.test_reference_reasoner import complete_design, native_existing_bindings


def existing_selection(identity, fields, *, owned=False):
    prepared = intake.prepare_reference_design(fixture_request(
        references=[reference(('device_type', 'function_hosts'))]))
    known = intake.ReferenceDesignProposal.model_validate(complete_design(prepared)).model_dump(mode='json')['devices']
    selected = next(row for row in known if row['id'] == identity)
    selected['owner_device_id'] = 'C' if owned else None
    fact = next(key for key, row in prepared['facts'].items() if row['kind'] == 'FUNCTION')
    choice = native_existing_bindings([{'device_id': identity, 'source_fact_ids': [fact],
        'rationale': 'Independent field eligibility example.', 'field_references': deepcopy(fields)}])
    value = {**intake.ReferenceDesignProposal().model_dump(mode='json'),
             'inventory_complete': True, 'inventory_choices': [choice]}
    schema = reasoner._reference_schema_for_stage(prepared, {'devices'},
        derivation_fact_ids=[fact], existing_devices=known)
    expanded = reasoner._reference_expand_inventory_choices(known, [choice])
    delta = reasoner._reference_scoped_inventory_delta(known, expanded, derivation_fact_ids=[fact])
    merged = reasoner._reference_merge_inventory_devices(known, delta,
        {'derivation_fact_ids': [fact]}, prepared['facts'])
    return prepared, known, value, schema, merged


@pytest.mark.parametrize('identity', ['C', 'S'])
@pytest.mark.parametrize('references', [['R1'], []])
def test_ownerless_existing_identity_cannot_emit_function_host_field(identity, references):
    prepared, known, value, schema, merged = existing_selection(identity, {'function_hosts': references})
    before = deepcopy(known)
    with pytest.raises(ValueError, match='fremden Entscheidungsfeld'):
        intake._validate_reference_inventory({'devices': merged}, prepared, (), partial=True)
    assert known == before, 'Binding/validation must preserve the immutable existing owner and identity.'
    assert not Draft202012Validator(schema).is_valid(value), (
        'Native grammar must exclude a known ineligible field, including its empty key.')


@pytest.mark.parametrize('identity', ['C', 'S'])
def test_ownerless_existing_identity_keeps_device_type_and_quantity_fields(identity):
    prepared, known, value, schema, merged = existing_selection(identity,
        {'device_type': ['R1'], 'quantity': []})
    Draft202012Validator(schema).validate(value)
    intake._validate_reference_inventory({'devices': merged}, prepared, (), partial=True)
    old = next(row for row in known if row['id'] == identity)
    current = next(row for row in merged if row['id'] == identity)
    assert current['owner_device_id'] is None
    assert all(current[key] == old[key] for key in ('id', 'name', 'kind', 'quantity'))
    assert set(old['source_fact_ids']) < set(current['source_fact_ids'])
    assert current['field_references'] == {'device_type': ['R1'], 'quantity': []}


def test_owned_existing_sensor_keeps_function_host_reference():
    prepared, _, value, schema, merged = existing_selection('S', {'function_hosts': ['R1']}, owned=True)
    Draft202012Validator(schema).validate(value)
    intake._validate_reference_inventory({'devices': merged}, prepared, (), partial=True)
    sensor = next(row for row in merged if row['id'] == 'S')
    assert sensor['owner_device_id'] == 'C'
    assert sensor['field_references'] == {'function_hosts': ['R1']}


def test_logical_function_keeps_executor_reference_with_keyed_selection():
    prepared = intake.prepare_reference_design(fixture_request(
        references=[reference(('function_hosts',))]))
    design = intake.ReferenceDesignProposal.model_validate(complete_design(prepared)).model_dump(mode='json')
    function = design['functions'][0]
    function['field_references'] = {'function_hosts': ['R1']}
    fact = function['source_fact_id']
    value = {**intake.ReferenceDesignProposal().model_dump(mode='json'),
             'functions_by_fact': {fact: {key: deepcopy(item) for key, item in function.items()
                                         if key != 'source_fact_id'}}}
    schema = reasoner._reference_schema_for_stage(prepared, {'functions'}, function_ids=[fact])
    Draft202012Validator(schema).validate(value)
    reviewed = intake.validate_reference_design(design, prepared)
    assert reviewed['approval_required'] and not reviewed['canonical_writes']
    assert reviewed['status'] == 'REVIEW_REQUIRED'


def test_source_field_eligibility_is_not_widened_for_an_owned_sensor():
    prepared, _, value, schema, merged = existing_selection('S', {'quantity': ['R1']}, owned=True)
    assert not Draft202012Validator(schema).is_valid(value)
    with pytest.raises(ValueError, match='Referenz'):
        intake._validate_reference_inventory({'devices': merged}, prepared, (), partial=True)
