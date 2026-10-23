"""Independent id-free native-port and lossless NIS allocation counterexamples."""
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator

from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_design import fixture_request, reference


def intent(owner='owner-a', technology='can'):
    return {'device_id': owner, 'technology': technology, 'role': 'LOCAL',
            'network_scope': 'authored-network', 'parameters': {},
            'rationale': 'Authored physical port decision.', 'field_references': {'ports': ['R1']}}


def prepared_schema(owners=('owner-a', 'owner-b')):
    prepared = intake.prepare_reference_design(fixture_request(references=[reference(('ports',))]))
    return prepared, reasoner._reference_schema_for_stage(prepared, {'ports'}, port_intent=True, device_ids=owners)


def allocate(existing, values, owners=('owner-a', 'owner-b')):
    codec = getattr(reasoner, '_reference_expand_port_intents', None)
    assert callable(codec), 'NIS must allocate identities rather than ask native inference to invent them.'
    return codec(existing, values, owners)


def native(*values):
    return {**intake.ReferenceDesignProposal().model_dump(mode='json'), 'port_intents': list(values),
            'port_intents_complete': True}


def test_native_port_intent_has_no_model_owned_identity():
    prepared, schema = prepared_schema()
    value = native(intent(), intent('owner-b'))
    for index, row in enumerate(value['port_intents']):
        Draft202012Validator(schema).validate({**native(row), 'port_intents_complete': index == 1})
    assert not Draft202012Validator(schema).is_valid(value)
    assert schema['properties']['ports']['maxItems'] == 0
    assert 'id' not in schema['properties']['port_intents']['items']['properties']
    rows = allocate([], value['port_intents'])
    Draft202012Validator(intake.reference_design_schema(prepared)).validate(
        {**intake.ReferenceDesignProposal().model_dump(mode='json'), 'ports': rows})


@pytest.mark.parametrize('same_details', [False, True])
def test_multiple_ports_of_one_owner_receive_unique_ids_without_deduplication(same_details):
    values = [intent(), intent(technology='can' if same_details else 'ethernet')]
    before = deepcopy(values)
    rows = allocate([], values)
    assert len(rows) == 2 and len({row['id'] for row in rows}) == 2
    assert [{key: value for key, value in row.items() if key != 'id'} for row in rows] == before
    assert values == before


def test_existing_ids_are_skipped_globally_and_existing_ports_never_modified():
    first = allocate([], [intent(), intent('owner-b')])
    existing = [{**row, 'device_id': 'earlier-owner'} for row in first]
    before = deepcopy(existing)
    following = allocate(existing, [intent(), intent(), intent('owner-b')])
    assert not {row['id'] for row in following} & {row['id'] for row in existing}
    assert len({row['id'] for row in following}) == 3
    assert existing == before and allocate(existing, [intent(), intent(), intent('owner-b')]) == following


def test_foreign_owner_and_model_supplied_identity_are_rejected():
    _, schema = prepared_schema()
    for value in (intent('foreign-owner'), {**intent(), 'id': 'existing-port'}):
        assert not Draft202012Validator(schema).is_valid(native(value))
        with pytest.raises(ValueError):
            allocate([], [value])


@pytest.mark.parametrize('values', [None, {}, [None], [1]])
def test_allocation_rejects_invalid_native_shapes(values):
    with pytest.raises((ValueError, TypeError)):
        allocate([], values)


def test_native_owner_is_selected_before_technical_decisions():
    _, schema = prepared_schema()
    assert next(iter(schema['properties']['port_intents']['items']['properties'])) == 'device_id'
