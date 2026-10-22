import asyncio
import hashlib
import json

import httpx
import pytest

from backend.nis.agent.orchestration.project_intake import validate_document_interpretation
from backend.nis.agent.orchestration.local_reasoner import LocalEngineeringReasoner


SOURCE = '1.1 ADAS Domain Controller (ADC)\nSensorik (Radar, Kamera)\nSensor: Probe\nAnschluss: ADC Eingang\nREQ-SAFE-14: Fusion MUSS bei Ausfall eines Sensors degradieren.'


def interpretation():
    return {
        'summary': 'Controller und unquantifizierte Sensorik getrennt prüfen.',
        'components': [
            {'name': 'ADAS Domain Controller', 'kind': 'INSTANCE', 'role': 'CONTROLLER', 'quantity': 1,
             'source_quote': '1.1 ADAS Domain Controller (ADC)'},
            {'name': 'Radar', 'kind': 'CATEGORY', 'role': 'SENSOR', 'quantity': None,
             'source_quote': 'Sensorik (Radar, Kamera)'},
            {'name': 'Probe', 'kind': 'CATEGORY', 'role': 'SENSOR', 'quantity': None,
             'source_quote': 'Sensor: Probe'},
            {'name': 'Fusion', 'kind': 'REQUIREMENT', 'role': 'OTHER', 'quantity': None,
             'source_quote': 'REQ-SAFE-14: Fusion MUSS bei Ausfall eines Sensors degradieren.'},
        ],
        'technologies': [{'name': 'ADC', 'kind': 'DEVICE_ALIAS', 'source_quote': '1.1 ADAS Domain Controller (ADC)'},
                         {'name': 'ADC', 'kind': 'TRANSPORT', 'source_quote': 'Anschluss: ADC Eingang'}],
        'proposed_task': 'ADAS-Verarbeitung mit Sensorik planen; Stückzahlen und Schnittstellen klären.',
        'assumptions': [], 'open_questions': ['Wie viele konkrete Radarsensoren?'],
    }


def test_mixed_architecture_clauses_have_disjoint_literal_references_and_no_parent_escape():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references, resolve_document_references
    source = 'Architektur: Raumcontroller, Sensorik (Luft, Temperatur), Aktoren.\r\n'
    rows = document_source_references(source)
    units = document_component_sources(rows)
    assert [u['policy']['role'] for u in units] == ['CONTROLLER', 'SENSOR', 'ACTUATOR']
    assert all(u['text'] in source and u['required'] for u in units)
    data = {'components': [{'source_ref': u['source_ref'], **u['policy']} for u in units], 'technologies': []}
    projected = resolve_document_references(data, rows)
    assert [c['source_quote'] for c in projected['components']] == ['Raumcontroller', 'Sensorik (Luft, Temperatur)', 'Aktoren']
    data['components'][0]['source_ref'] = 'R0001'
    with pytest.raises(ValueError, match='Ungültige Quellenreferenz'):
        resolve_document_references(data, rows)


@pytest.mark.parametrize('label,role', [('Motorcontroller (z. B. Drive A, Drive B)', 'CONTROLLER'),
                                      ('Mikrocontroller (ChipA, ChipB) für Echtzeitmotorik', 'CONTROLLER'),
                                      ('Ultraschallsensoren (8–12 Stück)', 'SENSOR'),
                                      ('Raumcontroller', 'CONTROLLER'), ('Embedded Controller', 'CONTROLLER')])
def test_generic_or_alternative_hardware_is_not_an_installed_instance(label, role):
    from backend.nis.agent.orchestration.project_intake import document_component_policy
    assert document_component_policy(label) == {'kind': 'CATEGORY', 'role': role, 'quantity': None}


def test_processing_and_all_named_function_groups_are_preserved():
    from backend.nis.agent.orchestration.project_intake import document_component_policy, document_component_sources, document_source_references
    assert document_component_policy('Baseband-Processing')['kind'] == 'FUNCTION'
    source = '3. Funktionsbeschreibung\n3.1 Navigation\nPfadplanung\n3.2 Manipulation\nGreifen\n4. Anforderungen\nF-REQ-1: Das System muss stoppen.'
    units = document_component_sources(document_source_references(source))
    functions = [u for u in units if u['required'] and u['policy'] and u['policy']['kind'] == 'FUNCTION']
    assert [u['text'].splitlines()[0] for u in functions] == ['3.1 Navigation', '3.2 Manipulation']
    assert 'Pfadplanung' in functions[0]['text'] and 'Greifen' in functions[1]['text']
    assert units[-1]['policy']['kind'] == 'REQUIREMENT'


def test_canonical_aliases_preserve_unicode_source_and_transport_qualifiers():
    from backend.nis.agent.orchestration.project_intake import document_registered_transport_citation
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    assert DEFAULT_TECHNOLOGY_REGISTRY.normalize_id('I²C') == 'i2c'
    assert DEFAULT_TECHNOLOGY_REGISTRY.normalize_id('WLAN') == 'wifi'
    assert document_registered_transport_citation('i2c', 'Sensor → I²C')
    assert document_registered_transport_citation('wifi', 'Telemetrie über WLAN')
    assert not document_registered_transport_citation('uart', 'SpaceWire/CAN/UART-ähnliche interne Busse')
    assert document_registered_transport_citation('uart', 'UART-ähnlich diskutiert; Anschluss: UART')


def test_semantic_validation_rejects_wrong_compound_controller_role_and_alternative_instance():
    label = 'Motorcontroller (z. B. Drive A, Drive B)'
    data = {**interpretation(), 'components': [{'name': label, 'source_quote': label, 'kind': 'CATEGORY', 'role': 'ACTUATOR', 'quantity': None}], 'technologies': []}
    with pytest.raises(ValueError, match='CONTROLLER'):
        validate_document_interpretation(data, label)
    data['components'][0].update(kind='INSTANCE', role='CONTROLLER', quantity=1)
    with pytest.raises(ValueError, match='keine individuelle Instanz'):
        validate_document_interpretation(data, label)


def test_missing_function_group_is_a_semantic_failure_even_with_valid_hardware():
    source = 'Funktionen: Navigation, Manipulation.'
    data = {**interpretation(), 'components': [], 'technologies': []}
    with pytest.raises(ValueError, match='Quellenangabe fehlt'):
        validate_document_interpretation(data, source)


def test_connection_only_source_keeps_transport_evidence_without_extra_hardware():
    from backend.nis.agent.orchestration.project_intake import DocumentInterpretation, document_output_schema, document_technology_grounding
    schema = document_output_schema('Motorcontroller → CAN', DocumentInterpretation.model_json_schema())
    assert schema['properties']['components']['maxItems'] == 0
    assert 'can' in document_technology_grounding(schema)['registered_transports']


def test_plain_function_section_body_and_manual_control_do_not_become_controllers():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    units = document_component_sources(document_source_references('3. Funktionsbeschreibung\nMode Management, FDIR\nManuelle Steuerung des Arms\n4. Anforderungen'))
    functions = [u for u in units if u['policy'] and u['policy']['kind'] == 'FUNCTION']
    assert len(functions) == 1 and functions[0]['required']
    assert 'Mode Management' in functions[0]['text'] and 'Manuelle Steuerung des Arms' in functions[0]['text']


def test_explicit_requirements_cannot_disappear_behind_correct_hardware_or_functions():
    source = 'Funktionen: Dosieren.\nAnforderungen: Stoppfunktion, nachvollziehbare Alarme.'
    data = {**interpretation(), 'components': [{'name': 'Dosieren', 'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None, 'source_quote': 'Funktionen: Dosieren.'}], 'technologies': []}
    with pytest.raises(ValueError, match='Anforderungen'):
        validate_document_interpretation(data, source)


def test_source_windows_reserve_output_capacity_for_every_required_fact():
    source = '\n'.join(f'REQ-G-{i:03d}: Das System muss Zustand {i} melden.\nHinweisblock {i}' for i in range(35))
    observed = []
    async def run():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()
        def transport(request):
            if request.url.path == '/api/show':
                return httpx.Response(200, json={'details': {'family': 'qwen35'}, 'model_info': {'general.parameter_count': 27000000000}})
            observed.append(json.loads(request.content))
            raise RuntimeError('output-capacity probe')
        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        try:
            with pytest.raises(RuntimeError, match='output-capacity probe'):
                await reasoner.interpret_document(source, 'requirements.txt')
        finally:
            await reasoner.client.aclose()
    asyncio.run(run())
    data = json.loads(observed[0]['messages'][1]['content'])
    assert 0 < len(data['required_components']) <= 24
    assert source.startswith(''.join(data['source_lines'].values()))
    assert ''.join(data['source_lines'].values()) != source


def test_adjacent_requirement_groups_preserve_every_original_character_and_avoid_output_loss():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_component_grounding, document_source_references, resolve_document_references
    source = '\r\n\r\n'.join(f'REQ-G-{i:03d}: Das System muss Zustand {i} melden.' for i in range(35))
    rows = document_source_references(source)
    groups = document_component_sources(rows)
    assert 1 < len(groups) < 24
    assert all(len(g['text']) <= 1200 for g in groups)
    wire = {'components': [{'source_ref': g['source_ref'], **g['policy']} for g in groups], 'technologies': []}
    facts = resolve_document_references(wire, rows)['components']
    for line in source.splitlines():
        assert not line or any(line in f['source_quote'] for f in facts)
    assert all(f['source_quote'] in source for f in facts)
    assert all(f['kind'] == 'REQUIREMENT' and f['quantity'] is None for f in facts)
    assert all('source_rows' in value for value in document_component_grounding(rows)['component_sources'].values())


def test_requirement_group_never_splices_over_a_connection_statement():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    source = 'REQ-A: Das System muss stoppen.\nSensor → UART\nREQ-B: Das System muss protokollieren.'
    units = document_component_sources(document_source_references(source))
    assert len(units) == 2
    assert all(u['text'] in source for u in units)


def test_system_function_scope_stops_at_its_next_sibling_section():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    source = '2.1 Systemfunktionen\n2.1.1 Manuelle Steuerung\nMotorsteuerung\n2.2 Hardware\nMotorcontroller'
    units = document_component_sources(document_source_references(source))
    assert any(u['policy'] and u['policy']['kind'] == 'FUNCTION' and '2.1.1 Manuelle Steuerung' in u['text'] and 'Motorsteuerung' in u['text'] for u in units)
    assert units[-1]['policy']['role'] == 'CONTROLLER'


def test_qualified_transport_cannot_be_confirmed_or_silently_omitted():
    from backend.nis.agent.orchestration.project_intake import DocumentInterpretation, document_output_schema, document_technology_grounding
    source = 'Schnittstellen: UART-ähnliche interne Busse.'
    choices = document_technology_grounding(document_output_schema(source, DocumentInterpretation.model_json_schema()))
    assert 'uart' not in choices['registered_transports']
    assert choices['unresolved_transports'] == {'UART-ähnliche': ['R0001']}
    data = {**interpretation(), 'components': [], 'technologies': []}
    with pytest.raises(ValueError, match='UNRESOLVED erhalten'):
        validate_document_interpretation(data, source)
    data['technologies'] = [{'name': 'UART-ähnliche', 'kind': 'UNRESOLVED', 'source_quote': source}]
    assert validate_document_interpretation(data, source)['technologies'][0]['kind'] == 'UNRESOLVED'


def test_model_keys_couple_single_claims_to_their_exact_source_and_keep_public_lists():
    from backend.nis.agent.orchestration.project_intake import DocumentInterpretation, document_output_schema, document_model_output_schema, document_source_references, resolve_document_references
    from jsonschema import validate, ValidationError
    source = 'Architektur: Raumcontroller, Sensorik, Aktoren.'
    rows = document_source_references(source)
    schema = document_model_output_schema(document_output_schema(source, DocumentInterpretation.model_json_schema()), rows)
    data = {**interpretation(), 'components': {'R0001.C01': {'kind': 'CATEGORY', 'role': 'CONTROLLER', 'quantity': None}, 'R0001.C02': {'kind': 'CATEGORY', 'role': 'SENSOR', 'quantity': None}, 'R0001.C03': {'kind': 'CATEGORY', 'role': 'ACTUATOR', 'quantity': None}}, 'technologies': []}
    data['technologies'] = {}
    validate(data, schema)
    projected = resolve_document_references(data, rows, model_schema=schema)
    assert isinstance(projected['components'], list) and len(projected['components']) == 3
    assert projected['components'][0]['source_quote'] == 'Raumcontroller'
    data['components']['R0001'] = data['components']['R0001.C01']
    with pytest.raises(ValidationError):
        validate(data, schema)


def test_duplicate_model_json_keys_are_rejected_before_claim_projection():
    from backend.nis.agent.orchestration.project_intake import document_response_json
    with pytest.raises(ValueError, match='Doppelter Schlüssel'):
        document_response_json('{"components":{"R0001":{"kind":"CATEGORY"},"R0001":{"kind":"INSTANCE"}}}')


def test_unknown_inventory_questions_do_not_imply_existing_named_instances():
    from backend.nis.agent.orchestration.project_intake import compose_document_proposal
    part = {'components': [{'name': 'Raumcontroller', 'kind': 'CATEGORY', 'role': 'CONTROLLER', 'quantity': None, 'source_quote': 'Raumcontroller'}], 'technologies': []}
    result = compose_document_proposal([part])
    assert result['open_questions'] and 'bereits benannten Instanzen' not in ' '.join(result['open_questions'])
    assert any('Anschlüsse' in q and 'Funktionspartner' in q for q in result['open_questions'])


@pytest.mark.parametrize('name', ['Funkmodul', 'Teach-Panel', 'Messmodul', 'Netzteil', 'DC-DC-Wandler'])
def test_unquantified_physical_assemblies_are_hardware_without_assumed_network_role(name):
    from backend.nis.agent.orchestration.project_intake import document_component_policy
    assert document_component_policy(name) == {'kind': 'CATEGORY', 'role': 'OTHER', 'quantity': None}


def test_software_modules_and_named_gateways_keep_distinct_semantics():
    from backend.nis.agent.orchestration.project_intake import document_component_policy
    assert document_component_policy('Softwaremodul für Signalverarbeitung')['kind'] == 'FUNCTION'
    assert document_component_policy('Gateway (GW)') == {'kind': 'INSTANCE', 'role': 'GATEWAY', 'quantity': 1}


def test_physical_inventory_is_required_without_counting_titles_prose_or_bus_assignments():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    source = 'Systembeschreibung – Roboter mit Sensorik\nDer Roboter ist mit Kamera ausgestattet.\nSensorik\nUltraschallsensoren (8–12 Stück)\nServomotoren\nCAN-Bus für Motoren\nI²C für Sensoren\nUART für LiDAR'
    units = document_component_sources(document_source_references(source))
    assert [u['text'] for u in units] == ['Sensorik', 'Ultraschallsensoren (8–12 Stück)', 'Servomotoren']
    assert all(u['required'] and u['policy']['kind'] == 'CATEGORY' for u in units)


@pytest.mark.parametrize('name', ['Greifer mit Kraftsensor oder Zweifingermechanik', 'Motor mit Encoder'])
def test_actuator_with_integrated_feedback_does_not_become_a_sensor(name):
    from backend.nis.agent.orchestration.project_intake import document_component_policy
    assert document_component_policy(name)['role'] == 'ACTUATOR'


def test_responsibility_section_does_not_turn_control_functions_into_new_hardware():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    source = '2.1 Controller (C1)\nAufgaben:\nMotorsteuerung\nGetriebelogik\nSchnittstellen:\nCAN\n2.2 Controller (C2)'
    units = document_component_sources(document_source_references(source))
    assert units[0]['policy']['kind'] == units[-1]['policy']['kind'] == 'INSTANCE'
    functions = [u for u in units if u['policy'] and u['policy']['kind'] == 'FUNCTION' and u['required']]
    assert len(functions) == 1 and 'Motorsteuerung' in functions[0]['text'] and 'Getriebelogik' in functions[0]['text']


def test_complete_requirement_coverage_accepts_different_window_group_boundaries():
    source = 'REQ-A: Das System muss stoppen.\nREQ-B: Das System muss protokollieren.'
    data = {**interpretation(), 'components': [{'name': line, 'kind': 'REQUIREMENT', 'role': 'OTHER', 'quantity': None, 'source_quote': line} for line in source.splitlines()], 'technologies': []}
    assert len(validate_document_interpretation(data, source)['components']) == 2
    data['components'].pop()
    with pytest.raises(ValueError, match='REQ-B'):
        validate_document_interpretation(data, source)


def test_declared_unknown_ports_and_radio_families_are_preserved_without_richer_defaults():
    from backend.nis.agent.orchestration.project_intake import DocumentInterpretation, document_output_schema, document_technology_grounding
    source = 'Kommunikation\nWiFi/Bluetooth für Telemetrie\n5. Schnittstellen\nKamera → CSI\nGreifarm → PWM/Serial\n6. Anforderungen\nREQ-COM-2: Das System muss per Web-Interface bedienbar sein.'
    choices = document_technology_grounding(document_output_schema(source, DocumentInterpretation.model_json_schema()))
    assert set(choices['unresolved_transports']) == {'Bluetooth', 'CSI', 'Serial'}
    assert set(choices['registered_transports']) == {'wifi', 'pwm'}
    assert 'bluetooth_le' not in choices['registered_transports'] and 'mipi_csi2' not in choices['registered_transports']


def test_slash_inside_registered_protocol_is_not_an_unknown_fragment_or_extra_ip_layer():
    from backend.nis.agent.orchestration.project_intake import DocumentInterpretation, document_output_schema, document_technology_grounding
    choices = document_technology_grounding(document_output_schema('Schnittstellen: SOME/IP, Mobilfunk', DocumentInterpretation.model_json_schema()))
    assert set(choices['registered_transports']) == {'someip'}
    assert set(choices['unresolved_transports']) == {'Mobilfunk'}


def test_technology_model_keys_bind_kind_identity_and_citation_independently():
    from backend.nis.agent.orchestration.project_intake import DocumentInterpretation, document_output_schema, document_model_output_schema, document_source_references, resolve_document_references
    from jsonschema import validate, ValidationError
    source = 'Controller (ADC)\nAnschluss: ADC Eingang\nUnbekannte Schnittstelle: XYZ'
    rows = document_source_references(source)
    schema = document_model_output_schema(document_output_schema(source, DocumentInterpretation.model_json_schema()), rows)
    facts = {'summary':'Prüfen','proposed_task':'Anschlüsse bestätigen','components':{'R0001':{'kind':'INSTANCE','role':'CONTROLLER','quantity':1}}, 'technologies':{'DEVICE_ALIAS:ADC':'R0001','TRANSPORT:adc':'R0002','UNRESOLVED:XYZ':'R0003'}, 'assumptions':[], 'open_questions':['Welche Realisierung hat XYZ?']}
    validate(facts, schema)
    result = resolve_document_references(facts, rows, model_schema=schema)
    assert {(t['kind'],t['name']) for t in result['technologies']} == {('DEVICE_ALIAS','ADC'),('TRANSPORT','adc'),('UNRESOLVED','XYZ')}
    facts['technologies']['TRANSPORT:adc'] = 'R0001'
    with pytest.raises(ValidationError): validate(facts,schema)
    with pytest.raises(ValueError,match='Nicht belegter'): resolve_document_references(facts,rows,model_schema=schema)


def test_function_and_interface_scope_survive_window_boundaries():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references, DocumentInterpretation, document_output_schema, document_technology_grounding
    prefix = '3. Funktionsbeschreibung\n3.1 Navigation\nPfadplanung\n'
    units = document_component_sources(document_source_references('Manuelle Steuerung\n4. Anforderungen'),scope_prefix=prefix)
    assert units[0]['required'] and units[0]['policy']['kind']=='FUNCTION'
    schema = document_output_schema('XYZ',DocumentInterpretation.model_json_schema(),scope_prefix='5. Schnittstellen\n')
    assert set(document_technology_grounding(schema)['unresolved_transports']) == {'XYZ'}


def test_explicit_aggregate_quantity_does_not_become_a_single_named_device_in_task():
    from backend.nis.agent.orchestration.project_intake import compose_document_proposal
    result=compose_document_proposal([{'components':[{'name':'3 Sensoren','kind':'INSTANCE','role':'SENSOR','quantity':3,'source_quote':'3 Sensoren'}],'technologies':[]}])
    assert 'Die 3 durch 1 Quellenangaben belegten Geräteinstanzen' in result['proposed_task']
    assert '1 konkret benannten Geräte' not in result['proposed_task']


def model_wire_response(value, payload):
    """Mock the actual reference-only model contract, retaining bad references."""
    from copy import deepcopy
    rows = json.loads(payload['messages'][1]['content'])['source_lines']
    result = deepcopy(value)
    for field in ('components', 'technologies'):
        for item in result[field]:
            quote = item.pop('source_quote')
            item['source_ref'] = next((reference for reference, text in rows.items() if quote == text.strip()), 'INVALID')
            if field == 'components':
                item.pop('name')
    shape = payload.get('format', {}).get('properties', {})
    if shape.get('components', {}).get('type') == 'object':
        result['components'] = {item.pop('source_ref'): item for item in result['components']}
    if shape.get('technologies', {}).get('type') == 'object':
        from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
        result['technologies'] = {item['kind'] + ':' + (DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(item['name']) if item['kind'] == 'TRANSPORT' else item['name']): item['source_ref'] for item in result['technologies']}
    return result


def test_source_bound_facts_preserve_unknown_sensor_count_and_device_alias():
    result = validate_document_interpretation(interpretation(), SOURCE)
    assert result['components'][1]['quantity'] is None
    assert result['technologies'][0]['kind'] == 'DEVICE_ALIAS'


@pytest.mark.parametrize('kind,role', [('CATEGORY', 'OTHER'), ('FUNCTION', 'SENSOR'), ('REQUIREMENT', 'CONTROLLER')])
def test_logical_functions_and_requirements_do_not_become_hardware_categories(kind, role):
    source = SOURCE + '\nSensorfusion (Radar, Kamera, Lidar, IMU)'
    data = interpretation()
    data['components'].append({'name': 'Sensorfusion', 'kind': kind, 'role': role,
                               'quantity': None, 'source_quote': 'Sensorfusion (Radar, Kamera, Lidar, IMU)'})
    with pytest.raises(ValueError, match='Gerätekategorie|Geräterolle'):
        validate_document_interpretation(data, source)
    data['components'][-1].update(kind='FUNCTION', role='OTHER')
    assert validate_document_interpretation(data, source)['components'][-1]['kind'] == 'FUNCTION'


@pytest.mark.parametrize('name', ['Mechanische Baugruppen', 'Elektrische Energieversorgung', 'Housing structures'])
def test_other_hardware_categories_remain_categories_without_invented_network_role(name):
    data = interpretation()
    data['components'].append({'name': name, 'kind': 'CATEGORY', 'role': 'OTHER', 'quantity': None, 'source_quote': name})
    assert validate_document_interpretation(data, SOURCE + '\n' + name)['components'][-1]['kind'] == 'CATEGORY'


def test_repeated_bus_cannot_replace_other_explicitly_cited_registered_transports():
    data = interpretation()
    source = SOURCE + '\nCAN-FD\nEthernet\nLIN'
    data['technologies'].extend([{'name': 'CAN-FD', 'kind': 'TRANSPORT', 'source_quote': 'CAN-FD'}] * 3)
    with pytest.raises(ValueError, match='ethernet, lin'):
        validate_document_interpretation(data, source)
    data['technologies'].extend({'name': name, 'kind': 'TRANSPORT', 'source_quote': name} for name in ['Ethernet', 'LIN'])
    validate_document_interpretation(data, source)


def test_model_grounding_uses_same_source_tuples_and_separates_alias_from_physical_adc():
    from backend.nis.agent.orchestration.project_intake import DocumentInterpretation, document_output_schema, document_technology_grounding
    source = 'ADAS Controller (ADC)\nAnschluss: ADC Eingang\nKommunikation: CAN-FD\nUnbekannte Schnittstelle: GMSL'
    choices = document_technology_grounding(document_output_schema(source, DocumentInterpretation.model_json_schema()))
    assert choices['device_aliases'] == {'ADC': ['R0001']}
    assert choices['registered_transports']['adc'] == ['R0002']
    assert choices['registered_transports']['can_fd'] == ['R0003']
    assert 'can' not in choices['registered_transports'] and 'GMSL' not in choices['registered_transports']


@pytest.mark.parametrize('failure', ['invented_quote', 'category_count', 'alias_transport', 'requirement_device', 'unknown_transport', 'missing_question'])
def test_rejects_unproven_document_facts(failure):
    data = interpretation()
    if failure == 'invented_quote':
        data['components'][0]['source_quote'] = 'Der Controller steht vorne links.'
    elif failure == 'category_count':
        data['components'][1]['quantity'] = 4
    elif failure == 'alias_transport':
        data['technologies'][0]['kind'] = 'TRANSPORT'
    elif failure == 'requirement_device':
        data['components'].append({'name': 'Fusion', 'kind': 'INSTANCE', 'role': 'CONTROLLER', 'quantity': 1,
                                   'source_quote': SOURCE.splitlines()[-1]})
    elif failure == 'unknown_transport':
        data['technologies'] = [{'name': 'GMSL', 'kind': 'TRANSPORT', 'source_quote': 'GMSL'}]
    else:
        data['open_questions'] = []
    with pytest.raises(ValueError):
        validate_document_interpretation(data, SOURCE + ('\nGMSL' if failure == 'unknown_transport' else ''))


def test_utf8_segments_cover_original_source_without_loss_or_overlap():
    from backend.nis.agent.orchestration.project_intake import document_segments
    source = ('Äußere Sensorik 🚗: Kamera\n' * 45) + 'Letzter vollständiger Satz.'
    parts = document_segments(source, max_bytes=250)
    assert ''.join(part['text'] for part in parts) == source
    assert parts[0]['start'] == 0 and parts[-1]['end'] == len(source)
    assert all(a['end'] == b['start'] for a, b in zip(parts, parts[1:]))
    assert all(len(part['text'].encode()) <= 250 for part in parts)


def test_late_controller_evidence_replaces_early_missing_context_prose_in_global_task():
    """Exercise the complete multi-window path with deliberately stale prose."""
    observed = []
    async def run():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()
        def transport(request):
            if request.url.path == '/api/show':
                return httpx.Response(200, json={'details': {'family': 'qwen35'}, 'model_info': {'general.parameter_count': 27000000000}})
            payload = json.loads(request.content)
            observed.append(payload)
            text = ''.join(json.loads(payload['messages'][1]['content'])['source_lines'].values())
            value = interpretation() if 'ADAS Domain Controller' in text else {
                **interpretation(), 'components': [], 'technologies': [], 'open_questions': [],
            }
            value.update(proposed_task='Keine konkreten Geräte vorhanden.',
                         assumptions=['R0001: Es sind keine Controller benannt.'],
                         open_questions=['Welche Controller werden später benannt?'])
            return httpx.Response(200, json={'message': {'content': json.dumps(model_wire_response(value, payload))}})
        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        try:
            result = await reasoner.interpret_document('A' * 6500 + '\n' + SOURCE, 'late-controller.txt')
            final = result['interpretation']
            assert result['source_complete'] is True
            assert any(item['kind'] == 'INSTANCE' and 'ADAS Domain Controller' in item['name'] for item in final['components'])
            assert '1 konkret benannten Geräte' in final['proposed_task']
            assert 'Keine konkreten Geräte' not in final['proposed_task']
            assert final['assumptions'] == []
            assert len(final['open_questions']) == 2
            assert 'Anschlüsse' in final['open_questions'][1]
            assert 'Sensorik (Radar, Kamera)' in final['open_questions'][0]
            assert 'Welche Controller' not in final['open_questions'][0]
            assert 'R0001' not in json.dumps(final, ensure_ascii=False)
        finally:
            await reasoner.client.aclose()
    asyncio.run(run())
    assert len(observed) > 1


def test_global_review_preserves_unknown_interfaces_and_robot_device_categories():
    from backend.nis.agent.orchestration.project_intake import compose_document_proposal
    late = interpretation()
    late['components'] = [
        {'name': 'Robot Controller (RC)', 'kind': 'INSTANCE', 'role': 'CONTROLLER', 'quantity': 1,
         'source_quote': 'Robot Controller (RC)'},
        {'name': 'Greifer (elektrisch, pneumatisch)', 'kind': 'CATEGORY', 'role': 'ACTUATOR', 'quantity': None,
         'source_quote': 'Greifer (elektrisch, pneumatisch)'},
        {'name': 'Greifen', 'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None, 'source_quote': 'Greifen'},
    ]
    late['technologies'] = [{'name': 'XYZ-Link', 'kind': 'UNRESOLVED', 'source_quote': 'XYZ-Link'}]
    early = {**interpretation(), 'components': [], 'technologies': [],
             'proposed_task': 'Keine Geräte vorhanden.', 'open_questions': ['Welche Controller gibt es?']}
    result = compose_document_proposal([early, late])
    assert result['components'] == late['components']
    assert result['technologies'] == late['technologies']
    assert any('Greifer (elektrisch, pneumatisch)' in question for question in result['open_questions'])
    assert any('XYZ-Link' in question for question in result['open_questions'])
    assert 'logischen Funktionen' in result['proposed_task']
    assert 'Keine Geräte' not in result['proposed_task']
    assert result['assumptions'] == []


def test_full_vehicle_fixture_fits_reference_context_without_truncation():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[2] / 'frontend/e2e/fixtures/document-intake-vehicle.txt').read_bytes().decode('utf-8')
    observed = []
    async def run():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()
        def transport(request):
            if request.url.path == '/api/show':
                return httpx.Response(200, json={'details': {'family': 'qwen35'}, 'model_info': {'general.parameter_count': 27000000000}})
            observed.append(json.loads(request.content))
            raise RuntimeError('budget probe; no inference')
        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        try:
            with pytest.raises(RuntimeError, match='budget probe'):
                await reasoner.interpret_document(source, 'Fahrzeug komplett.txt')
        finally:
            await reasoner.client.aclose()
    asyncio.run(run())
    assert len(source) == 19088
    assert len(observed) == 1  # Reaching inference proves all complete windows fit.
    payload = observed[0]
    lines = json.loads(payload['messages'][1]['content'])['source_lines']
    assert isinstance(lines, dict)
    assert source.startswith(''.join(lines.values()))
    assert len(json.dumps(payload['messages'], ensure_ascii=False).encode()) + 4096 + 1800 <= payload['options']['num_ctx']


@pytest.mark.parametrize('failed_section', [2, 10])
def test_a_failed_later_segment_cannot_return_complete_source_success(failed_section):
    calls = []
    async def run():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()
        def transport(request):
            if request.url.path == '/api/show':
                return httpx.Response(200, json={'details': {'family': 'qwen35'}, 'model_info': {'general.parameter_count': 27000000000}})
            calls.append(json.loads(request.content))
            value = {**interpretation(), 'components': [], 'technologies': [], 'open_questions': []}
            if len(calls) >= failed_section:
                value['components'] = interpretation()['components']
            return httpx.Response(200, json={'message': {'content': json.dumps(model_wire_response(value, calls[-1]))}})
        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        try:
            with pytest.raises(ValueError, match=f'Abschnitt {failed_section}'):
                await reasoner.interpret_document('Hinweis. ' * (700 * failed_section), 'late-failure.txt')
        finally:
            await reasoner.client.aclose()
    asyncio.run(run())
    assert len(calls) == failed_section + 1


def test_bounded_local_repair_uses_validation_feedback_and_original_source():
    observed = []
    async def run():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()
        def transport(request):
            if request.url.path == '/api/show':
                return httpx.Response(200, json={'details': {'family': 'qwen35'}, 'model_info': {'general.parameter_count': 27000000000}})
            observed.append(json.loads(request.content))
            value = interpretation()
            if len(observed) == 1:
                value['technologies'] = []
            return httpx.Response(200, json={'message': {'content': json.dumps(model_wire_response(value, observed[-1]))}})
        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        try:
            result = await reasoner.interpret_document(SOURCE, 'repair.txt')
            assert result['source_complete'] is True
            assert result['interpretation']['technologies'][0]['kind'] == 'DEVICE_ALIAS'
        finally:
            await reasoner.client.aclose()
    asyncio.run(run())
    assert len(observed) == 2
    feedback = json.loads(observed[1]['messages'][1]['content'])
    assert ''.join(feedback['source_lines'].values()) == SOURCE
    assert 'DEVICE_ALIAS' in feedback['validation_feedback']


def test_an_actual_adc_input_is_not_hidden_by_a_same_named_controller():
    data = interpretation()
    data['technologies'].append({'name': 'ADC', 'kind': 'TRANSPORT', 'source_quote': 'Anschluss: ADC Eingang'})
    assert validate_document_interpretation(data, SOURCE)['technologies'][1]['kind'] == 'TRANSPORT'


def test_unicode_hyphen_transport_labels_preserve_the_original_source_quote():
    data = interpretation()
    quote = 'Kommunikationsnetzwerke (CAN, CAN‑FD, Ethernet, LIN)'
    data['technologies'].extend({'name': name, 'kind': 'TRANSPORT', 'source_quote': quote} for name in ['CAN', 'Ethernet', 'LIN', 'CAN-FD'])
    result = validate_document_interpretation(data, SOURCE + '\r\n' + quote)
    assert result['technologies'][-1]['source_quote'] == quote


@pytest.mark.parametrize('controller', ['ADAS Controller', 'Steuergerät', 'SPS'])
def test_requirement_ids_and_controller_subjects_do_not_create_physical_adc_or_lin(controller):
    from backend.nis.agent.orchestration.project_intake import DocumentInterpretation, document_output_schema, document_technology_grounding, document_device_aliases
    heading = controller + ' (ADC)'
    requirement = 'REQ‑ADC‑01: ADC MUSS Sensorfusion ausführen.\nREQ‑LIN‑14: Das Diagramm MUSS verständlich sein.'
    source = heading + '\n' + requirement
    choices = document_technology_grounding(document_output_schema(source, DocumentInterpretation.model_json_schema()))
    assert choices['registered_transports'] == {}
    assert choices['device_aliases'] == {'ADC': ['R0001']}
    fragment_choices = document_technology_grounding(document_output_schema(requirement, DocumentInterpretation.model_json_schema(), context_aliases=document_device_aliases(source)))
    assert fragment_choices['registered_transports'] == {}
    source += '\nAnschluss: ADC Eingang'
    choices = document_technology_grounding(document_output_schema(source, DocumentInterpretation.model_json_schema()))
    assert choices['registered_transports'] == {'adc': ['R0004']}


def test_nonliteral_quote_is_rejected_with_original_punctuation_and_all_missing_aliases():
    data = interpretation()
    quote = 'Zentrale Domain‑Controller (Powertrain, Chassis)'
    data['components'].append({'name': 'Domain-Controller', 'kind': 'CATEGORY', 'role': 'CONTROLLER',
        'quantity': None, 'source_quote': quote.replace('‑', '-')})
    data['technologies'] = []
    with pytest.raises(ValueError) as failure:
        validate_document_interpretation(data, SOURCE + '\n' + quote)
    feedback = str(failure.value)
    assert 'Quellenzitat ist nicht' in feedback
    assert quote in feedback
    assert 'DEVICE_ALIAS' in feedback and 'ADC' in feedback


def test_ambiguous_punctuation_alignment_does_not_offer_a_fabricated_original_quote():
    data = interpretation()
    quote = 'Domain-Controller Gruppe'
    data['components'].append({'name': 'Domain-Controller', 'kind': 'CATEGORY', 'role': 'CONTROLLER',
        'quantity': None, 'source_quote': quote})
    with pytest.raises(ValueError) as failure:
        validate_document_interpretation(data, SOURCE + '\nDomain‑Controller Gruppe\nDomain–Controller Gruppe')
    assert 'Wortgetreue Originalzitate' not in str(failure.value)


def test_one_correction_receives_all_unsupported_transport_names_without_family_fallback():
    data = interpretation()
    for name in ('Bluetooth', 'Mobilfunk'):
        data['technologies'].append({'name': name, 'kind': 'TRANSPORT', 'source_quote': name})
    with pytest.raises(ValueError, match='Bluetooth, Mobilfunk'):
        validate_document_interpretation(data, SOURCE + '\nBluetooth\nMobilfunk')


def test_registered_identity_can_cite_its_exact_source_alias_without_losing_bus_variant():
    data = interpretation()
    quote = 'Chassis‑CAN/CAN‑FD'
    data['technologies'].append({'name': 'CAN', 'kind': 'TRANSPORT', 'source_quote': quote})
    data['technologies'].append({'name': 'can_fd', 'kind': 'TRANSPORT', 'source_quote': quote})
    assert validate_document_interpretation(data, SOURCE + '\n' + quote)['technologies'][-1]['name'] == 'can_fd'
    data['technologies'][-1]['source_quote'] = 'CAN'
    with pytest.raises(ValueError, match='nicht belegt'):
        validate_document_interpretation(data, SOURCE + '\nCAN')


def test_compound_transport_descriptions_do_not_collapse_an_explicit_bus_variant():
    data = interpretation()
    data['technologies'].append({'name': 'CAN-FD', 'kind': 'TRANSPORT', 'source_quote': 'CAN-FD'})
    for name, quote in [('ethernet', 'Ethernet‑Backbone'), ('LIN', 'LIN-Cluster'), ('CAN', 'CAN-Controller')]:
        data['technologies'].append({'name': name, 'kind': 'TRANSPORT', 'source_quote': quote})
    source = SOURCE + '\nEthernet‑Backbone\nLIN-Cluster\nCAN-Controller\nCAN-FD'
    assert validate_document_interpretation(data, source)['technologies'][-1]['name'] == 'CAN'
    data['technologies'][-1]['source_quote'] = 'CAN-FD'
    with pytest.raises(ValueError, match='nicht belegt'):
        validate_document_interpretation(data, source)


def test_model_schema_cannot_invent_a_transport_variant_missing_from_original():
    from backend.nis.agent.orchestration.project_intake import DocumentInterpretation, document_output_schema
    source = 'Diagnosezugänge (UDS, OBD)\r\nCAN‑FD\r\nConnectivity (Bluetooth, Mobilfunk)'
    schema = document_output_schema(source, DocumentInterpretation.model_json_schema())
    branches = schema['$defs']['DocumentTechnology']['oneOf']
    labels = {name for branch in branches for name in branch['properties']['name']['enum']}
    assert 'OBD' in labels and 'Bluetooth' in labels and 'Mobilfunk' in labels
    assert 'uds' in labels and 'can_fd' in labels
    assert 'obd2' not in labels and 'can' not in labels
    from jsonschema import validate, ValidationError
    data = {**interpretation(), 'components': [], 'technologies': [{'name': 'obd2', 'kind': 'TRANSPORT', 'source_ref': 'R0001'}]}
    with pytest.raises(ValidationError):
        validate(data, schema)
    data['technologies'][0].update(name='OBD', kind='UNRESOLVED')
    validate(data, schema)
    data['technologies'][0].update(name='OBD', kind='TRANSPORT')
    with pytest.raises(ValidationError):
        validate(data, schema)
    data['technologies'][0].update(name='Mobilfunk', kind='UNRESOLVED', source_ref='R0001')
    with pytest.raises(ValidationError):
        validate(data, schema)
    data['technologies'][0]['source_ref'] = 'R0003'
    validate(data, schema)


@pytest.mark.parametrize('prefix', ['', 'Größere Kommunikationsräume: '])
def test_registered_transport_grammar_accepts_literal_can_case_and_excludes_unmentioned_aliases(prefix):
    from backend.nis.agent.orchestration.project_intake import DocumentInterpretation, document_output_schema
    from jsonschema import validate, ValidationError
    source = prefix + 'Kommunikationsnetzwerke (CAN, CAN‑FD, Ethernet, LIN)'
    schema = document_output_schema(source, DocumentInterpretation.model_json_schema())
    data = {**interpretation(), 'components': [], 'technologies': []}
    for name in ['CAN', 'can', 'CAN‑FD', 'can_fd', 'Ethernet', 'LIN']:
        data['technologies'] = [{'name': name, 'kind': 'TRANSPORT', 'source_ref': 'R0001'}]
        validate(data, schema)
    for name in ['CAN 2.0A/B', 'automotive_ethernet', 'CANFD']:
        data['technologies'][0]['name'] = name
        with pytest.raises(ValidationError):
            validate(data, schema)


def test_embedded_ip_in_someip_is_not_a_separately_declared_ip_transport():
    from backend.nis.agent.orchestration.project_intake import document_registered_transport_citation, document_output_schema, document_technology_grounding, DocumentInterpretation
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    assert not document_registered_transport_citation('ip', 'Middleware (SOME/IP, DDS)')
    assert document_registered_transport_citation('ip', 'Middleware SOME/IP über IP')
    source = 'Middleware (SOME/IP, DDS)'
    choices = document_technology_grounding(document_output_schema(source, DocumentInterpretation.model_json_schema()))
    assert 'ip' not in choices['registered_transports']
    assert DEFAULT_TECHNOLOGY_REGISTRY.normalize_id('SOME/IP') in choices['registered_transports']
    choices = document_technology_grounding(document_output_schema(source + '\nIP als eigenständige Schicht', DocumentInterpretation.model_json_schema()))
    assert choices['registered_transports']['ip'] == ['R0002']


def test_requirement_subject_is_not_an_additional_controller_instance_in_model_grammar():
    from backend.nis.agent.orchestration.project_intake import DocumentInterpretation, document_output_schema
    from jsonschema import validate, ValidationError
    source = 'REQ‑ADC‑02: ADC MUSS Objektliste erzeugen.\n2.4 Body Domain Controller (BDC)'
    schema = document_output_schema(source, DocumentInterpretation.model_json_schema(), context_aliases={'ADC', 'BDC'})
    data = {**interpretation(), 'technologies': [], 'components': [
        {'source_ref': 'R0001', 'kind': 'REQUIREMENT', 'role': 'OTHER', 'quantity': None}]}
    validate(data, schema)
    data['components'][0].update(kind='INSTANCE', role='CONTROLLER', quantity=1)
    with pytest.raises(ValidationError):
        validate(data, schema)
    data['components'][0]['source_ref'] = 'R0002'
    validate(data, schema)


def test_controller_alias_without_its_named_instance_is_not_complete_document_interpretation():
    data = interpretation()
    data['components'] = [item for item in data['components'] if item['role'] != 'CONTROLLER']
    with pytest.raises(ValueError, match='eigene.*Deklaration|eigenen Deklaration'):
        validate_document_interpretation(data, SOURCE)


def test_source_references_couple_label_and_quote_and_reject_free_fields():
    from backend.nis.agent.orchestration.project_intake import (
        DocumentInterpretation, document_output_schema, document_source_references, resolve_document_references)
    from jsonschema import validate, ValidationError
    source = SOURCE.replace('\n', '\r\n') + '\r\n\r\nSafety‑ und Security‑Mechanismen integriert\r\nEthernet‑Backbone\r\n'
    rows = document_source_references(source)
    assert ''.join(row['text'] for row in rows) == source
    schema = document_output_schema(source, DocumentInterpretation.model_json_schema())
    payload = {'messages': [{}, {'content': json.dumps({'source_lines': {row['source_ref']: row['text'] for row in rows}})}]}
    data = model_wire_response(interpretation(), payload)
    validate(data, schema)
    projected = resolve_document_references(data, rows)
    assert projected['components'][0]['name'] == 'ADAS Domain Controller (ADC)'
    assert projected['components'][0]['source_quote'] == '1.1 ADAS Domain Controller (ADC)'
    data['components'][0]['source_quote'] = 'Safety-Mechanismen'
    with pytest.raises(ValidationError):
        validate(data, schema)
    with pytest.raises(ValueError, match='keine freien Quellenfelder'):
        resolve_document_references(data, rows)
    data['components'][0].pop('source_quote')
    data['components'][0]['source_ref'] = 'UN\u2011ECE'
    with pytest.raises(ValidationError):
        validate(data, schema)
    with pytest.raises(ValueError, match='Ungültige Quellenreferenz'):
        resolve_document_references(data, rows)


def test_a_source_group_cannot_be_duplicated_as_additional_installed_devices():
    from backend.nis.agent.orchestration.project_intake import document_source_references, resolve_document_references
    rows = document_source_references('Aktorik (Bremsaktuator, Lenkaktuator)')
    data = {'components': [
        {'source_ref': 'R0001', 'kind': 'CATEGORY', 'role': 'ACTUATOR', 'quantity': None},
        {'source_ref': 'R0001', 'kind': 'INSTANCE', 'role': 'ACTUATOR', 'quantity': 1}], 'technologies': []}
    with pytest.raises(ValueError, match='nicht mehrfach'):
        resolve_document_references(data, rows)


def test_combined_registered_buses_require_individual_variants_without_base_substitution():
    data = interpretation()
    quote = 'Kommunikation: CAN/CAN‑FD'
    source = SOURCE + '\n' + quote
    data['technologies'].append({'name': 'CAN', 'kind': 'TRANSPORT', 'source_quote': quote})
    with pytest.raises(ValueError, match='can_fd'):
        validate_document_interpretation(data, source)
    data['technologies'].append({'name': 'can_fd', 'kind': 'TRANSPORT', 'source_quote': quote})
    assert validate_document_interpretation(data, source)['technologies'][-1]['name'] == 'can_fd'


def test_known_controller_role_and_every_unquantified_type_group_must_be_classified():
    data = interpretation()
    data['components'][0]['role'] = 'OTHER'
    with pytest.raises(ValueError, match='role CONTROLLER'):
        validate_document_interpretation(data, SOURCE)
    data = interpretation()
    with pytest.raises(ValueError, match='Aktorik'):
        validate_document_interpretation(data, SOURCE + '\nAktorik (Bremsaktuator, Lenkaktuator)')


def test_missing_explicit_controller_alias_is_not_a_complete_semantic_assessment():
    data = interpretation()
    data['technologies'] = []
    with pytest.raises(ValueError, match='DEVICE_ALIAS'):
        validate_document_interpretation(data, SOURCE)


def test_local_inference_contract_uses_main_qwen_complete_source_and_no_tools():
    observed = []
    async def run():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()
        def transport(request):
            payload = json.loads(request.content)
            if request.url.path == '/api/show':
                return httpx.Response(200, json={'details': {'family': 'qwen35'}, 'model_info': {'general.parameter_count': 27000000000}})
            observed.append(payload)
            assert request.url.host in {'127.0.0.1', 'localhost'}
            return httpx.Response(200, json={'message': {'content': json.dumps(model_wire_response(interpretation(), payload))}})
        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        try:
            result = await reasoner.interpret_document(SOURCE, 'requirements.txt')
            assert result['source_sha256'] == hashlib.sha256(SOURCE.encode()).hexdigest()
            assert result['source_complete'] is True
            assert result['canonical_writes'] is False
            assert result['status'] == 'REVIEW_REQUIRED'
        finally:
            await reasoner.client.aclose()
    asyncio.run(run())
    assert observed[0]['model'] == 'qwen3.8:27b'
    assert SOURCE == ''.join(json.loads(observed[0]['messages'][1]['content'])['source_lines'].values())
    assert 'tools' not in observed[0]
    assert observed[0]['stream'] is False
    assert observed[0]['format']['properties']['components']
    assert observed[0]['format']['properties']['components']['maxProperties'] == 24
    assert observed[0]['options']['num_predict'] == 3000
    assert observed[0]['format']['properties']['technologies']['maxProperties'] == 16
    assert observed[0]['format']['properties']['proposed_task']['maxLength'] == 500
    assert observed[0]['format']['properties']['assumptions']['items']['maxLength'] == 200


def test_context_overflow_is_explicit_and_never_sends_a_truncated_document():
    async def run():
        reasoner = LocalEngineeringReasoner()
        reasoner.context_tokens = 100
        await reasoner.client.aclose()
        def forbidden(_):
            pytest.fail('Oversize source must not be sent or truncated.')
        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(forbidden))
        try:
            with pytest.raises(ValueError, match='nicht gekürzt'):
                await reasoner.interpret_document(SOURCE, 'context-overflow.txt')
        finally:
            await reasoner.client.aclose()
    asyncio.run(run())


def test_large_document_processes_every_section_and_preserves_complete_fact_union():
    from backend.nis.engineering.goal_execution.progress import sink
    source = ''.join(f'Controller (U{i:03d})\r\n' + 'Hinweis ohne zusätzliche Angaben. ' * 40 + '\r\nÄußere Quelle 😀\r\n' for i in range(70))
    observed, progress = [], []

    async def run():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()

        def transport(request):
            if request.url.path == '/api/show':
                return httpx.Response(200, json={'details': {'family': 'qwen35'}, 'model_info': {'general.parameter_count': 27000000000}})
            payload = json.loads(request.content)
            observed.append(payload)
            lines = json.loads(payload['messages'][1]['content'])['source_lines']
            declarations = [line.strip() for line in lines.values() if line.startswith('Controller (')]
            value = {**interpretation(), 'components': [
                {'name': line, 'kind': 'INSTANCE', 'role': 'CONTROLLER', 'quantity': 1, 'source_quote': line}
                for line in declarations], 'technologies': [
                {'name': line.split('(')[1][:-1], 'kind': 'DEVICE_ALIAS', 'source_quote': line}
                for line in declarations], 'open_questions': []}
            return httpx.Response(200, json={'message': {'content': json.dumps(model_wire_response(value, payload))}})

        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        token = sink.set(progress.append)
        try:
            result = await reasoner.interpret_document(source, 'large-robotics.md')
            assert result['source_complete'] is True and result['canonical_writes'] is False
            assert result['approval_required'] is True and result['status'] == 'REVIEW_REQUIRED'
            assert result['source_chars'] == len(source) > 80000
            assert result['source_sha256'] == hashlib.sha256(source.encode()).hexdigest()
            assert len(result['segments']) == len(observed) > 8
            assert len(result['interpretation']['components']) == 70
            assert {t['name'] for t in result['interpretation']['technologies']} == {f'U{i:03d}' for i in range(70)}
            assert result['segments'][0]['start'] == 0 and result['segments'][-1]['end'] == len(source)
            for part, payload in zip(result['segments'], observed):
                original = source[part['start']:part['end']]
                assert part['sha256'] == hashlib.sha256(original.encode()).hexdigest()
                assert ''.join(json.loads(payload['messages'][1]['content'])['source_lines'].values()) == original
                assert len(json.dumps(payload['messages'], ensure_ascii=False).encode()) + 4096 + 1800 <= payload['options']['num_ctx']
                assert payload['format']['properties']['components']['maxProperties'] == 24
            assert all(a['end'] == b['start'] for a, b in zip(result['segments'], result['segments'][1:]))
        finally:
            sink.reset(token)
            await reasoner.client.aclose()

    asyncio.run(run())
    sections = [p['metadata'] for p in progress if p.get('metadata', {}).get('source') == 'document_intake']
    assert [p['completed'] for p in sections] == list(range(len(observed)))
    assert all(p['total'] == len(observed) for p in sections)


def test_aggregate_still_rejects_missing_late_evidence_and_invented_sources():
    data = {**interpretation(), 'components': interpretation()['components'] * 16}
    assert len(validate_document_interpretation(data, SOURCE, aggregate=True)['components']) == 64
    with pytest.raises(ValueError, match='Quellenangabe fehlt'):
        validate_document_interpretation(data, SOURCE + '\nFunktionen: Späte Endkontrolle.', aggregate=True)
    data['components'].append({'name': 'Erfunden', 'source_quote': 'Erfunden', 'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None})
    with pytest.raises(ValueError, match='Quellenzitat'):
        validate_document_interpretation(data, SOURCE, aggregate=True)


def test_document_source_limits_match_native_tool_and_reject_oversize_without_truncation():
    from backend.nis.agent.orchestration.project_intake import DOCUMENT_SOURCE_MAX_CHARS, DocumentIntakeRequest
    from backend.nis.agent.tools.services import TOOLS
    assert DocumentIntakeRequest(source='x' * DOCUMENT_SOURCE_MAX_CHARS).source.endswith('x')
    schema = TOOLS['interpret_project_document'].input_model.model_json_schema()
    assert schema['properties']['source']['maxLength'] == DOCUMENT_SOURCE_MAX_CHARS
    with pytest.raises(ValueError):
        DocumentIntakeRequest(source='x' * (DOCUMENT_SOURCE_MAX_CHARS + 1))


def test_failed_local_inference_has_no_cloud_or_deterministic_success_fallback():
    calls = []
    async def run():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()
        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: calls.append(str(request.url)) or httpx.Response(503)))
        try:
            with pytest.raises(RuntimeError, match='Lokaler KI-Dienst'):
                await reasoner.interpret_document(SOURCE, 'requirements.txt')
        finally:
            await reasoner.client.aclose()
    asyncio.run(run())
    assert len(calls) == 1


def test_cloud_models_behind_a_loopback_service_cannot_interpret_documents():
    calls = []
    async def run():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()
        def transport(request):
            calls.append(str(request.url))
            return httpx.Response(200, json={'remote_host': 'https://ollama.com',
                'details': {'family': 'qwen35'}, 'model_info': {'general.parameter_count': 27000000000}})
        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        try:
            with pytest.raises(ValueError, match='Cloud-Modelle'):
                await reasoner.interpret_document(SOURCE, 'requirements.txt')
        finally:
            await reasoner.client.aclose()
    asyncio.run(run())
    assert len(calls) == 1 and calls[0].endswith('/api/show')


def test_document_endpoint_requires_explicit_human_action(monkeypatch):
    from flask import Flask
    from backend.nis.agent.tools import api
    app = Flask(__name__)
    app.register_blueprint(api.agent_api, url_prefix='/agent')
    monkeypatch.setattr(api, 'execute', lambda *args, **kwargs: pytest.fail('No inference without human action'))
    assert app.test_client().post('/agent/document-intake', json={'source': SOURCE}).status_code == 403


def test_document_endpoint_accepts_large_unicode_json_and_rejects_oversize_without_leaking_slot(monkeypatch):
    from flask import Flask
    from threading import BoundedSemaphore
    from backend.nis.agent.tools import api
    from backend.nis.agent.api.tool_contract import ToolResult
    from backend.nis.agent.orchestration.project_intake import DOCUMENT_REQUEST_MAX_BYTES
    app = Flask(__name__)
    app.register_blueprint(api.agent_api, url_prefix='/agent')
    monkeypatch.setattr(api, '_slots', BoundedSemaphore(1))
    observed = []
    monkeypatch.setattr(api, 'execute', lambda authority, name, permission, arguments, handler:
                        observed.append(arguments) or ToolResult(data={'source_chars': len(arguments['source'])}))
    client = app.test_client()
    client.set_cookie(api.COOKIE, 'review-token')
    headers = {'X-Human-Review': 'confirmed', 'X-Review-CSRF': 'review-token', 'X-Project-ID': 'test-large-source'}
    assert client.post('/agent/document-intake', data=' ' * (DOCUMENT_REQUEST_MAX_BYTES + 1),
                       content_type='application/json', headers=headers).status_code == 413
    source = '😀' * 100000
    body = json.dumps({'source': source})
    assert len(body) > 512 * 1024
    response = client.post('/agent/document-intake', data=body, content_type='application/json', headers=headers)
    assert response.status_code == 200
    assert observed == [{'source': source}]
    assert response.json['data']['source_chars'] == 100000
    assert api._slots.acquire(blocking=False)
    api._slots.release()


def test_document_stream_reports_progress_and_preserves_failed_tool_result(monkeypatch):
    from flask import Flask
    from backend.nis.agent.tools import api
    from backend.nis.agent.api.tool_contract import ToolResult, ToolStatus, Permission
    app = Flask(__name__)
    app.register_blueprint(api.agent_api, url_prefix='/agent')
    observed = []
    def execute(authority, name, permission, arguments, handler):
        observed.append((authority, name, permission, arguments))
        authority.progress_callback({'type': 'PROGRESS', 'text': 'Abschnitt 2 von 4'})
        return ToolResult(success=False, status=ToolStatus.INVALID_INPUT, findings=[{'message': 'Quellenzitat fehlt.'}])
    monkeypatch.setattr(api, 'execute', execute)
    client = app.test_client()
    client.set_cookie(api.COOKIE, 'review-token')
    response = client.post('/agent/document-intake', json={'source': SOURCE}, headers={
        'Accept': 'application/x-ndjson', 'X-Human-Review': 'confirmed', 'X-Review-CSRF': 'review-token',
        'X-Project-ID': 'test-native-document'}, buffered=True)
    events = [json.loads(line) for line in response.text.splitlines()]
    assert response.mimetype == 'application/x-ndjson'
    assert any(event.get('text') == 'Abschnitt 2 von 4' for event in events)
    assert events[-1]['type'] == 'RESULT' and events[-1]['result']['success'] is False
    assert observed[0][0].project_id == 'test-native-document'
    assert observed[0][1:3] == ('interpret_project_document', Permission.GENERATE_PROPOSAL)
    assert api._slots.acquire(blocking=False)
    api._slots.release()


def test_mcp_and_http_share_the_registered_native_document_tool():
    from backend.nis.agent.tools.services import TOOLS
    from backend.nis.agent.orchestration.project_intake import interpret_project_document
    from backend.nis.agent.orchestration.tool_selection import select_tools
    assert TOOLS['interpret_project_document'].handler is interpret_project_document
    selected = select_tools('Prüfe diese Dokumentdatei und schlage einen Entwurf vor.', [
        {'name': name} for name in TOOLS])
    assert any(tool['name'] == 'interpret_project_document' for tool in selected)


def test_native_document_mcp_budget_covers_local_sections_without_extending_other_tools(monkeypatch):
    from types import SimpleNamespace
    from backend.nis.agent.api.mcp_client import EngineeringMCPClient
    from backend.nis.agent.api.tool_contract import ToolResult
    monkeypatch.setenv('LOCAL_AI_TIMEOUT_SECONDS', '600')
    observed = []
    class Transport:
        async def call_tool(self, name, arguments, **options):
            observed.append((name, options))
            return SimpleNamespace(structured_content=ToolResult(data={}).model_dump(mode='json'))
    async def run():
        client = object.__new__(EngineeringMCPClient)
        client.client = Transport()
        assert (await client.call('interpret_project_document', {'source': SOURCE})).success
        assert (await client.call('calculate_message_size', {'payload_bytes': 1})).success
    asyncio.run(run())
    assert observed == [('interpret_project_document', {'read_timeout_seconds': 9600}), ('calculate_message_size', {})]



@pytest.mark.parametrize('statement', [
    'Sensor- und Aktorfehler erkennen und behandeln.',
    'Das System verarbeitet kontinuierlich Sensordaten und steuert Aktuatoren.',
    'Der Gebäuderegler überwacht die Sensoren und steuert Aktoren.',
    'The robot processes sensor readings and controls actuators.',
])
def test_action_statements_do_not_declare_installed_device_categories(statement):
    from backend.nis.agent.orchestration.project_intake import document_component_policy
    assert document_component_policy(statement) == {'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None}


def test_numbered_architecture_headings_do_not_become_controller_inventory():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    units = document_component_sources(document_source_references('2. Domain-Controller-Design\nController (PDC)'))
    assert len(units) == 1
    assert units[0]['policy'] == {'kind': 'INSTANCE', 'role': 'CONTROLLER', 'quantity': 1}


def test_normative_list_scope_preserves_unnumbered_requirements_across_windows():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    prefix = '5. Anforderungen\nDas System muss\n'
    source = '\nEnergieversorgung für alle Subsysteme sicherstellen.\nSystemzustände überwachen und protokollieren.\n6. Hardware\nRaumcontroller'
    units = document_component_sources(document_source_references(source), scope_prefix=prefix)
    requirements = [unit for unit in units if unit['policy'] and unit['policy']['kind'] == 'REQUIREMENT']
    assert requirements and all(unit['required'] for unit in requirements)
    assert all(any(line in unit['text'] for unit in requirements) for line in source.splitlines()[1:3])
    assert units[-1]['policy']['kind'] == 'CATEGORY'
    assert units[-1]['policy']['role'] == 'CONTROLLER'


def test_standalone_normative_lead_ends_at_a_new_hardware_section():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    units = document_component_sources(document_source_references('Das System muss\nSystemzustände überwachen.\n2. Hardware\nRaumcontroller'))
    assert units[0]['policy']['kind'] == 'REQUIREMENT'
    assert units[-1]['policy'] == {'kind': 'CATEGORY', 'role': 'CONTROLLER', 'quantity': None}


@pytest.mark.parametrize('statement', [
    'NIS soll die Sensoren und Aktoren mit dem Controller fachlich verbinden.',
    'Der Gebäuderegler soll Sensordaten auswerten.',
    'Die Controller sollen die Aktoren steuern.',
    'The robot should process sensor data and control actuators.',
])
def test_soft_normative_statements_are_requirements_not_additional_hardware(statement):
    from backend.nis.agent.orchestration.project_intake import document_component_policy
    assert document_component_policy(statement) == {'kind': 'REQUIREMENT', 'role': 'OTHER', 'quantity': None}


@pytest.mark.parametrize('lead', ['Das System soll', 'The system should'])
def test_soft_normative_list_lead_preserves_scoped_clauses(lead):
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    units = document_component_sources(document_source_references(f'{lead}\nSensoren überwachen.\n2. Hardware\nRaumcontroller'))
    assert units[0]['policy']['kind'] == 'REQUIREMENT'
    assert units[-1]['policy']['kind'] == 'CATEGORY'


def test_functional_partner_aliases_and_direct_sensor_links_are_not_false_protocols():
    from backend.nis.agent.orchestration.project_intake import document_declared_unknown_transports, document_source_references
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    source = 'Chassis Controller (CDC)\nSchnittstellen:\nCDC (Lenk-/Bremsanforderungen)\nDirekte Sensorlinks (GMSL, FPD-Link, GigE)\nEthernet möglich'
    unknown = document_declared_unknown_transports(document_source_references(source), DEFAULT_TECHNOLOGY_REGISTRY.profiles())
    assert set(unknown) == {'GMSL', 'FPD-Link', 'GigE'}


def test_unicode_transport_spelling_has_one_registry_identity_and_merged_fact():
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    from backend.nis.agent.orchestration.project_intake import compose_document_proposal
    assert {DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(name) for name in ['CAN-FD', 'CAN‑FD', 'can_fd']} == {'can_fd'}
    parts = [{'components': [], 'technologies': [{'name': name, 'kind': 'TRANSPORT', 'source_quote': name}]} for name in ['CAN‑FD', 'can_fd']]
    assert len(compose_document_proposal(parts)['technologies']) == 1


def test_robotics_markdown_preserves_all_ten_function_scopes_and_110_requirements_without_test_hardware():
    import re
    from pathlib import Path
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    fixture = Path(__file__).resolve().parents[2] / 'frontend/e2e/fixtures/document-intake-industrial-robotics.md'
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == '8fc201a55e8b0afeb7b708ac70abd0c72a7b25eb17d90fceca71d80a291f3cef'
    source = fixture.read_text(encoding='utf-8')
    units = document_component_sources(document_source_references(source))
    assert all(unit['text'] in source for unit in units)
    assert not any('TC-' in unit['text'] or unit['text'].startswith('|') for unit in units)
    functions = [unit for unit in units if unit['source_context'][-1:] == ['4. Funktionsbeschreibung']]
    assert len(functions) == 10
    assert all(unit['policy'] == {'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None} and unit['required'] for unit in functions)
    requirement_ids = set(re.findall(r'REQ-\d{3}-[A-Z]+-\d{3}', '\n'.join(unit['text'] for unit in units if unit['policy'] and unit['policy']['kind'] == 'REQUIREMENT')))
    assert requirement_ids == set(re.findall(r'REQ-\d{3}-[A-Z]+-\d{3}', source))
    assert len(requirement_ids) == 110
    names = [unit['text'] for unit in units]
    assert 'Teach Pendant' in names and 'Endeffektor' in names
    encoders = [unit for unit in units if unit['text'] == 'Encoder']
    assert len(encoders) >= 2 and len({tuple(unit['source_context']) for unit in encoders}) == len(encoders)


def test_markdown_test_sections_override_hardware_words_and_normative_language_across_windows():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    prefix = '# Building\n## Verification and test cases\n'
    source = '- TC-BLD-01: Sensor drift must be detected.\n## Architecture\nRoomcontroller\n## Functions\nSensor fault handling\n## Requirements\nREQ-BLD-01: The room controller shall report faults.'
    units = document_component_sources(document_source_references(source), scope_prefix=prefix)
    assert not any('TC-BLD' in unit['text'] for unit in units)
    assert [unit['policy']['kind'] for unit in units] == ['CATEGORY', 'FUNCTION', 'REQUIREMENT']
    assert units[1]['source_context'] == ['Building', 'Functions']


@pytest.mark.parametrize('section', ['Safety', 'Security', 'Sicherheit', 'Systemkontext', 'Operating modes'])
def test_explicit_safety_and_context_requirements_survive_without_fault_scenario_hardware(section):
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    source = f'# {section}\nREQ-SAFE-01: Das System MUSS Sensorausfälle erkennen.\n'
    units = document_component_sources(document_source_references(source))
    assert len(units) == 1
    assert units[0]['policy'] == {'kind': 'REQUIREMENT', 'role': 'OTHER', 'quantity': None}
    assert units[0]['text'] == 'REQ-SAFE-01: Das System MUSS Sensorausfälle erkennen.'
    assert units[0]['source_context'] == [section]


def test_a_safety_plc_in_architecture_is_a_controller_and_not_a_safety_section():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    units = document_component_sources(document_source_references('# Robot\n## Architecture\nSafety-PLC\n'))
    assert len(units) == 1
    assert units[0]['policy'] == {'kind': 'CATEGORY', 'role': 'CONTROLLER', 'quantity': None}


def _reviewed_room_document():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references, resolve_document_references
    source = '# Building\n## Architecture\nRaumcontroller\n## Functions\nRaumtemperatur regeln.\n## Requirements\nREQ-BLD-01: The room controller shall report faults.'
    rows = document_source_references(source)
    units = document_component_sources(rows)
    facts = resolve_document_references({'components': [{'source_ref': unit['source_ref'], **unit['policy']} for unit in units], 'technologies': []}, rows)['components']
    envelope = {'source_sha256': hashlib.sha256(source.encode()).hexdigest(), 'source_chars': len(source),
                'source_name': 'building.md', 'source_text': source, 'facts': facts, 'technologies': [], 'questions': [], 'answers': []}
    return source, envelope


def test_reviewed_document_handoff_retains_every_typed_fact_in_proposal_source_evidence():
    from backend.nis.agent.orchestration.project_intake import reviewed_document_evidence
    source, envelope = _reviewed_room_document()
    evidence = reviewed_document_evidence(source + '\n- Dokument-Geräte: ' + json.dumps(envelope))
    assert evidence['components'] == envelope['facts']
    assert {fact['kind'] for fact in evidence['components']} == {'CATEGORY', 'FUNCTION', 'REQUIREMENT'}
    assert evidence['source_sha256'] == envelope['source_sha256']
    assert evidence['canonical_writes'] is False and evidence['approval_required'] is True


@pytest.mark.parametrize('change', ['hash', 'omit_requirement', 'context', 'hardware_function'])
def test_reviewed_document_handoff_rejects_changed_source_incomplete_facts_and_wrong_context(change):
    from backend.nis.agent.orchestration.project_intake import reviewed_document_evidence
    source, envelope = _reviewed_room_document()
    if change == 'hash':
        envelope['source_sha256'] = '0' * 64
    elif change == 'omit_requirement':
        envelope['facts'] = [fact for fact in envelope['facts'] if fact['kind'] != 'REQUIREMENT']
    elif change == 'context':
        envelope['facts'][0]['source_context'] = ['An unrelated building']
    else:
        envelope['facts'][1].update(kind='CATEGORY', role='CONTROLLER')
    with pytest.raises(ValueError):
        reviewed_document_evidence(source + '\n- Dokument-Geräte: ' + json.dumps(envelope))


def test_same_component_name_in_different_source_contexts_is_not_deduplicated():
    from backend.nis.agent.orchestration.project_intake import compose_document_proposal
    component = {'name': 'Encoder', 'kind': 'CATEGORY', 'role': 'SENSOR', 'quantity': None, 'source_quote': 'Encoder'}
    parts = [{'components': [{**component, 'source_context': ['Robot A', 'Architecture']}], 'technologies': []},
             {'components': [{**component, 'source_context': ['Robot B', 'Architecture']}], 'technologies': []}]
    assert len(compose_document_proposal(parts)['components']) == 2


def test_markdown_context_validation_survives_different_normative_grouping_at_window_boundaries():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references, resolve_document_references, compose_document_proposal
    lines = ['# Building\n', '## Requirements\n', *[f'REQ-BLD-{index:03d}: The controller shall retain this original requirement and its complete source text.\n' for index in range(12)]]
    source = ''.join(lines)
    first = ''.join(lines[:5])
    pieces = [first, source[len(first):]]
    parts, prefix = [], ''
    for piece in pieces:
        rows = document_source_references(piece)
        units = document_component_sources(rows, scope_prefix=prefix)
        parts.append(resolve_document_references({'components': [{'source_ref': unit['source_ref'], **unit['policy']} for unit in units], 'technologies': []}, rows, scope_prefix=prefix))
        prefix += piece
    combined = compose_document_proposal(parts)
    accepted = validate_document_interpretation(combined, source, aggregate=True)
    assert all(fact['source_context'] == ['Building', 'Requirements'] for fact in accepted['components'])
    assert all(f'REQ-BLD-{index:03d}' in '\n'.join(fact['source_quote'] for fact in accepted['components']) for index in range(12))



def test_numeric_plain_text_profiles_preserve_equal_hardware_and_function_facts():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references, resolve_document_references, compose_document_proposal
    source = '1. Anlage Nord\n1.1 Architektur\nController: SPS\n1.2 Funktionen\nRegelung\n2. Anlage Süd\n2.1 Architektur\nController: SPS\n2.2 Funktionen\nRegelung\n'
    rows = document_source_references(source)
    units = document_component_sources(rows)
    facts = resolve_document_references({'components': [{'source_ref': unit['source_ref'], **unit['policy']} for unit in units], 'technologies': []}, rows)['components']
    assert [fact['source_context'] for fact in facts] == [
        ['1. Anlage Nord', '1.1 Architektur'], ['1. Anlage Nord', '1.2 Funktionen'],
        ['2. Anlage Süd', '2.1 Architektur'], ['2. Anlage Süd', '2.2 Funktionen']]
    combined = compose_document_proposal([{'components': [fact], 'technologies': []} for fact in facts])
    assert len(combined['components']) == 4
    assert len(validate_document_interpretation(combined, source, aggregate=True)['components']) == 4


def test_numeric_context_covers_declaring_heading_and_survives_window_prefix():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references, resolve_document_references
    source = '1. Architektur\n1.1 Hauptrechner\n1.1.1 Aufgaben\nBahnplanung\n'
    rows = document_source_references(source)
    units = document_component_sources(rows)
    facts = resolve_document_references({'components': [{'source_ref': unit['source_ref'], **unit['policy']} for unit in units], 'technologies': []}, rows)['components']
    data = {**interpretation(), 'components': facts, 'technologies': []}
    assert validate_document_interpretation(data, source)['components'] == facts
    prefix = '1. Anlage Nord\n1.1 Architektur\n'
    unit = document_component_sources(document_source_references('Controller: SPS\n'), scope_prefix=prefix)[0]
    assert unit['source_context'] == ['1. Anlage Nord', '1.1 Architektur']


def test_missing_numeric_context_is_derived_only_for_an_unambiguous_literal_quote():
    data = {**interpretation(), 'components': [{'name': 'SPS', 'source_quote': 'Controller: SPS', 'kind': 'CATEGORY', 'role': 'CONTROLLER', 'quantity': None}], 'technologies': []}
    source = '1. Anlage Nord\n1.1 Architektur\nController: SPS\n'
    result = validate_document_interpretation(data, source)
    assert result['components'][0]['source_context'] == ['1. Anlage Nord', '1.1 Architektur']
    with pytest.raises(ValueError, match='Abschnittskontext'):
        validate_document_interpretation(data, source + '2. Anlage Süd\n2.1 Architektur\nController: SPS\n')


def test_explicit_hardware_quantity_line_does_not_replace_the_numeric_profile_context():
    from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
    source = '1. Anlage Nord\n1.1 Architektur\n3 Sensoren\n'
    units = document_component_sources(document_source_references(source))
    assert units[0]['source_context'] == ['1. Anlage Nord', '1.1 Architektur']
    assert units[0]['policy']['quantity'] == 3
