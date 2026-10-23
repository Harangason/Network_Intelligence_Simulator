"""Authored decoder/public-field counterexamples, never original acceptance."""
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator

from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_port_intent_allocation import prepared_schema, intent, native, allocate
from backend.tests.test_reference_design import fixture_request, reference


@pytest.mark.parametrize('identity', ['port-idc-eth-01', 'an-existing-arbitrary-id'])
def test_native_intent_excludes_every_existing_port_id(identity):
    existing = [{'id': identity, **intent('earlier-owner')}]
    before = deepcopy(existing)
    _, schema = prepared_schema(('selected-owner',))
    legacy = {**intake.ReferenceDesignProposal().model_dump(mode='json'),
              'ports': [{'id': identity, **intent('selected-owner')}]}
    assert not Draft202012Validator(schema).is_valid(legacy)
    assert not Draft202012Validator(schema).is_valid(native({'id': identity, **intent('selected-owner')}))
    Draft202012Validator(schema).validate(native(intent('selected-owner')))
    rows = allocate(existing, [intent('selected-owner')], ('selected-owner',))
    assert rows[0]['id'] != identity and existing == before


def test_fresh_namespace_skips_an_existing_matching_prefix():
    owner = ('selected-owner',)
    first = allocate([], [intent(owner[0])], owner)
    following = allocate(first, [intent(owner[0])], owner)
    assert first[0]['id'] != following[0]['id']
    assert following == allocate(first, [intent(owner[0])], owner)
    _, schema = prepared_schema(owner)
    Draft202012Validator(schema).validate(native(intent(owner[0])))


def test_native_new_id_is_bound_to_its_selected_participant():
    _, schema = prepared_schema()
    Draft202012Validator(schema).validate(native(intent('owner-a'), intent('owner-b')))
    rows = allocate([], [intent('owner-a'), intent('owner-b')])
    assert [row['device_id'] for row in rows] == ['owner-a', 'owner-b']
    assert rows[0]['id'] != rows[1]['id']
    assert not Draft202012Validator(schema).is_valid(native({'id': rows[0]['id'], **intent('owner-b')}))
    assert not Draft202012Validator(schema).is_valid(native(intent('foreign-owner')))
    with pytest.raises(ValueError):
        allocate([], [{'id': rows[0]['id'], **intent('owner-b')}])


@pytest.mark.parametrize('owners', [('only-owner',), ('owner-a', 'owner-b')])
def test_native_port_participant_is_chosen_before_opaque_generated_identity(owners):
    _, schema = prepared_schema(owners)
    fields = schema['properties']['port_intents']['items']['properties']
    assert next(iter(fields)) == 'device_id'
    assert 'id' not in fields


@pytest.mark.parametrize('count', [1, 5, 17])
def test_fresh_intents_preserve_unbounded_need_and_public_contract(count):
    prepared, schema = prepared_schema(('selected-owner',))
    public = deepcopy(intake.reference_design_schema(prepared))
    value = native(*(intent('selected-owner') for _ in range(count)))
    Draft202012Validator(schema).validate(value)
    rows = allocate([], value['port_intents'], ('selected-owner',))
    assert len(rows) == count and len({row['id'] for row in rows}) == count
    Draft202012Validator(public).validate(
        {**intake.ReferenceDesignProposal().model_dump(mode='json'), 'ports': rows})
    assert intake.reference_design_schema(prepared) == public
    bad = deepcopy(value)
    bad['port_intents'][0]['parameters'] = {'bitrate_bps': 500000}
    assert not Draft202012Validator(schema).is_valid(bad)


def test_non_intent_parameter_stage_preserves_exact_existing_port_keys():
    prepared = intake.prepare_reference_design(fixture_request(references=[reference(('ports',))]))
    schema = reasoner._reference_schema_for_stage(prepared, {'ports'}, port_ids=('legacy-port',))
    assert schema['properties']['port_parameters']['required'] == ['legacy-port']
    assert schema['properties']['ports']['maxItems'] == 0
