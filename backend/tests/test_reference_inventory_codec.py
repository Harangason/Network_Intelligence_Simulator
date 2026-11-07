"""Private response compression preserves the offered identity and native decisions."""
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, ValidationError

from backend.nis.agent.orchestration import local_reasoner as r
from backend.nis.agent.orchestration.project_intake import ReferenceDesignProposal
from backend.tests.test_reference_inventory_batch import batch_case


def codec_case():
    prepared, target, full, value = batch_case(8)
    schema, codec = r._reference_compact_inventory_schema(full)
    compact = deepcopy(value)
    for name, row in compact['inventory_choices'].items():
        for key in codec[name][row['choice_kind']]['constants']:
            row.pop(key, None)
    return prepared, target, full, value, schema, codec, compact


def test_native_wire_omits_only_offered_constants_and_restores_exact_public_rows():
    prepared, target, full, value, schema, codec, compact = codec_case()
    Draft202012Validator(schema).validate(compact)
    assert all(not {'id', 'name', 'kind', 'quantity', 'source_fact_ids', 'source_member_bindings',
                    'context_kind', 'contained_device_ids'} & row.keys()
               for row in compact['inventory_choices'].values())
    assert all({'owner_device_id', 'purpose', 'rationale', 'field_references'} <= row.keys()
               for row in compact['inventory_choices'].values())
    restored = r._reference_expand_inventory_choices([], compact['inventory_choices'],
        inventory_target=target, inventory_codec=codec)
    expected = r._reference_expand_inventory_choices([], value['inventory_choices'], inventory_target=target)
    assert restored == expected
    public = ReferenceDesignProposal.model_validate({'devices': restored}).model_dump(mode='json')['devices']
    merged = r._reference_merge_inventory_devices([], public, target, prepared['facts'])
    assert len({row['id'] for row in merged}) == 8
    assert [row['name'] for row in merged] == target['names']
    Draft202012Validator(full).validate(value)  # Input schema wasn't mutated.


@pytest.mark.parametrize('fault', ['id', 'name', 'kind', 'quantity', 'source_fact_ids',
                                   'source_member_bindings', 'context_kind', 'contained_device_ids',
                                   'choice_kind', 'missing_rationale', 'foreign_slot', 'missing_slot'])
def test_compact_wire_rejects_injection_and_missing_decisions_at_schema_and_runtime(fault):
    _, target, _, _, schema, codec, compact = codec_case()
    name = target['names'][0]; choices = compact['inventory_choices']
    if fault == 'missing_rationale': choices[name].pop('rationale')
    elif fault == 'foreign_slot': choices['foreign'] = choices.pop(name)
    elif fault == 'missing_slot': choices.pop(name)
    else: choices[name][fault] = 'foreign'
    with pytest.raises(ValidationError): Draft202012Validator(schema).validate(compact)
    with pytest.raises(ValueError):
        r._reference_expand_inventory_choices([], choices, inventory_target=target, inventory_codec=codec)


def test_codec_preserves_native_ownership_and_purpose_instead_of_seeding_topology():
    _, target, _, _, _, codec, compact = codec_case()
    row = compact['inventory_choices'][target['names'][0]]
    row.update(owner_device_id='native-owner', purpose='Native purpose', rationale='Native evidence')
    result = r._reference_expand_inventory_choices([], compact['inventory_choices'],
        inventory_target=target, inventory_codec=codec)
    assert result[0]['owner_device_id'] == 'native-owner'
    assert result[0]['purpose'] == 'Native purpose'
    assert result[0]['rationale'] == 'Native evidence'


def test_codec_does_not_change_unnamed_or_other_stage_schema():
    for schema in ({'properties': {'ports': {'type': 'array'}}},
                   {'properties': {'inventory_choices': {'type': 'array', 'items': {'type': 'object'}}}}):
        result, codec = r._reference_compact_inventory_schema(schema)
        assert result == schema
        assert codec == {}


def test_normal_planner_sends_only_open_decisions_and_preserves_complete_model(monkeypatch):
    from backend.tests.test_reference_inventory_batch import (
        test_normal_planner_batches_seventeen_literal_sensors_without_scope_loss)
    original = r._reference_stream_response
    seen = []

    async def observe(client, url, payload, report):
        choices = payload['format']['properties'].get('inventory_choices', {})
        if choices.get('type') == 'object':
            for slot in choices['properties'].values():
                for variant in slot.get('anyOf', [slot]):
                    if variant['properties']['choice_kind']['enum'] == ['NEW_SENSOR']:
                        assert 'id' not in variant['properties']
                        assert 'source_fact_ids' not in variant['properties']
            seen.append(len(choices['properties']))
        return await original(client, url, payload, report)

    monkeypatch.setattr(r, '_reference_stream_response', observe)
    test_normal_planner_batches_seventeen_literal_sensors_without_scope_loss(monkeypatch)
    assert seen == [8, 8]


def test_variable_physical_context_and_quantity_remain_native_decisions():
    prepared, target, _, _ = batch_case(3)
    prepared['facts'][target['fact_id']]['role'] = 'OTHER'
    full = r._reference_schema_for_stage(prepared, {'devices'}, inventory_target=target)
    schema, codec = r._reference_compact_inventory_schema(full)
    for name in target['names']:
        record = codec[name]['NEW_PHYSICAL_CONTEXT']
        assert not {'quantity', 'context_kind', 'contained_device_ids'} & record['constants'].keys()
        variant = next(row for row in schema['properties']['inventory_choices']['properties'][name]['anyOf']
                       if row['properties']['choice_kind']['enum'] == ['NEW_PHYSICAL_CONTEXT'])
        assert variant['properties']['context_kind']['enum'] == ['PASSIVE', 'ASSEMBLY', 'SOFTWARE_SERVICE']
        assert 'quantity' in variant['properties']


def test_existing_binding_keeps_its_identity_and_full_binding_wire():
    prepared, target, _, value = batch_case(3)
    name = target['names'][0]
    existing = deepcopy(value['inventory_choices'][name]); existing.pop('choice_kind')
    existing['source_fact_ids'] = ['previous-source']
    full = r._reference_schema_for_stage(prepared, {'devices'}, inventory_target=target, existing_devices=[existing])
    schema, codec = r._reference_compact_inventory_schema(full)
    original = next(row for row in full['properties']['inventory_choices']['properties'][name]['anyOf']
                    if row['properties']['choice_kind']['enum'] == ['EXISTING'])
    compact = next(row for row in schema['properties']['inventory_choices']['properties'][name]['anyOf']
                   if row['properties']['choice_kind']['enum'] == ['EXISTING'])
    assert compact == original
    assert codec[name]['EXISTING']['constants'] == {}
    choices = {key: {field: deepcopy(v) for field, v in row.items()
                    if field not in codec[key]['NEW_SENSOR']['constants']}
               for key, row in value['inventory_choices'].items()}
    choices[name] = dict(choice_kind='EXISTING', device_id=existing['id'],
                        source_fact_ids=[target['fact_id']], rationale='New source binding', field_references={})
    result = r._reference_expand_inventory_choices([existing], choices, inventory_target=target, inventory_codec=codec)
    bound = next(row for row in result if row['id'] == existing['id'])
    assert bound['name'] == existing['name']
    assert bound['source_fact_ids'] == [target['fact_id']]
    assert existing['source_fact_ids'] == ['previous-source']
    assert len({row['id'] for row in result}) == 3
