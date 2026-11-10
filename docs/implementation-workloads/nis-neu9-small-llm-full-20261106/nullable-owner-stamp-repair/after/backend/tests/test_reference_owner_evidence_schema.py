"""Private native ownership alternatives must agree with the public evidence gate."""
from copy import deepcopy
import hashlib

import pytest
from jsonschema import Draft202012Validator, ValidationError

from backend.nis.agent.orchestration import local_reasoner as r
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_design import fixture_request, fixture_design


def owner_case(kind, owner, *, compact):
    text = 'Authored unit-test ownership review; not original-model evidence.'
    reference = dict(id='owner-review', name='Authored owner review', role='USER_CLARIFICATION',
                     text=text, source_sha256=hashlib.sha256(text.encode()).hexdigest(),
                     allowed_fields=['function_hosts'])
    prepared = intake.prepare_reference_design(fixture_request(references=[reference]))
    base = intake.ReferenceDesignProposal.model_validate(fixture_design(prepared)).model_dump(mode='json')
    controller = next(row for row in base['devices'] if row['kind'] == 'CONTROLLER')
    if kind == 'PHYSICAL_CONTEXT':
        fact_id = next(key for key, fact in prepared['facts'].items() if fact['kind'] == 'REQUIREMENT')
        row = dict(id='probe-context', name='Authored enclosure', kind=kind, quantity=1,
                   context_kind='PASSIVE', source_fact_ids=[fact_id], rationale='Authored passive context')
        row = intake.ReferenceDesignProposal.model_validate({'devices': [row]}).model_dump(mode='json')['devices'][0]
    else:
        row = deepcopy(next(row for row in base['devices'] if row['kind'] == kind))
        fact_id = row['source_fact_ids'][0]
    row['owner_device_id'] = controller['id'] if owner else None
    row['field_references'] = {'function_hosts': ['owner-review']} if owner else {'device_type': []}
    target = dict(fact_id=fact_id, member=None, names=[row['name'], row['name'] + ' second'],
                  minimum_rows=2, max_rows=2)
    schema = r._reference_schema_for_stage(prepared, {'devices'}, inventory_target=target,
                                          existing_devices=[controller])
    choices = {}
    for name in target['names']:
        slot = schema['properties']['inventory_choices']['properties'][name]
        variant = next(value for value in slot.get('anyOf', [slot])
                       if value['properties']['choice_kind']['enum'] == ['NEW_' + kind])
        choices[name] = {**deepcopy(row), 'id': variant['properties']['id']['enum'][0],
                         'name': name, 'choice_kind': 'NEW_' + kind}
    value = dict(devices=[], unresolved=[], inventory_complete=True,
                 inventory_choices=choices)
    codec = None
    if compact:
        schema, codec = r._reference_compact_inventory_schema(schema)
        for name, choice in choices.items():
            for key in codec[name]['NEW_' + kind]['constants']:
                choice.pop(key, None)
    return prepared, controller, target, schema, codec, value


def expanded(prepared, controller, target, codec, value):
    rows = r._reference_expand_inventory_choices([controller], value['inventory_choices'],
                                                  inventory_target=target, inventory_codec=codec)
    return {'devices': [controller, *rows]}


@pytest.mark.parametrize('kind', ['SENSOR', 'ACTUATOR', 'PHYSICAL_CONTEXT'])
@pytest.mark.parametrize('compact', [False, True])
def test_null_owner_rejects_even_empty_foreign_evidence_key(kind, compact):
    prepared, controller, target, schema, codec, value = owner_case(kind, False, compact=compact)
    Draft202012Validator(schema).validate(value)
    intake._validate_reference_inventory(expanded(prepared, controller, target, codec, value),
                                         prepared, (), partial=True)
    row = next(iter(value['inventory_choices'].values()))
    row['field_references']['function_hosts'] = []
    with pytest.raises(ValueError, match='fremden Entscheidungsfeld'):
        intake._validate_reference_inventory(expanded(prepared, controller, target, codec, value),
                                             prepared, (), partial=True)
    # The exact native failure shape must already be excluded at the decoder boundary.
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(value)


@pytest.mark.parametrize('kind', ['SENSOR', 'ACTUATOR', 'PHYSICAL_CONTEXT'])
@pytest.mark.parametrize('compact', [False, True])
def test_non_null_owner_and_authorized_evidence_survive_codec_and_public_gate(kind, compact):
    prepared, controller, target, schema, codec, value = owner_case(kind, True, compact=compact)
    Draft202012Validator(schema).validate(value)
    result = expanded(prepared, controller, target, codec, value)
    intake._validate_reference_inventory(result, prepared, (), partial=True)
    row = result['devices'][1]
    assert row['owner_device_id'] == controller['id']
    assert row['field_references'] == {'function_hosts': ['owner-review']}
    assert row['source_fact_ids'] == [target['fact_id']]
    assert row['name'] == target['names'][0]
    bad = deepcopy(value)
    next(iter(bad['inventory_choices'].values()))['field_references']['function_hosts'] = ['foreign-source']
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(bad)
    with pytest.raises(ValueError, match='Referenzquelle darf'):
        intake._validate_reference_inventory(expanded(prepared, controller, target, codec, bad),
                                             prepared, (), partial=True)
