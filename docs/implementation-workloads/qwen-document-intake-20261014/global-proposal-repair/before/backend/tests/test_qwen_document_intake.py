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
        ],
        'technologies': [{'name': 'ADC', 'kind': 'DEVICE_ALIAS', 'source_quote': '1.1 ADAS Domain Controller (ADC)'},
                         {'name': 'ADC', 'kind': 'TRANSPORT', 'source_quote': 'Anschluss: ADC Eingang'}],
        'proposed_task': 'ADAS-Verarbeitung mit Sensorik planen; Stückzahlen und Schnittstellen klären.',
        'assumptions': [], 'open_questions': ['Wie viele konkrete Radarsensoren?'],
    }


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


def test_a_failed_later_segment_cannot_return_complete_source_success():
    calls = []
    async def run():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()
        def transport(request):
            if request.url.path == '/api/show':
                return httpx.Response(200, json={'details': {'family': 'qwen35'}, 'model_info': {'general.parameter_count': 27000000000}})
            calls.append(json.loads(request.content))
            value = {**interpretation(), 'components': [], 'technologies': [], 'open_questions': []}
            if len(calls) >= 2:
                value['components'] = interpretation()['components']
            return httpx.Response(200, json={'message': {'content': json.dumps(model_wire_response(value, calls[-1]))}})
        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        try:
            with pytest.raises(ValueError, match='Abschnitt 2'):
                await reasoner.interpret_document('A' * 6500, 'two-segments.txt')
        finally:
            await reasoner.client.aclose()
    asyncio.run(run())
    assert len(calls) == 3


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
    assert observed[0]['format']['properties']['components']['maxItems'] == 8
    assert observed[0]['format']['properties']['technologies']['maxItems'] == 16
    assert observed[0]['format']['properties']['proposed_task']['maxLength'] == 500
    assert observed[0]['format']['properties']['assumptions']['items']['maxLength'] == 200


def test_context_overflow_is_explicit_and_never_sends_a_truncated_document():
    async def run():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()
        def forbidden(_):
            pytest.fail('Oversize source must not be sent or truncated.')
        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(forbidden))
        try:
            with pytest.raises(ValueError, match='nicht gekürzt'):
                await reasoner.interpret_document('x' * 79999, 'big.txt')
        finally:
            await reasoner.client.aclose()
    asyncio.run(run())


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
