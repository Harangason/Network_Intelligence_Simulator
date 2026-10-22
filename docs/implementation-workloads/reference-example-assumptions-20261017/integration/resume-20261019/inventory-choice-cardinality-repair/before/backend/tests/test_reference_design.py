"""Reference candidates are unit fixtures, never product/model acceptance."""
from copy import deepcopy
import hashlib
import json

import pytest

from backend.nis.agent.orchestration import project_intake as intake


def fixture_request(*, references=None, answers=None, assignments=None, sensor_group='Sensorik (Temperatursensoren)', controller_count=1, controller_category=False):
    controller_name = 'Steuergeräte' if controller_category else 'Controller (ECU)'
    controller_quote = 'Steuergeräte (ECU)' if controller_category else ('Controller (ECU)' if controller_count == 1 else f'{controller_count} Controller (ECU)')
    source = (controller_quote + '\n' + sensor_group + '\nAktorik (Ventile)\n'
              'Funktion: Regelung\nFunktion: Diagnose\nFunktion: Gesamtfunktion\n'
              'REQ-001: Das System MUSS diagnostizierbar sein.')
    rows = [
        (controller_name, 'CATEGORY' if controller_category else 'INSTANCE', 'CONTROLLER', None if controller_category else controller_count, controller_quote),
        (sensor_group, 'CATEGORY', 'SENSOR', None, sensor_group),
        ('Aktorik (Ventile)', 'CATEGORY', 'ACTUATOR', None, 'Aktorik (Ventile)'),
        *[(name, 'FUNCTION', 'OTHER', None, 'Funktion: ' + name) for name in ('Regelung', 'Diagnose', 'Gesamtfunktion')],
        ('REQ-001', 'REQUIREMENT', 'OTHER', None, 'REQ-001: Das System MUSS diagnostizierbar sein.'),
    ]
    facts = [{'name': name, 'kind': kind, 'role': role, 'quantity': count,
              'source_quote': quote, 'source_context': []} for name, kind, role, count, quote in rows]
    envelope = {'source_text': source, 'source_name': 'complete-example.txt',
                'source_sha256': hashlib.sha256(source.encode()).hexdigest(), 'source_chars': len(source),
                'devices': [] if controller_category else [{'name': facts[0]['name'], 'role': 'CONTROLLER', 'quantity': controller_count,
                             'source_quote': facts[0]['source_quote'], 'source_context': [], 'minimum': False}],
                'questions': [{key: value for key, value in answer.items() if key in
                    {'id', 'label', 'role', 'source_quote', 'source_context'}} for answer in answers or []],
                'facts': facts, 'technologies': [{'name': 'ECU', 'kind': 'DEVICE_ALIAS', 'source_quote': 'ECU' if controller_category else 'Controller (ECU)'}],
                'answers': answers or [], 'function_assignments': assignments or {}}
    return {'mode': 'EXAMPLE_PROJECT', 'prompt': source + '\n- Dokument-Geräte: ' + json.dumps(envelope, ensure_ascii=False),
            'reference_sources': references or []}


def wire():
    return {'length_bits': 1, 'data_type': 'unsigned', 'unit': 'code', 'factor': 1,
            'min_value': 0, 'max_value': 1,
            'semantic': {'semantic_type': 'BOOLEAN', 'meaning': 'Ventil öffnen/schließen'},
            'data': {'enum_values': {'CLOSE': 0, 'OPEN': 1}}}


def fixture_design(prepared):
    ids = {fact['name']: fact_id for fact_id, fact in prepared['facts'].items()}
    sensor_group = next(fact['name'] for fact in prepared['facts'].values() if fact['role'] == 'SENSOR')
    controller_source = next(fact['name'] for fact in prepared['facts'].values() if fact['role'] == 'CONTROLLER')
    devices = [{'id': key, 'name': name, 'kind': kind, 'quantity': count,
                'source_fact_ids': [ids[fact]], 'rationale': 'Prüfbarer Referenzentwurf'}
               for key, name, kind, count, fact in [
                   ('C', 'Controller (ECU)', 'CONTROLLER', 1, controller_source),
                   ('S', 'Temperatursensor', 'SENSOR', 1, sensor_group),
                   ('A', 'Ventil', 'ACTUATOR', 1, 'Aktorik (Ventile)')]]
    for device in devices:
        source_fact = prepared['facts'][device['source_fact_ids'][0]]
        if source_fact['kind'] == 'INSTANCE':
            previous = [row for row in prepared.get('catalog', {}).get('source_devices', [])
                        if row.get('evidence', {}).get('source_quote') == source_fact['source_quote']
                        and row.get('evidence', {}).get('source_context', []) == source_fact.get('source_context', [])]
            if previous:
                device['name'] = previous[0]['name']
    return {'devices': devices,
            'functions': [{'source_fact_id': ids[name], 'realization': 'ATOMIC', 'executor_device_ids': ['C'],
                           'rationale': 'Ausführung im Referenzcontroller'} for name in ('Regelung', 'Diagnose', 'Gesamtfunktion')],
            'measurements': [{'device_id': 'S', 'measurement_id': 'temperature', 'rationale': 'Temperaturmessung'}],
            'commands': [{'device_id': 'A', 'definition': wire(), 'rationale': 'Schaltendes Referenzventil'}]}


@pytest.fixture
def prepared():
    return intake.prepare_reference_design(fixture_request())


def test_complete_original_and_short_ids_survive_detached_review(prepared):
    result = intake.validate_reference_design(fixture_design(prepared), prepared)
    assert result['status'] == 'REVIEW_REQUIRED'
    assert result['canonical_writes'] is False and result['approval_required'] is True
    assert result['source_evidence'] == prepared['source_evidence']
    assert result['source_evidence']['source_text'] in result['request']['prompt']
    assert 'source_text' not in intake.reviewed_document_evidence(prepared['request']['prompt'])
    assert result['request'] == prepared['request']
    assert len(result['coverage']['requirement_fact_ids']) == 1
    assert len(result['coverage']['function_fact_ids']) == 3
    assert all(len(key) == 13 and key.startswith('F') for key in result['fact_id_map'])
    assert all(identity == intake.document_fact_identity(prepared['facts'][key])
               for key, identity in result['fact_id_map'].items())
    assert all(item['kind'] == 'REFERENCE_ASSUMPTION' for item in result['decision_evidence'])
    result['source_evidence']['components'][0]['name'] = 'edited copy'
    assert prepared['source_evidence']['components'][0]['name'] != 'edited copy'


@pytest.mark.parametrize('corruption', ['source_hash', 'source_chars', 'fact_quote', 'fact_kind'])
def test_primary_source_evidence_cannot_be_replaced(corruption):
    request = fixture_request()
    original, raw = request['prompt'].split('\n- Dokument-Geräte: ')
    envelope = json.loads(raw)
    if corruption == 'source_hash': envelope['source_sha256'] = '0' * 64
    elif corruption == 'source_chars': envelope['source_chars'] -= 1
    elif corruption == 'fact_quote': envelope['facts'][0]['source_quote'] = 'Invented controller'
    else: envelope['facts'][1].update(kind='INSTANCE', quantity=1)
    request['prompt'] = original + '\n- Dokument-Geräte: ' + json.dumps(envelope)
    with pytest.raises(ValueError): intake.prepare_reference_design(request)


def reference(fields=('commands',)):
    text = 'Kommunikationsbeispiel mit 100 ECUs, keine Primärstückliste.'
    return {'id': 'R1', 'name': 'reference.txt', 'role': 'REFERENCE_SUPPLEMENT', 'text': text,
            'source_sha256': hashlib.sha256(text.encode()).hexdigest(), 'allowed_fields': list(fields)}


def test_inventory_checkpoint_reuses_full_source_guards_without_granting_review(prepared):
    value = fixture_design(prepared)
    devices = {'devices': value['devices']}
    assert intake._validate_reference_inventory(devices, prepared, []) == []
    complete = intake.validate_reference_design(devices, prepared)
    assert complete['proposal']['unresolved']  # IO/functions still missing.
    assert complete['approval_required'] and not complete['canonical_writes']
    missing = {'devices': value['devices'][:1]}
    findings = intake._validate_reference_inventory(missing, prepared, [])
    assert {row['target_ref'] for row in findings if row['code'] == 'REFERENCE_INVENTORY_UNCOVERED'} == {
        key for key, fact in prepared['facts'].items() if fact['role'] in {'SENSOR', 'ACTUATOR'}}
    for check in (lambda value: intake._validate_reference_inventory(value, prepared, []),
                  lambda value: intake.validate_reference_design(value, prepared)):
        corrupt = deepcopy(devices)
        corrupt['devices'][0]['name'] = 'Unrelated controller replacing the source instance'
        with pytest.raises(ValueError, match='Instanzidentität'):
            check(corrupt)


def test_sensor_type_list_needs_separate_literal_member_bindings():
    request = fixture_request()
    original, encoded = request['prompt'].split('\n- Dokument-Geräte: ')
    envelope = json.loads(encoded)
    before, after = 'Sensorik (Temperatursensoren)', 'Sensorik (Temperatursensoren, Drucksensoren)'
    envelope['source_text'] = original.replace(before, after)
    envelope['source_chars'] = len(envelope['source_text'])
    envelope['source_sha256'] = hashlib.sha256(envelope['source_text'].encode()).hexdigest()
    for fact in envelope['facts']:
        for key in ('name', 'source_quote'):
            fact[key] = fact[key].replace(before, after)
    request['prompt'] = envelope['source_text'] + '\n- Dokument-Geräte: ' + json.dumps(envelope, ensure_ascii=False)
    prepared = intake.prepare_reference_design(request)
    previous = intake.prepare_reference_design(fixture_request())
    value = fixture_design(previous)
    replacements = {old_id: next(key for key, fact in prepared['facts'].items()
                    if fact['name'] == old_fact['name'].replace(before, after)) for old_id, old_fact in previous['facts'].items()}
    for row in value['devices']:
        row['source_fact_ids'] = [replacements[key] for key in row['source_fact_ids']]
    sensor_id = value['devices'][1]['source_fact_ids'][0]
    fact = prepared['facts'][sensor_id]
    assert intake.reference_inventory_members(fact) == ['Temperatursensoren', 'Drucksensoren']
    value = {'devices': value['devices']}
    assert sum(row['code'] == 'REFERENCE_INVENTORY_MEMBER_UNCOVERED'
               for row in intake._validate_reference_inventory(value, prepared, [])) == 2
    value['devices'][1]['source_member_bindings'] = {sensor_id: 'Temperatursensoren'}
    pressure = {**deepcopy(value['devices'][1]), 'id': 'S2', 'name': 'Drucksensor',
                'source_member_bindings': {sensor_id: 'Drucksensoren'}}
    value['devices'].append(pressure)
    assert intake._validate_reference_inventory(value, prepared, []) == []
    full = intake.validate_reference_design(value, prepared)
    assert not any(row['code'] == 'REFERENCE_INVENTORY_MEMBER_UNCOVERED' for row in full['proposal']['unresolved'])
    assert full['source_evidence']['components'] == prepared['source_evidence']['components']
    value['devices'][-1]['source_member_bindings'] = {sensor_id: 'Erfundener Typ'}
    with pytest.raises(ValueError, match='wörtliches Mitglied'):
        intake._validate_reference_inventory(value, prepared, [])


@pytest.mark.parametrize('quote', ['Sensorik (Radar oder Kamera)', 'Aktorik (z. B. Pumpen, Ventile)',
                                  'Sensor types (camera/lidar, IMU)', 'Function: camera processing'])
def test_alternatives_and_examples_do_not_create_mandatory_inventory_members(quote):
    assert intake.reference_inventory_members({'kind': 'CATEGORY', 'role': 'SENSOR', 'source_quote': quote}) == []


def test_reference_inventory_is_not_promoted_and_field_scope_is_enforced():
    prepared = intake.prepare_reference_design(fixture_request(references=[reference()]))
    assert len(prepared['facts']) == 7
    candidate = fixture_design(prepared)
    candidate['commands'][0]['field_references'] = {'commands': ['R1']}
    result = intake.validate_reference_design(candidate, prepared)
    assert result['reference_sources']['R1']['role'] == 'REFERENCE_SUPPLEMENT'
    assert any(item['reference_sources'] for item in result['decision_evidence'])
    candidate['devices'][0]['field_references'] = {'quantity': ['R1']}
    with pytest.raises(ValueError, match='Entscheidungsfeld'): intake.validate_reference_design(candidate, prepared)


@pytest.mark.parametrize('mutation', ['hash', 'duplicate_id', 'bad_role', 'duplicate_scope'])
def test_reference_manifest_rejects_corruption(mutation):
    refs = [reference()]
    if mutation == 'hash': refs[0]['source_sha256'] = '0' * 64
    elif mutation == 'duplicate_id': refs.append(deepcopy(refs[0]))
    elif mutation == 'bad_role': refs[0]['role'] = 'ORIGINAL'
    else: refs[0]['allowed_fields'] = ['commands', 'commands']
    with pytest.raises(ValueError): intake.prepare_reference_design(fixture_request(references=refs))


def test_model_cannot_claim_approval_or_source_authority(prepared):
    for key in ('approved', 'canonical_writes', 'decision_evidence', 'source_evidence'):
        candidate = fixture_design(prepared)
        candidate[key] = True
        with pytest.raises(ValueError): intake.validate_reference_design(candidate, prepared)


def test_stale_request_and_untrusted_prepared_facts(prepared):
    candidate = fixture_design(prepared)
    stale = deepcopy(prepared)
    stale['request']['prompt'] += '\nnew revision'
    with pytest.raises(ValueError, match='Auftragsrevision'): intake.validate_reference_design(candidate, stale)
    forged = deepcopy(prepared)
    forged['facts'] = {}
    assert intake.validate_reference_design(candidate, forged)['source_evidence'] == prepared['source_evidence']


@pytest.mark.parametrize('mutation', ['unknown_fact', 'duplicate_device', 'name_collision', 'instance_quantity', 'known_role', 'float_quantity'])
def test_identity_quantity_and_known_role_guards(prepared, mutation):
    candidate = fixture_design(prepared)
    if mutation == 'unknown_fact': candidate['devices'][0]['source_fact_ids'] = ['unknown']
    elif mutation == 'duplicate_device': candidate['devices'].append(deepcopy(candidate['devices'][0]))
    elif mutation == 'name_collision': candidate['devices'][1]['name'] = candidate['devices'][0]['name']
    elif mutation == 'instance_quantity': candidate['devices'][0]['quantity'] = 2
    elif mutation == 'known_role': candidate['devices'][1]['kind'] = 'CONTROLLER'
    else: candidate['devices'][1]['quantity'] = 1.5
    with pytest.raises(ValueError): intake.validate_reference_design(candidate, prepared)


def test_composite_preserves_source_binding_without_own_executor(prepared):
    candidate = fixture_design(prepared)
    parent = candidate['functions'][-1]
    parent.update(realization='COMPOSITE', executor_device_ids=[],
                  realized_by_fact_ids=[row['source_fact_id'] for row in candidate['functions'][:-1]])
    result = intake.validate_reference_design(candidate, prepared)
    assert len(result['coverage']['function_fact_ids']) == 3
    assert result['proposal']['functions'][-1]['executor_device_ids'] == []
    parent['realized_by_fact_ids'].append(parent['source_fact_id'])
    with pytest.raises(ValueError, match='zyklisch'): intake.validate_reference_design(candidate, prepared)


def test_confirmed_atomic_owner_cannot_be_hidden_by_composite():
    original = fixture_request()
    raw = json.loads(original['prompt'].split('\n- Dokument-Geräte: ')[1])
    fact = next(f for f in raw['facts'] if f['name'] == 'Gesamtfunktion')
    prepared = intake.prepare_reference_design(fixture_request(assignments={intake.document_fact_identity(fact): 'Controller (ECU)'}))
    candidate = fixture_design(prepared)
    candidate['functions'][-1].update(realization='COMPOSITE', executor_device_ids=[],
                                    realized_by_fact_ids=[candidate['functions'][0]['source_fact_id']])
    with pytest.raises(ValueError, match='bestätigte'): intake.validate_reference_design(candidate, prepared)


def test_missing_source_items_are_explicit_findings_not_deleted(prepared):
    candidate = fixture_design(prepared)
    candidate['functions'].pop()
    candidate['devices'].pop()
    candidate['commands'] = []
    result = intake.validate_reference_design(candidate, prepared)
    assert {f['code'] for f in result['proposal']['unresolved']} >= {'REFERENCE_FUNCTION_UNCOVERED', 'REFERENCE_INVENTORY_UNCOVERED'}
    assert result['source_evidence'] == prepared['source_evidence']


@pytest.mark.parametrize('mutation', ['unknown_measurement', 'bits', 'raw_overlap', 'semantic_unit', 'nan'])
def test_existing_measurement_and_wire_invariants(prepared, mutation):
    candidate = fixture_design(prepared)
    definition = candidate['commands'][0]['definition']
    if mutation == 'unknown_measurement': candidate['measurements'][0]['measurement_id'] = 'not-a-registry-id'
    elif mutation == 'bits': definition['data']['enum_values']['OPEN'] = 4
    elif mutation == 'raw_overlap': definition['data']['invalid_values'] = [1]
    elif mutation == 'semantic_unit': definition['unit'] = 'Nm'
    else: definition['data']['invalid_values'] = [float('nan')]
    with pytest.raises(ValueError): intake.validate_reference_design(candidate, prepared)


def test_physical_context_cannot_serve_as_controller(prepared):
    candidate = fixture_design(prepared)
    # A source FUNCTION can motivate a new execution node, never prove hardware.
    candidate['devices'].append({'id': 'P', 'name': 'Softwarekontext', 'kind': 'PHYSICAL_CONTEXT',
        'context_kind': 'SOFTWARE_SERVICE', 'quantity': 1,
        'source_fact_ids': [candidate['functions'][0]['source_fact_id']], 'rationale': 'Quellenbindung ohne erfundene ECU'})
    intake.validate_reference_design(candidate, prepared)
    candidate['functions'][0]['executor_device_ids'] = ['P']
    with pytest.raises(ValueError, match='Controller'): intake.validate_reference_design(candidate, prepared)


def test_reviewed_counts_remain_exact_or_minimum():
    answer = {'id': 'SENSOR:Sensorik (Temperatursensoren):Sensorik (Temperatursensoren)', 'label': 'Sensorik (Temperatursensoren)', 'source_context': [],
              'source_quote': 'Sensorik (Temperatursensoren)', 'role': 'SENSOR', 'quantity': 3, 'minimum': True}
    prepared = intake.prepare_reference_design(fixture_request(answers=[answer]))
    candidate = fixture_design(prepared)
    with pytest.raises(ValueError, match='Gerätemenge'): intake.validate_reference_design(candidate, prepared)
    for index in range(2, 5):
        sensor = deepcopy(candidate['devices'][1])
        sensor.update(id=f'S{index}', name=f'Temperatursensor{index}')
        candidate['devices'].append(sensor)
    intake.validate_reference_design(candidate, prepared)
    answer['minimum'] = False
    prepared = intake.prepare_reference_design(fixture_request(answers=[answer]))
    with pytest.raises(ValueError, match='Gerätemenge'): intake.validate_reference_design(candidate, prepared)


def test_partial_inventory_preserves_explicit_instance_names_and_final_exact_count():
    prepared = intake.prepare_reference_design(fixture_request(controller_count=3))
    candidate = {'devices': fixture_design(prepared)['devices'][:1]}
    pending = intake._validate_reference_inventory(candidate, prepared, [], partial=True)
    assert any(row['code'] == 'REFERENCE_INVENTORY_QUANTITY_PENDING' for row in pending)
    assert isinstance(pending, list)  # Internal findings confer no review/approval.
    with pytest.raises(ValueError, match='Instanzmenge'):
        intake._validate_reference_inventory(candidate, prepared, [])
    with pytest.raises(ValueError, match='Instanzmenge'):
        intake.validate_reference_design(candidate, prepared)
    candidate['devices'][0]['name'] = 'Unrelated replacement'
    with pytest.raises(ValueError, match='Instanzidentität'):
        intake._validate_reference_inventory(candidate, prepared, [], partial=True)
    with pytest.raises(ValueError, match='keinen Referenz-Review'):
        intake._validate_reference_design(candidate, prepared, partial_inventory=True)


def test_partial_inventory_never_relaxes_confirmed_count_upper_bound():
    label = 'Sensorik (Temperatursensoren)'
    answer = {'id': f'SENSOR:{label}:{label}', 'label': label, 'source_context': [],
              'source_quote': label, 'role': 'SENSOR', 'quantity': 2, 'minimum': False}
    prepared = intake.prepare_reference_design(fixture_request(answers=[answer]))
    candidate = fixture_design(prepared)
    assert any(row['code'] == 'REFERENCE_INVENTORY_QUANTITY_PENDING'
               for row in intake._validate_reference_inventory(candidate, prepared, [], partial=True))
    for index in (2, 3):
        candidate['devices'].append({**deepcopy(candidate['devices'][1]), 'id': f'S{index}', 'name': f'Sensor {index}'})
    for partial in (True, False):
        with pytest.raises(ValueError, match='Gerätemenge'):
            intake._validate_reference_inventory(candidate, prepared, [], partial=partial)


@pytest.mark.parametrize('source_kind', ['FUNCTION', 'REQUIREMENT'])
def test_additional_hardware_is_a_reference_derivation_not_a_source_fact(prepared, source_kind):
    candidate = fixture_design(prepared)
    fact_id = next(key for key, fact in prepared['facts'].items() if fact['kind'] == source_kind)
    candidate['devices'].append({'id': 'DERIVED', 'name': 'Referenzdrucksensor', 'kind': 'SENSOR',
        'quantity': 1, 'owner_device_id': 'C', 'source_fact_ids': [fact_id],
        'rationale': 'Zusätzlicher Sensor als ausdrücklich zu prüfende Referenzauslegung'})
    result = intake.validate_reference_design(candidate, prepared)
    assert result['source_evidence'] == prepared['source_evidence']
    evidence = [row for row in result['decision_evidence'] if row['target_ref'] == 'DERIVED']
    assert evidence and all(row['kind'] == 'REFERENCE_ASSUMPTION' for row in evidence)
    assert all(row['source_fact_kinds'][fact_id] == source_kind for row in evidence)
    assert fact_id not in result['coverage']['inventory_bindings']
    assert 'DERIVED' in result['coverage']['derived_device_bindings'][fact_id]
    assert len(result['coverage']['function_fact_ids']) == 3


def test_controller_fact_cannot_be_relabelled_as_derived_sensor(prepared):
    candidate = fixture_design(prepared)
    candidate['devices'].append({'id': 'DERIVED', 'name': 'Referenzdrucksensor', 'kind': 'SENSOR',
        'quantity': 1, 'source_fact_ids': candidate['devices'][0]['source_fact_ids'],
        'rationale': 'Unzulässige Umdeutung einer Controllerdeklaration'})
    with pytest.raises(ValueError, match='Geräteart'): intake.validate_reference_design(candidate, prepared)


def with_communication(candidate):
    candidate['devices'][1]['owner_device_id'] = 'C'
    candidate['ports'] = [{'id': node + 'port', 'device_id': node, 'technology': 'i2c',
        'role': 'LOCAL', 'network_scope': 'reference_local_i2c', 'parameters': {},
        'rationale': 'Getrennt zu prüfender physischer Anschluss'} for node in ('S', 'C')]
    candidate['communication'] = [{'id': 'TEMP', 'producer_device_id': 'S', 'consumer_device_ids': ['C'],
        'source_port_id': 'Sport', 'consumer_port_ids': ['Cport'], 'scope': 'LOCAL_IO',
        'signal_name': 'Temperatur', 'encoding': {'length_bits': 16, 'data_type': 'signed', 'unit': 'degC',
            'factor': 0.1, 'offset_value': 0, 'min_value': -40, 'max_value': 125,
            'semantic': {'semantic_type': 'NUMERIC', 'meaning': 'Temperatur'},
            'data': {'minimum': -40, 'maximum': 125, 'resolution': 0.1}},
        'transmission_mode': 'CYCLIC', 'cycle_ms': 100, 'rationale': 'Expliziter Referenzmesszyklus'}]
    return candidate


def test_port_and_event_design_is_reviewed_without_qualifying_physical_parameters(prepared):
    candidate = with_communication(fixture_design(prepared))
    result = intake.validate_reference_design(candidate, prepared)
    assert len(result['proposal']['ports']) == 2
    assert 'validation_scope' not in result
    assert result['status'] == 'REVIEW_REQUIRED'
    assert any(item['code'].startswith('REFERENCE_PORT_') for item in result['proposal']['unresolved'])
    candidate['communication'][0].update(transmission_mode='EVENT', cycle_ms=None, trigger='on_change', trigger_description='Temperaturänderung', min_interval_ms=10)
    intake.validate_reference_design(candidate, prepared)


@pytest.mark.parametrize('mutation', ['sender_port', 'receiver_port', 'unknown_protocol', 'cycle', 'event_rate', 'event_trigger', 'physical_traffic', 'function_host', 'local_owner'])
def test_transport_and_function_bindings_cannot_be_faked(prepared, mutation):
    candidate = with_communication(fixture_design(prepared))
    communication = candidate['communication'][0]
    if mutation == 'sender_port': communication['source_port_id'] = 'Cport'
    elif mutation == 'receiver_port': communication['consumer_port_ids'] = ['Sport']
    elif mutation == 'unknown_protocol': candidate['ports'][0]['technology'] = 'unknown-tech'
    elif mutation == 'cycle': communication['cycle_ms'] = None
    elif mutation == 'event_rate': communication.update(transmission_mode='EVENT', trigger='on_change', min_interval_ms=None)
    elif mutation == 'event_trigger': communication.update(transmission_mode='EVENT', min_interval_ms=10, trigger=None)
    elif mutation == 'physical_traffic': candidate['devices'][1].update(kind='PHYSICAL_CONTEXT', context_kind='PASSIVE')
    elif mutation == 'function_host': communication['producer_fact_id'] = candidate['functions'][0]['source_fact_id']
    else: candidate['devices'][1]['owner_device_id'] = None
    with pytest.raises(ValueError): intake.validate_reference_design(candidate, prepared)


@pytest.mark.parametrize('case', ['unsigned_negative', 'too_narrow', 'float_width', 'nonaligned_range'])
def test_numeric_encoding_retains_sign_scale_and_width(prepared, case):
    candidate = with_communication(fixture_design(prepared))
    encoding = candidate['communication'][0]['encoding']
    if case == 'unsigned_negative': encoding['data_type'] = 'unsigned'
    elif case == 'too_narrow': encoding['length_bits'] = 8
    elif case == 'float_width': encoding.update(data_type='float32', length_bits=16)
    else: encoding['factor'] = 0.3
    with pytest.raises(ValueError): intake.validate_reference_design(candidate, prepared)


def test_candidate_cannot_move_between_projects(prepared):
    from backend.nis.engineering.projects.project_context import activate_project, reset_project
    token = activate_project('different-example-project')
    try:
        with pytest.raises(ValueError, match='Auftragsrevision'):
            intake.validate_reference_design(fixture_design(prepared), prepared)
    finally:
        reset_project(token)


def test_live_catalog_revision_and_known_source_host_are_protected(monkeypatch):
    from backend.nis.agent.tools import wizard_generation
    original_catalog = wizard_generation.reference_design_catalog
    request = fixture_request()
    prepared = intake.prepare_reference_design(request)
    def changed_catalog(prompt):
        return {**original_catalog(prompt), 'catalog_revision': 'changed'}
    monkeypatch.setattr(wizard_generation, 'reference_design_catalog', changed_catalog)
    with pytest.raises(ValueError, match='Auftragsrevision'):
        intake.validate_reference_design(fixture_design(prepared), prepared)
    legacy = next(identity for key, identity in prepared['fact_id_map'].items()
                  if prepared['facts'][key]['name'] == 'Regelung')
    def known_host_catalog(prompt):
        return {**original_catalog(prompt), 'source_function_assignments': {legacy: 'Controller (ECU)'}}
    monkeypatch.setattr(wizard_generation, 'reference_design_catalog', known_host_catalog)
    prepared = intake.prepare_reference_design(request)
    candidate = fixture_design(prepared)
    candidate['devices'].append({'id': 'C2', 'name': 'Referenzcontroller', 'kind': 'CONTROLLER', 'quantity': 1,
        'source_fact_ids': [candidate['functions'][0]['source_fact_id']], 'rationale': 'Zusätzlicher Entwurfsknoten'})
    candidate['functions'][0]['executor_device_ids'] = ['C2']
    with pytest.raises(ValueError, match='Funktionsausführer'):
        intake.validate_reference_design(candidate, prepared)


def profiled_fixture():
    request = fixture_request()
    original = json.loads(request['prompt'].split('\n- Dokument-Geräte: ')[1])
    labels = ['054. Roboterbeispiel', '055. Zellenbeispiel']
    source = '\n'.join('# ' + label + '\n' + original['source_text'] for label in labels)
    envelope = {**original, 'source_text': source, 'source_chars': len(source),
                'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                'devices': [{**device, 'source_context': [label]} for label in labels for device in original['devices']],
                'facts': [{**fact, 'source_context': [label]} for label in labels for fact in original['facts']]}
    prepared = intake.prepare_reference_design({'mode': 'EXAMPLE_PROJECT',
        'prompt': source + '\n- Dokument-Geräte: ' + json.dumps(envelope, ensure_ascii=False)})
    candidate = {}
    for index, label in enumerate(labels):
        subset = {**prepared, 'facts': {key: fact for key, fact in prepared['facts'].items()
                                      if fact['source_context'] == [label]}}
        part = fixture_design(subset)
        prefix = str(index) + '_'
        for device in part['devices']:
            device['id'] = prefix + device['id']
            if device['kind'] != 'CONTROLLER': device['name'] = prefix + device['name']
        for function in part['functions']:
            function['executor_device_ids'] = [prefix + key for key in function['executor_device_ids']]
        for field in ('commands', 'measurements'):
            for item in part[field]: item['device_id'] = prefix + item['device_id']
        for field, items in part.items(): candidate.setdefault(field, []).extend(items)
    return prepared, candidate


@pytest.mark.parametrize('mutation', ['host', 'derived_device', 'owner', 'network_identity'])
def test_same_labels_do_not_merge_independent_source_profiles(mutation):
    prepared, candidate = profiled_fixture()
    result = intake.validate_reference_design(candidate, prepared)
    assert len(result['coverage']['function_fact_ids']) == 6
    if mutation == 'host': candidate['functions'][0]['executor_device_ids'] = ['1_C']
    elif mutation == 'derived_device': candidate['devices'][0]['source_fact_ids'].append(candidate['devices'][3]['source_fact_ids'][0])
    elif mutation == 'owner': candidate['devices'][1]['owner_device_id'] = '1_C'
    else:
        candidate['ports'] = [{'id': key + 'port', 'device_id': key, 'technology': 'i2c', 'role': 'LOCAL',
            'network_scope': 'accidentally_shared', 'rationale': 'Getrennte Quellenprofile'} for key in ('0_C', '1_C')]
    with pytest.raises(ValueError): intake.validate_reference_design(candidate, prepared)


@pytest.mark.parametrize('caption', [
    '6. Systemverhalten (High-Level)', '3. Kommunikationsarchitektur',
    '5. Systemanforderungen (Top-Level)', '4. Safety-Anforderungen (ISO 26262)',
    '5. Cybersecurity-Anforderungen (ISO 21434)', '7. Erweiterte Safety-Requirements (ISO 26262)',
    '8. Erweiterte Cybersecurity-Requirements (ISO 21434)', '9. Erweiterte ADAS-/Sensorfusion-Requirements',
    '6. Diagnose & OTA', '8. Zusammenfassung', '5. Schnittstellen und Daten',
    '8. Safety, Security, Qualität und Betrieb', 'Interfaces and Data',
    'Safety, Security, Quality and Operations', 'Extended Safety Requirements',
])
def test_generic_chapter_scope_is_not_an_independent_source_system(caption):
    assert intake.document_system_scope([caption, '6.1 Normalbetrieb']) == []
    named = ['D – Industrieautomation, Produktion und Robotik', '054. Kollaborativer Roboterarm']
    assert intake.document_system_scope([*named, caption, '6.1 Normalbetrieb']) == named
    assert intake.document_system_scope(['vehicle-example', caption]) == ['vehicle-example']


@pytest.mark.parametrize('name', ['054. Kollaborativer Roboterarm', '056. Mobiler Service-Roboter mit Greifarm',
                                 '062. Digitale Fabriklinie / Montagewerk', 'Safety PLC', 'Cybersecurity Gateway'])
def test_named_system_identity_is_never_removed_as_a_generic_chapter(name):
    assert intake.document_system_scope([name]) == [name]


@pytest.mark.parametrize('field,value', [('factor', True), ('unit', ' '),
    ('semantic', {'semantic_type': [], 'meaning': 'bad'}),
    ('semantic', {'semantic_type': 'BOOLEAN', 'meaning': {'bad': 'shape'}}),
    ('data', {'enum_values': []})])
def test_malformed_wire_fields_are_actionable_validation_errors(prepared, field, value):
    candidate = fixture_design(prepared)
    candidate['commands'][0]['definition'][field] = value
    with pytest.raises(ValueError): intake.validate_reference_design(candidate, prepared)


def with_local_dependency(candidate):
    candidate['functional_dependencies'] = [{'id': 'local_function_data',
        'producer_fact_id': candidate['functions'][0]['source_fact_id'],
        'consumer_fact_ids': [candidate['functions'][1]['source_fact_id']],
        'executor_device_id': 'C', 'signal_name': 'Funktionsergebnis', 'encoding': wire(),
        'rationale': 'Prüfbare lokale Datenabhängigkeit; Algorithmus und Timing sind unbestätigt'}]
    return candidate


def test_local_function_dependency_preserves_no_physical_self_transport(prepared):
    candidate = with_local_dependency(fixture_design(prepared))
    result = intake.validate_reference_design(candidate, prepared)
    assert result['proposal']['communication'] == []
    assert len(result['proposal']['functional_dependencies']) == 1
    assert result['processing_evidence'] == 'NONE' and result['timing_evidence'] == 'NONE'
    assert any(row['target_ref'] == 'local_function_data' and row['kind'] == 'REFERENCE_ASSUMPTION'
               for row in result['decision_evidence'])


@pytest.mark.parametrize('mutation', ['unknown', 'composite', 'different_host', 'self', 'duplicate', 'physical_port'])
def test_function_dependency_cannot_fake_function_or_host_binding(prepared, mutation):
    candidate = with_local_dependency(fixture_design(prepared))
    dependency = candidate['functional_dependencies'][0]
    if mutation == 'unknown': dependency['producer_fact_id'] = 'unknown'
    elif mutation == 'composite':
        candidate['functions'][0].update(realization='COMPOSITE', executor_device_ids=[],
            realized_by_fact_ids=[candidate['functions'][2]['source_fact_id']])
    elif mutation == 'different_host':
        candidate['devices'].append({'id': 'C2', 'name': 'Zweiter Referenzcontroller', 'kind': 'CONTROLLER',
            'quantity': 1, 'source_fact_ids': [candidate['functions'][1]['source_fact_id']], 'rationale': 'Zusätzlicher Controllerentwurf'})
        candidate['functions'][1]['executor_device_ids'] = ['C2']
    elif mutation == 'self': dependency['consumer_fact_ids'] = [dependency['producer_fact_id']]
    elif mutation == 'duplicate': dependency['consumer_fact_ids'] *= 2
    else: dependency['source_port_id'] = 'invented_loopback'
    with pytest.raises(ValueError): intake.validate_reference_design(candidate, prepared)


def confirmed_fixture(monkeypatch):
    from backend.nis.agent.tools import wizard_generation
    original = wizard_generation.reference_design_catalog
    controller_name = next((row['name'] for row in original(fixture_request()['prompt']).get('source_devices', [])
                            if row.get('evidence', {}).get('source_quote') == 'Controller (ECU)'), 'Controller (ECU)')
    command = {**wire(), 'length_bits': 8}
    choices = {'confirmed_commands': {'Ventil (A)': command},
        'confirmed_measurements': {'Temperatursensor': 'temperature'},
        'confirmed_connections': {'Temperatursensor': 'I2C'},
        'confirmed_owners': {'Temperatursensor': controller_name},
        'name_aliases': {'Ventil (A)': 'ventil', 'Ventil': 'ventil'}}
    def confirmed_catalog(prompt):
        catalog = original(prompt)
        return {**catalog, **deepcopy(choices), 'name_aliases': {**catalog.get('name_aliases', {}), **choices['name_aliases']}}
    monkeypatch.setattr(wizard_generation, 'reference_design_catalog', confirmed_catalog)
    prepared = intake.prepare_reference_design(fixture_request())
    candidate = fixture_design(prepared)
    candidate['commands'][0]['definition'] = deepcopy(command)
    candidate['devices'][1]['owner_device_id'] = 'C'
    return prepared, candidate, choices


def test_unchanged_confirmed_choices_are_inherited_instead_of_regenerated(monkeypatch):
    prepared, candidate, choices = confirmed_fixture(monkeypatch)
    candidate['commands'] = []
    candidate['measurements'] = []
    candidate['devices'][1]['owner_device_id'] = None
    result = intake.validate_reference_design(candidate, prepared)
    assert result['protected_fields']['commands'] == choices['confirmed_commands']
    assert result['protected_fields']['connections'] == choices['confirmed_connections']
    assert result['protected_fields']['owners'] == choices['confirmed_owners']
    assert result['source_evidence'] == prepared['source_evidence']


@pytest.mark.parametrize('mutation', ['rename', 'command_width', 'command_vocab', 'measurement', 'connection', 'owner'])
def test_reference_proposals_cannot_overwrite_previously_confirmed_fields(monkeypatch, mutation):
    prepared, candidate, choices = confirmed_fixture(monkeypatch)
    if mutation == 'rename': candidate['devices'][-1]['name'] = 'Umbenannt'
    elif mutation == 'command_width': candidate['commands'][0]['definition']['length_bits'] = 16
    elif mutation == 'command_vocab': candidate['commands'][0]['definition']['data']['enum_values']['INVENTED_ERROR'] = 255
    elif mutation == 'measurement': candidate['measurements'][0]['measurement_id'] = 'humidity'
    elif mutation == 'connection': candidate['ports'] = [{'id': 'different_port', 'device_id': 'S', 'technology': 'can',
        'role': 'LOCAL', 'network_scope': 'different_can', 'rationale': 'Unerlaubter Ersatz eines bestätigten Anschlusses'}]
    else:
        candidate['devices'].append({'id': 'C2', 'name': 'Zweiter Referenzcontroller', 'kind': 'CONTROLLER', 'quantity': 1,
            'source_fact_ids': [candidate['functions'][0]['source_fact_id']], 'rationale': 'Zusätzlicher Controllerentwurf'})
        candidate['devices'][1]['owner_device_id'] = 'C2'
    with pytest.raises(ValueError): intake.validate_reference_design(candidate, prepared)


def test_additional_ports_keep_all_confirmed_ports(monkeypatch):
    prepared, candidate, _ = confirmed_fixture(monkeypatch)
    candidate['ports'] = [{'id': key, 'device_id': 'S', 'technology': technology, 'role': 'LOCAL',
        'network_scope': 'separate_' + technology, 'rationale': 'Zusätzlicher prüfpflichtiger Anschluss'}
        for key, technology in [('existing_i2c', 'i2c'), ('additional_can', 'can')]]
    result = intake.validate_reference_design(candidate, prepared)
    assert len(result['proposal']['ports']) == 2


@pytest.mark.parametrize('mode', ['EVENT', 'MIXED', 'ON_REQUEST'])
def test_native_release_contracts_do_not_invent_periodic_requests(prepared, mode):
    from backend.nis.engineering.capacity.transmission import release_grid
    candidate = with_communication(fixture_design(prepared))
    row = candidate['communication'][0]
    row.update(transmission_mode=mode, min_interval_ms=10, cycle_ms=100 if mode == 'MIXED' else None)
    if mode == 'ON_REQUEST': row.update(request_source='external_application', request_times_ms=[20., 50.])
    else: row.update(trigger='explicit', release_times_ms=[20., 50.])
    result = intake.validate_reference_design(candidate, prepared)
    saved = result['proposal']['communication'][0]
    times = release_grid(intake.reference_transmission_contract(saved), saved['cycle_ms'], 100)
    assert times == ([0., 20., 50., 100.] if mode == 'MIXED' else [20., 50.])


@pytest.mark.parametrize('mutation', ['missing_request', 'independent_times', 'negative_time', 'too_close'])
def test_invalid_release_inputs_are_not_replaced_with_cycles(prepared, mutation):
    candidate = with_communication(fixture_design(prepared))
    row = candidate['communication'][0]
    row.update(transmission_mode='ON_REQUEST', cycle_ms=None, min_interval_ms=10,
               request_source='bus_message', request_communication_id='unknown', response_processing_ms=1)
    if mutation == 'independent_times': row['request_times_ms'] = [1.]
    elif mutation == 'negative_time': row.update(request_source='external_application', request_times_ms=[-1.])
    elif mutation == 'too_close': row.update(request_source='external_application', request_times_ms=[1., 2.])
    with pytest.raises(ValueError): intake.validate_reference_design(candidate, prepared)


def with_command(candidate, definition=None):
    candidate = with_communication(candidate)
    candidate['devices'][-1]['owner_device_id'] = 'C'
    candidate['ports'].append({'id': 'Aport', 'device_id': 'A', 'technology': 'i2c', 'role': 'LOCAL',
        'network_scope': 'reference_local_i2c', 'rationale': 'Bewusster Aktoranschluss'})
    candidate['communication'].append({'id': 'COMMAND', 'producer_device_id': 'C', 'consumer_device_ids': ['A'],
        'source_port_id': 'Cport', 'consumer_port_ids': ['Aport'], 'scope': 'LOCAL_IO', 'role': 'COMMAND',
        'signal_name': 'Ventilbefehl', 'encoding': deepcopy(definition or wire()),
        'transmission_mode': 'CYCLIC', 'cycle_ms': 100, 'rationale': 'Stellgröße am tatsächlichen Aktorempfänger'})
    return candidate


def test_command_encoding_is_bound_to_actuator_and_keeps_raw_vocabulary(prepared):
    candidate = with_command(fixture_design(prepared))
    candidate['communication'][-1]['encoding']['semantic']['meaning'] = 'Gleichbedeutender Ventilbefehl'
    assert len(intake.validate_reference_design(candidate, prepared)['proposal']['communication']) == 2
    candidate['communication'][-1]['encoding']['data']['enum_values'] = {'OPEN': 0, 'CLOSE': 1}
    with pytest.raises(ValueError, match='Stellgröße'): intake.validate_reference_design(candidate, prepared)


@pytest.mark.parametrize('mutation', ['width', 'unit', 'missing', 'semantic'])
def test_command_and_measurement_encodings_cannot_diverge_from_selected_quantity(prepared, mutation):
    candidate = with_command(fixture_design(prepared))
    if mutation == 'width': candidate['communication'][-1]['encoding']['length_bits'] = 8
    elif mutation == 'unit': candidate['communication'][0]['encoding']['unit'] = 'Nm'
    elif mutation == 'missing': candidate['commands'] = []
    else: candidate['communication'][0]['encoding'] = wire()
    with pytest.raises(ValueError): intake.validate_reference_design(candidate, prepared)


def test_status_is_separate_from_sensor_measurement(prepared):
    candidate = with_communication(fixture_design(prepared))
    status = deepcopy(candidate['communication'][0])
    status.update(id='STATUS', role='STATUS', signal_name='Sensorstatus', encoding=wire())
    candidate['communication'].append(status)
    assert len(intake.validate_reference_design(candidate, prepared)['proposal']['communication']) == 2


def test_inherited_command_encoding_is_still_checked(monkeypatch):
    prepared, candidate, choices = confirmed_fixture(monkeypatch)
    candidate = with_command(candidate, choices['confirmed_commands']['Ventil (A)'])
    candidate['commands'] = []
    intake.validate_reference_design(candidate, prepared)
    candidate['communication'][-1]['encoding']['length_bits'] = 16
    with pytest.raises(ValueError, match='Stellgröße'): intake.validate_reference_design(candidate, prepared)


def test_electronics_are_individually_addressed_and_unplanned_confirmed_ports_remain_findings(monkeypatch):
    prepared, candidate, _ = confirmed_fixture(monkeypatch)
    result = intake.validate_reference_design(candidate, prepared)
    assert any(row['code'] == 'REFERENCE_CONFIRMED_PORT_UNPLANNED' for row in result['proposal']['unresolved'])
    candidate['devices'][1]['quantity'] = 2
    with pytest.raises(ValueError, match='einzelne Identitäten'): intake.validate_reference_design(candidate, prepared)


def test_multiple_explicit_instances_keep_their_total_without_implicit_group_endpoints():
    request = fixture_request()
    source, serialized = request['prompt'].split('\n- Dokument-Geräte: ')
    envelope = json.loads(serialized)
    envelope['facts'][0]['quantity'] = 2
    source = source.replace('Controller (ECU)', '2 Controller (ECU)')
    envelope['facts'][0]['source_quote'] = '2 Controller (ECU)'
    envelope['devices'][0].update(quantity=2, source_quote='2 Controller (ECU)')
    envelope.update(source_text=source, source_chars=len(source), source_sha256=hashlib.sha256(source.encode()).hexdigest())
    request['prompt'] = source + '\n- Dokument-Geräte: ' + json.dumps(envelope)
    prepared = intake.prepare_reference_design(request)
    candidate = fixture_design(prepared)
    second = deepcopy(candidate['devices'][0]); second.update(id='C2',name='ControllerZwei')
    previous = [row['name'] for row in prepared.get('catalog', {}).get('source_devices', [])
                if row.get('evidence', {}).get('source_quote') == '2 Controller (ECU)']
    if len(previous) == 2: second['name'] = previous[1]
    candidate['devices'].append(second)
    assert len(intake.validate_reference_design(candidate, prepared)['coverage']['inventory_bindings'][candidate['devices'][0]['source_fact_ids'][0]]) == 2


def single_profile_part(candidate, prefix='0_'):
    return {key: [deepcopy(row) for row in rows if
        (row.get('id', '').startswith(prefix) if key == 'devices' else
         row.get('device_id', '').startswith(prefix) if key in {'commands', 'measurements'} else
         all(host.startswith(prefix) for host in row.get('executor_device_ids', [])))]
        for key, rows in candidate.items()}


def test_internal_profile_feedback_keeps_complete_original_but_final_validation_requires_all():
    prepared, candidate = profiled_fixture()
    partial = single_profile_part(candidate)
    profile = ['054. Roboterbeispiel']
    checked = intake.validate_reference_design_profile(partial, prepared, profile)
    assert checked['validation_scope'] == 'PROFILE_ONLY'
    assert checked['source_profile'] == profile
    assert checked['proposal']['unresolved'] == []
    assert len(checked['coverage']['function_fact_ids']) == 3
    assert checked['source_evidence'] == prepared['source_evidence']
    assert checked['fact_id_map'] == prepared['fact_id_map']
    final = intake.validate_reference_design(partial, prepared)
    assert 'validation_scope' not in final
    assert len(final['coverage']['function_fact_ids']) == 6
    assert {row['code'] for row in final['proposal']['unresolved']} >= {'REFERENCE_FUNCTION_UNCOVERED', 'REFERENCE_INVENTORY_UNCOVERED'}


def test_profile_identity_survives_measurement_catalog_validation(prepared):
    candidate = with_communication(fixture_design(prepared))
    checked = intake.validate_reference_design_profile(candidate, prepared, [])
    assert checked['source_profile'] == []
    assert checked['validation_scope'] == 'PROFILE_ONLY'
    assert 'validation_scope' not in intake.validate_reference_design(candidate, prepared)


def test_physical_context_has_explicit_canonical_membership_without_becoming_an_executor(prepared):
    candidate = fixture_design(prepared)
    candidate['devices'].append({'id': 'SW', 'name': 'Steuerungssoftware', 'kind': 'PHYSICAL_CONTEXT',
        'context_kind': 'SOFTWARE_SERVICE', 'quantity': 1, 'source_fact_ids': [candidate['functions'][0]['source_fact_id']],
        'rationale': 'Expliziter Softwarekontext auf dem Ausführungsgerät'})
    checked = intake.validate_reference_design(candidate, prepared)
    assert any(row['code'] == 'REFERENCE_CONTEXT_UNBOUND' for row in checked['proposal']['unresolved'])
    candidate['devices'][-1]['owner_device_id'] = 'C'
    checked = intake.validate_reference_design(candidate, prepared)
    assert not any(row['code'] == 'REFERENCE_CONTEXT_UNBOUND' for row in checked['proposal']['unresolved'])
    assert checked['proposal']['devices'][-1]['kind'] == 'PHYSICAL_CONTEXT'
    assert all(row['executor_device_ids'] == ['C'] for row in checked['proposal']['functions'])


def with_reference_port(candidate, technology='lin', parameters=None):
    candidate['ports'] = [{'id': 'P', 'device_id': 'C', 'technology': technology, 'role': 'LOCAL',
        'network_scope': 'reference_' + technology, 'parameters': parameters or {},
        'rationale': 'Prüfbare Softwareauslegung ohne Behauptung von Hardware- oder Abnahmenachweisen'}]
    return candidate


def lin_reference_configuration():
    return {'lin_edition': 'LIN_2_2A_2010', 'lin_physical_profile': 'LIN_2_2A_SINGLE_WIRE',
            'lin_node_role': 'COMMANDER', 'lin_frame_kind': 'UNCONDITIONAL', 'lin_bitrate_bps': 19200}


@pytest.mark.parametrize('parameter,value', [('lin_device_source', 'invented-vendor-proof'),
    ('lin_commander_node_id', 'invented-canonical-id'), ('lin_capacity_confirmed', True)])
def test_machine_reference_parameters_cannot_invent_evidence_or_canonical_references(prepared, parameter, value):
    candidate = with_reference_port(fixture_design(prepared), parameters={**lin_reference_configuration(), parameter: value})
    with pytest.raises(ValueError, match='keine Hardware-, Referenz- oder Abnahmebelege'):
        intake.validate_reference_design(candidate, prepared)


def test_missing_evidence_is_separate_qualification_with_the_unmodified_native_finding(prepared):
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    parameters = lin_reference_configuration()
    native = registry.validate_parameters('lin', parameters)
    candidate = with_reference_port(fixture_design(prepared), parameters=parameters)
    result = intake.validate_reference_design(candidate, prepared)
    roles = registry.parameter_roles('lin')
    expected = [row for row in native['findings'] if row['code'] == 'TECHNOLOGY_PARAMETER_MISSING'
                and roles.get(row.get('parameter')) in {'EVIDENCE', 'REFERENCE'}]
    assert expected and [row['finding'] for row in result['qualification_findings']] == expected
    assert result['qualification'] == 'UNVERIFIED' and result['hardware_evidence'] is False
    assert result['processing_evidence'] == 'NONE' and result['timing_evidence'] == 'NONE'
    assert all(row['qualification'] == 'UNVERIFIED' and row['hardware_evidence'] is False for row in result['qualification_findings'])
    assert not result['proposal']['unresolved']
    assert candidate['ports'][0]['parameters'] == parameters


def test_missing_configuration_still_blocks_the_design_review(prepared):
    parameters = lin_reference_configuration(); del parameters['lin_bitrate_bps']
    result = intake.validate_reference_design(with_reference_port(fixture_design(prepared), parameters=parameters), prepared)
    assert any(row['code'] == 'REFERENCE_PORT_TECHNOLOGY_PARAMETER_MISSING' and 'lin_bitrate_bps' in row['message']
               for row in result['proposal']['unresolved'])
    assert all(row['parameter'] != 'lin_bitrate_bps' for row in result['qualification_findings'])


def test_invalid_configuration_is_never_relabelled_as_missing_hardware_proof(prepared):
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    parameters = {**lin_reference_configuration(), 'lin_bitrate_bps': 25000}
    native_errors = [row for row in registry.validate_parameters('lin', parameters)['findings']
                     if row['code'] != 'TECHNOLOGY_PARAMETER_MISSING' and row['severity'] in {'ERROR', 'BLOCKER', 'OPEN', 'REVIEW'}]
    assert native_errors
    result = intake.validate_reference_design(with_reference_port(fixture_design(prepared), parameters=parameters), prepared)
    assert {'REFERENCE_PORT_' + row['code'] for row in native_errors} <= {row['code'] for row in result['proposal']['unresolved']}
    assert all(row['finding']['code'] == 'TECHNOLOGY_PARAMETER_MISSING' for row in result['qualification_findings'])


def test_existing_native_parameter_aliases_keep_configurable_values_as_assumptions(prepared):
    result = intake.validate_reference_design(with_reference_port(fixture_design(prepared), 'ethernet', {'bitrate': 1000000000}), prepared)
    assert not result['proposal']['unresolved'] and result['qualification_findings'] == []
    assert result['proposal']['ports'][0]['parameters'] == {'bitrate': 1000000000}
    assert result['qualification'] == 'UNVERIFIED' and result['hardware_evidence'] is False


@pytest.mark.parametrize('change', ['profile', 'parameter_role'])
def test_native_technology_and_role_revisions_invalidate_the_reference_request(monkeypatch, change):
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    prepared = intake.prepare_reference_design(fixture_request())
    candidate = fixture_design(prepared)
    if change == 'profile':
        original = registry.profiles
        def revised_profiles():
            profiles = original()
            next(row for row in profiles if row['id'] == 'lin')['parameter_schema']['lin_bitrate_bps']['max'] = 19000
            return profiles
        monkeypatch.setattr(registry, 'profiles', revised_profiles)
    else:
        original = registry.parameter_roles
        def revised_roles(technology):
            roles = original(technology)
            if technology == 'lin': roles['lin_tx_enabled'] = 'EVIDENCE'
            return roles
        monkeypatch.setattr(registry, 'parameter_roles', revised_roles)
    current = intake.prepare_reference_design(prepared['request'])
    assert current['catalog_sha256'] != prepared['catalog_sha256']
    assert current['request_sha256'] != prepared['request_sha256']
    with pytest.raises(ValueError, match='Auftragsrevision'):
        intake.validate_reference_design(candidate, prepared)


@pytest.mark.parametrize('mutation', ['foreign_fact', 'foreign_profile', 'invented_scope', 'changed_source'])
def test_internal_profile_feedback_cannot_change_scope_or_primary_evidence(mutation):
    prepared, candidate = profiled_fixture()
    partial = single_profile_part(candidate)
    profile = ['054. Roboterbeispiel']
    if mutation == 'foreign_fact': partial['devices'].append(deepcopy(candidate['devices'][3]))
    elif mutation == 'foreign_profile': profile = ['055. Zellenbeispiel']
    elif mutation == 'invented_scope': profile = ['054.']
    else: prepared['request']['prompt'] += '\nchanged request'
    with pytest.raises(ValueError): intake.validate_reference_design_profile(partial, prepared, profile)


def test_same_instance_label_uses_existing_scoped_identity_and_profile_specific_protection(monkeypatch):
    from backend.nis.agent.tools import wizard_generation
    prepared, candidate = profiled_fixture()
    original_catalog = wizard_generation.reference_design_catalog
    source_devices = [{'name': device['name'], 'device_type': 'PLC', 'evidence': deepcopy(prepared['facts'][device['source_fact_ids'][0]])}
                      for device in candidate['devices'] if device['kind'] == 'CONTROLLER']
    monkeypatch.setattr(wizard_generation, 'reference_design_catalog', lambda prompt: {
        **original_catalog(prompt), 'source_devices': source_devices,
        'confirmed_commands': {'1_Ventil': wire()}, 'confirmed_owners': {'1_Temperatursensor': '1_Controller (ECU)'},
    })
    prepared = intake.prepare_reference_design(prepared['request'])
    partial = single_profile_part(candidate)
    checked = intake.validate_reference_design_profile(partial, prepared, ['054. Roboterbeispiel'])
    assert checked['proposal']['unresolved'] == []
    assert checked['protected_fields']['commands'] == {'1_Ventil': wire()}
    partial['devices'][0]['name'] = 'LostOriginalScopedIdentity'
    with pytest.raises(ValueError, match='Instanzidentität'):
        intake.validate_reference_design_profile(partial, prepared, ['054. Roboterbeispiel'])


def test_reference_decoder_preserves_contract_and_source_bindings(prepared):
    public = intake.reference_design_schema(prepared)
    original = deepcopy(public)
    decoder = intake.reference_model_output_schema(prepared)
    assert intake.reference_design_schema(prepared) == original
    assert public['properties']['devices']['maxItems'] == 2000
    assert public['$defs']['ReferenceDevice']['properties']['rationale']['maxLength'] == 2000
    assert 'maxItems' not in decoder['properties']['devices']
    assert 'maxLength' not in decoder['$defs']['ReferenceDevice']['properties']['rationale']
    device = decoder['$defs']['ReferenceDevice']
    assert device['additionalProperties'] is False
    assert device['required'] == public['$defs']['ReferenceDevice']['required']
    assert device['properties']['source_fact_ids']['minItems'] == 1
    assert set(device['properties']['source_fact_ids']['items']['enum']) == set(prepared['facts'])
    assert device['properties']['id']['minLength'] == 1
    assert device['properties']['quantity'] == public['$defs']['ReferenceDevice']['properties']['quantity']
    assert device['properties']['kind'] == public['$defs']['ReferenceDevice']['properties']['kind']
    technology = decoder['$defs']['ReferencePort']['properties']['technology']
    public_technology = public['$defs']['ReferencePort']['properties']['technology']
    assert technology['enum'] == public_technology['enum']
    assert technology['type'] == public_technology['type']
    assert technology['minLength'] == public_technology['minLength']
    assert public_technology['maxLength'] == 80 and 'maxLength' not in technology
    device['properties']['source_fact_ids']['items']['enum'].clear()
    assert public == original and intake.reference_design_schema(prepared) == original


def test_reference_decoder_keeps_zero_bounds(monkeypatch):
    public = {'type': 'object', 'properties': {'unused': {'type': 'array', 'maxItems': 0},
              'empty': {'type': 'string', 'maxLength': 0}}, 'additionalProperties': False}
    monkeypatch.setattr(intake, 'reference_design_schema', lambda prepared=None: public)
    projected = intake.reference_model_output_schema()
    assert projected == public and projected is not public


def test_reference_decoder_distinguishes_schema_keywords_from_data_names(monkeypatch):
    public = {'type': 'object', 'required': ['maxLength'],
              'properties': {'maxLength': {'type': 'string', 'maxLength': 8},
                             'payload': {'const': {'maxItems': 7, 'maxLength': 8},
                                         'default': {'maxLength': 9}, 'enum': [{'maxItems': 10}]}},
              '$defs': {'maxItems': {'type': 'array', 'maxItems': 11, 'items': {'type': 'string', 'maxLength': 12}}},
              'x-metadata': {'maxLength': 13}}
    original = deepcopy(public)
    monkeypatch.setattr(intake, 'reference_design_schema', lambda prepared=None: public)
    projected = intake.reference_model_output_schema()
    assert projected['required'] == ['maxLength']
    assert projected['properties']['maxLength'] == {'type': 'string'}
    assert projected['properties']['payload'] == original['properties']['payload']
    assert projected['x-metadata'] == original['x-metadata']
    assert projected['$defs']['maxItems'] == {'type': 'array', 'items': {'type': 'string'}}
    assert public == original


@pytest.mark.parametrize('field', ['devices', 'rationale', 'port_technology'])
def test_decoder_projection_does_not_accept_oversized_server_candidates(field):
    from pydantic import ValidationError
    device = {'id': 'C', 'name': 'Controller', 'kind': 'CONTROLLER', 'quantity': 1,
              'source_fact_ids': ['F1'], 'rationale': 'Explicit example choice'}
    intake.ReferenceDesignProposal.model_validate({'devices': [device]})
    intake.reference_model_output_schema()
    if field == 'devices':
        candidate, location, error_type = {'devices': [device] * 2001}, ('devices',), 'too_long'
    elif field == 'rationale':
        candidate = {'devices': [{**device, 'rationale': 'x' * 2001}]}
        location, error_type = ('devices', 0, 'rationale'), 'string_too_long'
    else:
        candidate = {'ports': [{'id': 'P', 'device_id': 'C', 'technology': 'x' * 81,
                                'role': 'LOCAL', 'network_scope': 'Bus', 'rationale': 'Explicit choice'}]}
        location, error_type = ('ports', 0, 'technology'), 'string_too_long'
    with pytest.raises(ValidationError) as error:
        intake.ReferenceDesignProposal.model_validate(candidate)
    assert any(row['loc'] == location and row['type'] == error_type for row in error.value.errors())


def test_local_reference_planner_uses_decoder_projection_but_rejects_oversized_response(prepared):
    import asyncio
    from backend.nis.agent.orchestration.local_reasoner import LocalEngineeringReasoner
    candidate = {'devices': [{**fixture_design(prepared)['devices'][0], 'rationale': 'x' * 2001}]}
    encoded_candidate = json.dumps({**candidate, 'inventory_complete': True, 'inventory_bindings': []})
    requests = []
    class Response:
        is_error = False
        def __init__(self, body): self.body = body
        def json(self): return self.body
    class Client:
        async def post(self, url, *, json):
            if url.endswith('/show'):
                return Response({'details': {'family': 'qwen35'}, 'model_info': {'general.parameter_count': 27_000_000_000}})
            requests.append(json)
            return Response({'message': {'content': encoded_candidate}})
    async def run():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()
        reasoner.client = Client()
        return await reasoner.plan_reference_design(prepared)
    with pytest.raises(ValueError, match='2000'):
        asyncio.run(run())
    assert len(requests) == 2
    expected = intake.reference_model_output_schema(prepared)
    # The participant phase preserves the public decoder's constraints while
    # forbidding arrays that belong to later native planning phases.
    for field in ('functions', 'ports', 'measurements', 'commands', 'communication', 'functional_dependencies'):
        expected['properties'][field]['maxItems'] = 0
    expected['properties']['devices'].update(minItems=1, maxItems=1)
    expected['properties']['inventory_complete'] = {'type': 'boolean'}
    device_properties = expected['$defs']['ReferenceDevice']['properties']
    binding_properties = {key: deepcopy(device_properties[key])
                          for key in ('source_fact_ids', 'rationale', 'field_references')}
    binding_properties['source_fact_ids'].update(minItems=1, maxItems=1)
    binding_properties['source_fact_ids']['items']['enum'] = sorted(
        key for key, fact in prepared['facts'].items() if fact['role'] == 'SENSOR')
    binding_properties['device_id'] = {'type': 'string', 'minLength': 1}
    # Only the source-compiled controller exists at this first sensor cursor;
    # it is not a sensor candidate and cannot be selected as a substitute.
    expected['properties']['inventory_bindings'] = {
        'type': 'array', 'minItems': 0, 'maxItems': 0,
        'items': {'type': 'object', 'properties': binding_properties,
                  'required': list(binding_properties), 'additionalProperties': False}}
    expected.setdefault('required', []).extend(['inventory_complete', 'inventory_bindings'])
    for request in requests:
        actual = deepcopy(request['format'])
        variants = actual['$defs']['ReferenceDevice']['anyOf']
        sensor = next(row for row in variants if row['properties']['kind']['enum'] == ['SENSOR'])
        assert len(variants) == 1
        assert sensor['properties']['source_member_bindings'] == {
            'type': 'object', 'properties': {}, 'additionalProperties': False}
        assert sensor['properties']['quantity'] == {'type': 'integer', 'enum': [1]}
        assert all(row['properties']['rationale'] == expected['$defs']['ReferenceDevice']['properties']['rationale']
                   for row in variants)
        actual['$defs']['ReferenceDevice'] = deepcopy(expected['$defs']['ReferenceDevice'])
        assert actual == expected
        assert request['options']['num_predict'] == 8192
    assert intake.reference_design_schema(prepared)['$defs']['ReferenceDevice']['properties']['rationale']['maxLength'] == 2000


@pytest.mark.parametrize('context,timeout,expected_context,expected_timeout', [
    (None, None, 131072, 1200),
    ('65536', '900', 65536, 900),
    ('1', '1', 8192, 90),
    ('999999', '999999', 131072, 1200),
])
def test_local_reference_runtime_defaults_overrides_and_existing_caps(monkeypatch, context, timeout, expected_context, expected_timeout):
    import asyncio
    from backend.nis.agent.orchestration.local_reasoner import LocalEngineeringReasoner
    for key, value in [('LOCAL_AI_CONTEXT_TOKENS', context), ('LOCAL_AI_TIMEOUT_SECONDS', timeout)]:
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    async def run():
        reasoner = LocalEngineeringReasoner()
        try:
            return reasoner.context_tokens, reasoner.client.timeout.read
        finally:
            await reasoner.client.aclose()
    assert asyncio.run(run()) == (expected_context, expected_timeout)
