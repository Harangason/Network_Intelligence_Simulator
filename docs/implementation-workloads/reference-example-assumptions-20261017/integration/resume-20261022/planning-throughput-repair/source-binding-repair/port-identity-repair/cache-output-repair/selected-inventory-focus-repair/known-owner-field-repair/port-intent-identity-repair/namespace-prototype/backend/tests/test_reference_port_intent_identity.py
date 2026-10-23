"""Authored native identity counterexamples, not original-model acceptance."""
from copy import deepcopy
import inspect

import pytest
from jsonschema import Draft202012Validator

from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_design import fixture_request, reference


def schema_for(owners, existing=()):
    prepared = intake.prepare_reference_design(fixture_request(references=[reference(('ports',))]))
    options = {'port_intent': True, 'device_ids': owners}
    # Exercise the actual old implementation too, without a signature-only RED.
    if 'existing_ports' in inspect.signature(reasoner._reference_schema_for_stage).parameters:
        options['existing_ports'] = existing
    return prepared, reasoner._reference_schema_for_stage(prepared, {'ports'}, **options)


def port(identity, owner):
    return {'id': identity, 'device_id': owner, 'technology': 'can', 'role': 'LOCAL',
            'network_scope': 'authored-network', 'parameters': {},
            'rationale': 'Authored participant connection.', 'field_references': {}}


def proposal(*ports):
    return {**intake.ReferenceDesignProposal().model_dump(mode='json'), 'ports': list(ports)}


def fresh_id(schema, owner, suffix='01'):
    definition = schema['$defs']['ReferencePort']
    for variant in definition.get('anyOf', [definition]):
        fields = variant['properties']
        if owner in fields['device_id']['enum']:
            pattern = fields['id'].get('pattern')
            return pattern[1:].split('[', 1)[0] + suffix if pattern else 'authored-fresh-' + suffix
    raise AssertionError('Selected participant missing from native schema')


@pytest.mark.parametrize('identity', ['port-idc-eth-01', 'an-existing-arbitrary-id'])
def test_native_intent_excludes_every_existing_port_id(identity):
    existing = [port(identity, 'earlier-owner')]
    before = deepcopy(existing)
    _, schema = schema_for(('selected-owner',), existing)
    assert not Draft202012Validator(schema).is_valid(proposal(port(identity, 'selected-owner')))
    assert existing == before


def test_fresh_namespace_skips_an_existing_matching_prefix():
    _, first = schema_for(('selected-owner',))
    previously_allocated = fresh_id(first, 'selected-owner')
    _, following = schema_for(('selected-owner',), [port(previously_allocated, 'selected-owner')])
    assert not Draft202012Validator(following).is_valid(
        proposal(port(previously_allocated, 'selected-owner')))
    Draft202012Validator(following).validate(proposal(port(fresh_id(following, 'selected-owner'), 'selected-owner')))


def test_native_new_id_is_bound_to_its_selected_participant():
    _, schema = schema_for(('owner-a', 'owner-b'))
    identity = fresh_id(schema, 'owner-a')
    Draft202012Validator(schema).validate(proposal(port(identity, 'owner-a')))
    assert not Draft202012Validator(schema).is_valid(proposal(port(identity, 'owner-b')))
    assert not Draft202012Validator(schema).is_valid(proposal(port(identity, 'foreign-owner')))


@pytest.mark.parametrize('owners', [('only-owner',), ('owner-a', 'owner-b')])
def test_native_port_participant_is_chosen_before_opaque_generated_identity(owners):
    # The native same-prompt counterprobe chose owner-a twice when an opaque
    # ID namespace preceded device_id. Choosing the participant first fixed it.
    _, schema = schema_for(owners)
    definition = schema['$defs']['ReferencePort']
    for variant in definition.get('anyOf', [definition]):
        assert next(iter(variant['properties'])) == 'device_id'


@pytest.mark.parametrize('count', [1, 5, 17])
def test_fresh_intents_preserve_unbounded_need_and_public_contract(count):
    prepared, schema = schema_for(('selected-owner',))
    public = deepcopy(intake.reference_design_schema(prepared))
    value = proposal(*(port(fresh_id(schema, 'selected-owner', str(index)), 'selected-owner')
                       for index in range(count)))
    Draft202012Validator(schema).validate(value)
    Draft202012Validator(public).validate(value)
    assert intake.reference_design_schema(prepared) == public
    bad = deepcopy(value)
    bad['ports'][0]['parameters'] = {'bitrate_bps': 500000}
    assert not Draft202012Validator(schema).is_valid(bad)


def test_non_intent_parameter_stage_preserves_exact_existing_port_keys():
    prepared = intake.prepare_reference_design(fixture_request(references=[reference(('ports',))]))
    schema = reasoner._reference_schema_for_stage(prepared, {'ports'}, port_ids=('legacy-port',))
    assert schema['properties']['port_parameters']['required'] == ['legacy-port']
    assert schema['properties']['ports']['maxItems'] == 0
