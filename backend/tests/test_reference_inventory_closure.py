"""Authored finite-inventory closure checks; no original acceptance evidence."""
from copy import deepcopy
import json

import pytest
from jsonschema import Draft202012Validator, ValidationError

from backend.nis.agent.orchestration import local_reasoner as r
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_design import fixture_request, fixture_design


def closure_case():
    request = fixture_request(sensor_group='3 Sensoren')
    source, encoded = request['prompt'].split('\n- Dokument-Geräte: ', 1)
    envelope = json.loads(encoded)
    fact = next(row for row in envelope['facts'] if row['role'] == 'SENSOR')
    fact.update(kind='INSTANCE', quantity=3)
    envelope['devices'].append({**fact, 'minimum': False})
    request['prompt'] = source + '\n- Dokument-Geräte: ' + json.dumps(envelope)
    prepared = intake.prepare_reference_design(request)
    sensor = next(row for row in intake.ReferenceDesignProposal.model_validate(
        fixture_design(prepared)).model_dump(mode='json')['devices'] if row['kind'] == 'SENSOR')
    fact_id = sensor['source_fact_ids'][0]
    names = [row['name'] for row in prepared['catalog']['source_devices']
             if row['evidence']['source_quote'] == '3 Sensoren']
    assert len(names) == 3
    known = [{**deepcopy(sensor), 'id': f'authored-{index}', 'name': name}
             for index, name in enumerate(names)]
    target = dict(fact_id=fact_id, member=None, names=[], minimum_rows=0, max_rows=1)
    return prepared, known, target


def test_native_completed_exact_instances_accept_only_empty_complete_delta():
    prepared, known, target = closure_case()
    schema = r._reference_schema_for_stage(prepared, {'devices'}, inventory_target=target,
                                         existing_devices=known)
    validator = Draft202012Validator(schema)
    empty = {'devices': [], 'unresolved': [], 'inventory_choices': [], 'inventory_complete': True}
    validator.validate(empty)
    # A fresh ID does not justify redeclaring an already covered original name.
    variant = schema['properties']['inventory_choices']['items']
    variant = next(row for row in variant.get('anyOf', [variant])
                   if row['properties']['choice_kind']['enum'] == ['NEW_SENSOR'])
    duplicate = {**deepcopy(known[0]), 'choice_kind': 'NEW_SENSOR',
                 'id': variant['properties']['id']['enum'][0]}
    for complete in (True, False):
        with pytest.raises(ValidationError):
            validator.validate({**empty, 'inventory_complete': complete, 'inventory_choices': [duplicate]})
    with pytest.raises(ValidationError):
        validator.validate({**empty, 'inventory_complete': False})
    merged = r._reference_merge_inventory_devices(known, [], target, prepared['facts'])
    assert merged == known
    assert not r._reference_inventory_progress(known, merged)


@pytest.mark.parametrize('fault', ['missing', 'wrong_name', 'wrong_source', 'wrong_member',
                                  'duplicate_id', 'duplicate_name', 'wrong_quantity', 'excess',
                                  'requested_name', 'requested_count', 'category'])
def test_incomplete_or_open_source_cannot_be_forced_closed(fault):
    prepared, known, target = closure_case()
    if fault == 'missing': known.pop()
    elif fault == 'wrong_name': known[0]['name'] = 'not the original instance'
    elif fault == 'wrong_source': known[0]['source_fact_ids'] = []
    elif fault == 'wrong_member': target['member'] = 'unbound member'
    elif fault == 'duplicate_id': known[0]['id'] = known[1]['id']
    elif fault == 'duplicate_name': known[0]['name'] = known[1]['name']
    elif fault == 'wrong_quantity': known[0]['quantity'] = 2
    elif fault == 'excess': known.append({**known[0], 'id': 'excess', 'name': 'excess'})
    elif fault == 'requested_name': target['names'] = ['still requested']
    elif fault == 'requested_count': target['minimum_rows'] = 1
    elif fault == 'category': prepared['facts'][target['fact_id']].update(kind='CATEGORY', quantity=None)
    assert not r._reference_inventory_closed(prepared, target, known)


def test_closure_is_scoped_and_does_not_drop_open_questions_or_later_hardware():
    prepared, known, target = closure_case()
    schema = r._reference_schema_for_stage(prepared, {'devices'}, inventory_target=target,
                                         existing_devices=known)
    base = intake.reference_model_output_schema(prepared)
    assert schema['properties']['unresolved'] == base['properties']['unresolved']
    assert r._reference_inventory_closed(prepared, target, known)
    assert not r._reference_inventory_closed(prepared, None, known)
    fact = next(key for key, row in prepared['facts'].items() if row['kind'] == 'FUNCTION')
    functional = r._reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=[fact],
                                             existing_devices=known)
    assert functional['properties']['inventory_choices']['maxItems'] == 1
    assert functional['properties']['inventory_complete'] == {'type': 'boolean'}
    assert any(variant['properties']['inventory_complete']['enum'] == [False]
               for variant in functional['anyOf'])
