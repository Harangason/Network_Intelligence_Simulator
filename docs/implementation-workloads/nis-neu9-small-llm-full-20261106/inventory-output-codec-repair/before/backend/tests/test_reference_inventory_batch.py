"""Bounded native inventory wire, never generated original-model evidence."""
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, ValidationError

from backend.nis.agent.orchestration import local_reasoner as r
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_design import fixture_request, fixture_design


def batch_case(count=3):
    prepared = intake.prepare_reference_design(fixture_request())
    sensor = next(row for row in intake.ReferenceDesignProposal.model_validate(
        fixture_design(prepared)).model_dump(mode='json')['devices'] if row['kind'] == 'SENSOR')
    fact = sensor['source_fact_ids'][0]
    prepared['facts'][fact].update(kind='INSTANCE', quantity=count)
    names = [f'Independent probe {i}' for i in range(count)]
    target = dict(fact_id=fact, member=None, names=names, minimum_rows=count, max_rows=count)
    schema = r._reference_schema_for_stage(prepared, {'devices'}, inventory_target=target)
    wire = schema['properties']['inventory_choices']
    choices = {}
    for index, name in enumerate(names):
        slot = wire.get('properties', {}).get(name, wire.get('items'))
        variants = slot.get('anyOf', [slot])
        variant = next(row for row in variants if row['properties']['choice_kind']['enum'] == ['NEW_SENSOR'])
        choices[name] = {**deepcopy(sensor), 'choice_kind': 'NEW_SENSOR', 'name': name,
                         'id': variant['properties']['id']['enum'][0]}
    value = {'devices': [], 'unresolved': [], 'inventory_complete': True, 'inventory_choices': choices}
    return prepared, target, schema, value


def test_named_batch_grammar_and_runtime_preserve_all_distinct_identities():
    prepared, target, schema, value = batch_case(8)
    Draft202012Validator(schema).validate(value)
    choices = value['inventory_choices']
    assert len({row['id'] for row in choices.values()}) == 8
    expanded = r._reference_expand_inventory_choices([], choices, inventory_target=target)
    delta = r._reference_scoped_inventory_delta([], expanded, inventory_target=target)
    merged = r._reference_merge_inventory_devices([], delta, target, prepared['facts'])
    assert [row['name'] for row in merged] == target['names']
    assert all(row['quantity'] == 1 and row['source_fact_ids'] == [target['fact_id']] for row in merged)
    assert r._reference_inventory_progress([], merged)


@pytest.mark.parametrize('fault', ['missing', 'foreign_slot', 'wrong_name', 'wrong_kind', 'foreign_source', 'duplicate_id'])
def test_batch_schema_rejects_missing_foreign_or_colliding_choices(fault):
    _, target, schema, value = batch_case()
    assert schema['properties']['inventory_choices']['type'] == 'object'
    choices = value['inventory_choices']; a, b, _ = target['names']
    if fault == 'missing': choices.pop(a)
    elif fault == 'foreign_slot': choices['foreign'] = choices.pop(a)
    elif fault == 'wrong_name': choices[a]['name'] = b
    elif fault == 'wrong_kind': choices[a]['kind'] = 'ACTUATOR'
    elif fault == 'foreign_source': choices[a]['source_fact_ids'] = ['foreign']
    elif fault == 'duplicate_id': choices[a]['id'] = choices[b]['id']
    with pytest.raises(ValidationError): Draft202012Validator(schema).validate(value)


def test_runtime_rejects_missing_or_misbound_batch_even_without_schema():
    _, target, _, value = batch_case()
    choices = value['inventory_choices']
    # Establish support first so these negatives cannot pass on an old list-only decoder.
    assert len(r._reference_expand_inventory_choices([], choices, inventory_target=target)) == 3
    for changed in ({}, {**choices, 'foreign': choices[target['names'][0]]}):
        with pytest.raises(ValueError):
            r._reference_expand_inventory_choices([], changed, inventory_target=target)
    changed = deepcopy(choices)
    changed[target['names'][0]]['name'] = target['names'][1]
    with pytest.raises(ValueError):
        r._reference_expand_inventory_choices([], changed, inventory_target=target)


def test_batch_target_cannot_bypass_shared_eight_identity_bound():
    with pytest.raises(ValueError): batch_case(9)


def test_normal_planner_batches_seventeen_literal_sensors_without_scope_loss(monkeypatch):
    import json
    from backend.tests.test_reference_reasoner import reasoner_with_transport, run_reference, complete_design
    request = fixture_request(sensor_group='17 Sensoren')
    source, raw = request['prompt'].split('\n- Dokument-Geräte: ', 1)
    envelope = json.loads(raw)
    fact = next(row for row in envelope['facts'] if row['role'] == 'SENSOR')
    fact.update(kind='INSTANCE', quantity=17)
    envelope['devices'].append({**fact, 'minimum': False})
    request['prompt'] = source + '\n- Dokument-Geräte: ' + json.dumps(envelope, ensure_ascii=False)

    def authored_design(prepared):
        design = complete_design(prepared)
        first = next(row for row in design['devices'] if row['kind'] == 'SENSOR')
        names = [row['name'] for row in prepared['catalog']['source_devices']
                 if row['evidence']['source_quote'] == '17 Sensoren']
        assert len(names) == 17
        first['name'] = names[0]
        port = next(row for row in design['ports'] if row['device_id'] == first['id'])
        measurement = next(row for row in design['measurements'] if row['device_id'] == first['id'])
        communication = next(row for row in design['communication'] if row['producer_device_id'] == first['id'])
        for index, name in enumerate(names[1:], 1):
            identity, port_id = f'authored-sensor-{index}', f'authored-port-{index}'
            design['devices'].append({**deepcopy(first), 'id': identity, 'name': name})
            design['ports'].append({**deepcopy(port), 'id': port_id, 'device_id': identity})
            design['measurements'].append({**deepcopy(measurement), 'device_id': identity})
            design['communication'].append({**deepcopy(communication), 'id': f'authored-signal-{index}',
                'signal_name': f'authored-signal-{index}', 'producer_device_id': identity, 'source_port_id': port_id})
        return design

    engine, prepared, observed = reasoner_with_transport(monkeypatch, request=request, design_factory=authored_design)
    from backend.nis.engineering.goal_execution.progress import sink
    events = []
    token = sink.set(events.append)
    try:
        result = run_reference(engine, prepared)
    finally:
        sink.reset(token)
    targets = [row['inventory_target_for_this_stage'] for row in observed
               if row.get('inventory_target_for_this_stage') and
               prepared['facts'][row['inventory_target_for_this_stage']['fact_id']]['role'] == 'SENSOR']
    assert [len(target['names']) for target in targets] == [8, 8, 1]
    assert len({row['id'] for row in result['proposal']['devices']}) == 19
    assert len(result['proposal']['measurements']) == 17
    assert result['source_evidence'] == prepared['source_evidence']
    assert result['proposal']['unresolved'] == []
    outputs = [event for event in events if event.get('metadata', {}).get('source') == 'document_reference_output'
               and (event['metadata'].get('inventory_target') or {}).get('fact_id') == targets[0]['fact_id']]
    assert outputs
    assert {event['metadata']['selected_inventory_bound_count'] for event in outputs} == {0, 8, 16}
    for event in outputs:
        meta = event['metadata']
        assert meta['selected_inventory_required_count'] == 17
        assert meta['selected_inventory_batch_size'] == len(meta['inventory_target']['names'])
        assert f"{meta['selected_inventory_bound_count']} von 17" in event['text']
        assert 'kein freigegebenes Modell' in event['text']


@pytest.mark.parametrize('label,role', [('Sensortypen', 'SENSOR'), ('Sensor types', 'SENSOR'),
                                       ('Aktortypen', 'ACTUATOR'), ('Actuator types', 'ACTUATOR')])
def test_explicit_type_list_role_matches_member_contract(label, role):
    text = label + ' (Links, Rechts)'
    assert intake.document_component_policy(text) == {'kind': 'CATEGORY', 'role': role, 'quantity': None}
    assert intake.reference_inventory_members({'kind': 'CATEGORY', 'role': role, 'source_quote': text}) == ['Links', 'Rechts']


@pytest.mark.parametrize('text,kind', [('Sensortypen müssen geprüft werden.', 'REQUIREMENT'),
                                     ('Das System verarbeitet Sensortypen (Links, Rechts).', 'FUNCTION'),
                                     ('Unbekannte Typen (Links, Rechts)', None)])
def test_mentions_and_requirements_are_not_promoted_to_type_list_hardware(text, kind):
    policy = intake.document_component_policy(text)
    assert (policy['kind'] if policy else None) == kind
    if policy: assert policy['role'] == 'OTHER'
