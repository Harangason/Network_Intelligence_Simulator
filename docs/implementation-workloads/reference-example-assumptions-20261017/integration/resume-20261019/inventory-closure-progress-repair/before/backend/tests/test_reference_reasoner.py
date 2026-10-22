"""Mocked local-wire regressions, explicitly not a native model/E2E proof."""
import asyncio
from copy import deepcopy
import json

import httpx
import pytest

from backend.nis.agent.orchestration import project_intake as intake
from backend.nis.agent.orchestration.local_reasoner import (
    LocalEngineeringReasoner, _reference_context_window,
    _reference_merge_port_parameters, _reference_schema_for_stage, _reference_merge_inventory_devices,
)
from backend.tests.test_reference_design import fixture_request, fixture_design, wire


def complete_design(prepared):
    value = fixture_design(prepared)
    value['devices'][1]['quantity'] = 1
    for device in value['devices']:
        if device['kind'] in {'SENSOR', 'ACTUATOR'}:
            device['owner_device_id'] = 'C'
    value['ports'] = [{'id': 'P' + key, 'device_id': key, 'technology': 'can', 'role': 'LOCAL',
        'network_scope': 'local', 'parameters': {'bitrate_bps': 500000}, 'rationale': 'Unit scenario, not physical evidence'} for key in ('C', 'S', 'A')]
    temperature = {'length_bits': 8, 'data_type': 'unsigned', 'unit': 'degC', 'factor': 1,
                   'min_value': 0, 'max_value': 100, 'semantic': {'semantic_type': 'NUMERIC', 'meaning': 'Temperatur'}, 'data': {}}
    def communication(key, source, target, encoding, role):
        return {'id': key, 'producer_device_id': source, 'consumer_device_ids': [target],
            'source_port_id': 'P' + source, 'consumer_port_ids': ['P' + target],
            'scope': 'LOCAL_IO', 'role': role, 'signal_name': key, 'encoding': encoding,
            'transmission_mode': 'CYCLIC', 'cycle_ms': 50, 'rationale': 'Unit communication fixture'}
    value['communication'] = [communication('temperature', 'S', 'C', temperature, 'MEASUREMENT'),
        communication('request', 'A', 'C', wire(), 'FEEDBACK'),
        {**communication('response', 'C', 'A', wire(), 'COMMAND'), 'transmission_mode': 'ON_REQUEST',
         'min_interval_ms': 50, 'request_source': 'bus_message', 'request_communication_id': 'request', 'response_processing_ms': 0}]
    return value


def reasoner_with_transport(monkeypatch, *, family='qwen3', truncate=False, capture=None, timeout=False,
                            foreign_io=None, duplicate_port_ids=False, retry_foreign_port=False, omit_inventory_role=None,
                            request=None, design_factory=complete_design, never_complete_inventory_role=None):
    prepared = intake.prepare_reference_design(request or fixture_request())
    design = design_factory(prepared)
    observed = []
    monkeypatch.setenv('LOCAL_AI_CONTEXT_TOKENS', '131072')
    def handler(request):
        if request.url.path.endswith('/show'):
            return httpx.Response(200, json={'details': {'family': family}, 'model_info': {'general.parameter_count': 27000000000}})
        payload = json.loads(request.content)
        if capture is not None:
            capture.append(deepcopy(payload))
        if timeout:
            raise httpx.ReadTimeout('Unit provider deadline', request=request)
        content = json.loads(payload['messages'][1]['content'])
        observed.append(content)
        allowed = set(content['output_fields_for_this_stage'])
        candidate = {key: deepcopy(value) for key, value in design.items() if key in allowed}
        if content.get('inventory_target_for_this_stage'):
            target = content['inventory_target_for_this_stage']
            candidate['devices'] = [row for row in candidate['devices']
                if target['fact_id'] in row['source_fact_ids'] and row['kind'] != omit_inventory_role
                and (not target['member'] or row.get('source_member_bindings', {}).get(target['fact_id']) == target['member'])]
            if target['names']:
                candidate['devices'] = [row for row in candidate['devices'] if row['name'] in target['names']]
            existing = {row['id'] for row in content['current_candidate']['devices']}
            fresh = [row for row in candidate['devices'] if row['id'] not in existing]
            candidate['inventory_complete'] = len(fresh) <= 2 and prepared['facts'][target['fact_id']]['role'] != never_complete_inventory_role
            candidate['devices'] = (fresh or candidate['devices'])[:2]
        if content.get('port_ids_for_this_stage'):
            selected = set(content['port_ids_for_this_stage'])
            candidate['ports'] = [row for row in candidate['ports'] if row['id'] in selected]
        elif content.get('device_ids_for_this_stage') and allowed == {'ports'}:
            for row in candidate['ports']:
                row['parameters'] = {}
        if content.get('device_ids_for_this_stage'):
            selected = set(content['device_ids_for_this_stage'])
            for field in allowed:
                candidate[field] = [row for row in candidate[field] if row['device_id'] in selected]
            if foreign_io in allowed:
                row = deepcopy(candidate[foreign_io][0])
                row['device_id'] = 'not-selected'
                candidate[foreign_io].append(row)
            if duplicate_port_ids and allowed == {'ports'}:
                for row in candidate['ports']:
                    row['id'] = 'same-id-for-different-participants'
            if retry_foreign_port and allowed == {'ports'}:
                if len(payload['messages']) == 2:
                    candidate['ports'][0]['parameters'] = {'bitrate_bps': 500000}
                else:
                    candidate['ports'][0]['device_id'] = 'S'
        if content.get('function_fact_ids_for_this_stage'):
            selected = set(content['function_fact_ids_for_this_stage'])
            candidate['functions'] = [row for row in candidate['functions'] if row['source_fact_id'] in selected]
            candidate['functional_dependencies'] = [row for row in candidate.get('functional_dependencies', []) if row['producer_fact_id'] in selected]
        if allowed == {'communication'}:
            selected = set(content['producer_device_ids_for_this_stage'])
            candidate['communication'] = [row for row in candidate['communication'] if row['producer_device_id'] in selected]
        return httpx.Response(200, json={'message': {'content': json.dumps(candidate)}, 'done_reason': 'length' if truncate else 'stop',
                                       'prompt_eval_count': 500, 'eval_count': 500})
    instance = LocalEngineeringReasoner()
    asyncio.run(instance.client.aclose())
    instance.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return instance, prepared, observed


def test_local_request_ids_are_remapped_with_actual_communication_ids(monkeypatch):
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch)
    async def run():
        try:
            return await reasoner.plan_reference_design(prepared)
        finally:
            await reasoner.client.aclose()
    result = asyncio.run(run())
    by_name = {row['signal_name']: row for row in result['proposal']['communication']}
    assert by_name['response']['request_communication_id'] == by_name['request']['id']
    assert by_name['request']['id'] != 'request'
    assert all(row['id'].startswith('c') for row in by_name.values())
    batches = [row for row in observed if row['planning_stage'] == 'Fachliche Kommunikation']
    assert len(batches) >= 2
    assert any(row['known_communication'] for row in batches[1:])
    assert result['source_evidence']['source_text'] == prepared['source_evidence']['source_text']
    assert result['canonical_writes'] is False


def test_reference_planner_rejects_non_qwen_instead_of_changing_provider(monkeypatch):
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, family='llama')
    async def run():
        try:
            with pytest.raises(ValueError, match='lokal installiertes Qwen'):
                await reasoner.plan_reference_design(prepared)
        finally:
            await reasoner.client.aclose()
    asyncio.run(run())
    assert observed == []


def test_truncated_local_response_never_becomes_a_reviewable_candidate(monkeypatch):
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, truncate=True)
    async def run():
        try:
            with pytest.raises(ValueError, match='abgeschnitten'):
                await reasoner.plan_reference_design(prepared)
        finally:
            await reasoner.client.aclose()
    asyncio.run(run())
    assert len(observed) == 1


def run_reference(reasoner, prepared):
    async def run():
        try:
            return await reasoner.plan_reference_design(prepared)
        finally:
            await reasoner.client.aclose()
    return asyncio.run(run())


def test_stage_catalogs_preserve_originals_and_only_supply_selected_port_schemas(monkeypatch):
    payloads = []
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, capture=payloads)
    result = run_reference(reasoner, prepared)
    assert result['status'] == 'REVIEW_REQUIRED' and result['canonical_writes'] is False
    assert len(result['proposal']['ports']) == 3
    assert all(row['parameters'] == {'bitrate_bps': 500000} for row in result['proposal']['ports'])
    parameter_stages = [row for row in observed if row['port_ids_for_this_stage']]
    assert len(parameter_stages) == 3
    assert {row['port_ids_for_this_stage'][0] for row in parameter_stages} == {'PC', 'PS', 'PA'}
    for row in observed:
        assert row['original_source'] == prepared['source_evidence']['source_text']
        assert row['reference_sources'] == prepared['reference_sources']
        schemas = row['registered_catalogs'].get('technology_parameters')
        if row['port_ids_for_this_stage']:
            assert len(row['port_ids_for_this_stage']) == 1
            assert set(schemas) == {'can'}
            from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
            assert schemas['can']['parameter_roles'] == registry.parameter_roles('can')
            assert schemas['can']['parameter_aliases'] == registry.profile('can').get('parameter_aliases', {})
            assert schemas['can']['layer'] == registry.profile('can')['layer']
        else:
            assert schemas is None
    # Known peer ports remain visible when the next native port is configured.
    second = parameter_stages[1]['current_candidate']['ports']
    assert next(row for row in second if row['id'] == 'PC')['parameters'] == {'bitrate_bps': 500000}
    function_stages = [row for row in observed if row['function_fact_ids_for_this_stage']]
    expected = {key for key, fact in prepared['facts'].items() if fact['kind'] == 'FUNCTION'}
    assert {key for row in function_stages for key in row['function_fact_ids_for_this_stage']} == expected
    assert all(len(row['function_fact_ids_for_this_stage']) <= 4 for row in function_stages)
    for payload in payloads:
        required = len(json.dumps(payload['messages'], ensure_ascii=False).encode()) + 8192 + 2048
        assert required <= payload['options']['num_ctx'] <= 131072


def test_stage_decoder_narrows_outputs_but_does_not_modify_public_schema(monkeypatch):
    prepared = intake.prepare_reference_design(fixture_request())
    public = deepcopy(intake.reference_design_schema(prepared))
    intent = _reference_schema_for_stage(prepared, {'ports', 'measurements', 'commands'}, port_intent=True)
    assert intent['properties']['devices']['maxItems'] == 0
    port = intent['$defs']['ReferencePort']
    assert port['properties']['parameters'] == {'type': 'object', 'properties': {}, 'additionalProperties': False}
    parameters = _reference_schema_for_stage(prepared, {'ports'}, port_ids=('PC',))
    assert parameters['properties']['ports']['minItems'] == parameters['properties']['ports']['maxItems'] == 1
    assert parameters['$defs']['ReferencePort']['properties']['id']['enum'] == ['PC']
    assert intake.reference_design_schema(prepared) == public
    assert public['properties']['ports']['maxItems'] > 1


def test_io_stages_cover_exact_participants_and_preserve_whole_native_result(monkeypatch):
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch)
    result = run_reference(reasoner, prepared)
    stages = [row for row in observed if row['device_ids_for_this_stage']]
    owners = lambda field: [row['device_ids_for_this_stage'] for row in stages
                            if row['output_fields_for_this_stage'] == [field]]
    assert owners('ports') == [['C'], ['S'], ['A']]
    assert owners('measurements') == [['S']]
    assert owners('commands') == [['A']]
    assert all(len(row['device_ids_for_this_stage']) == 1 for row in stages)
    assert len(result['proposal']['ports']) == 3
    assert len(result['proposal']['measurements']) == len(result['proposal']['commands']) == 1
    assert result['proposal']['unresolved'] == [] and result['canonical_writes'] is False


@pytest.mark.parametrize('field', ['ports', 'measurements', 'commands'])
def test_io_decoder_binds_owner_without_changing_public_schema(field):
    prepared = intake.prepare_reference_design(fixture_request())
    public = deepcopy(intake.reference_design_schema(prepared))
    schema = _reference_schema_for_stage(prepared, {field}, device_ids=('chosen-owner',), port_intent=field == 'ports')
    name = {'ports': 'ReferencePort', 'measurements': 'ReferenceMeasurement', 'commands': 'ReferenceCommand'}[field]
    assert schema['$defs'][name]['properties']['device_id']['enum'] == ['chosen-owner']
    assert all(row['maxItems'] == 0 for key, row in schema['properties'].items() if key not in {field, 'unresolved'})
    assert intake.reference_design_schema(prepared) == public


@pytest.mark.parametrize('field', ['ports', 'measurements', 'commands'])
def test_foreign_io_owner_is_rejected_even_if_native_decoder_is_bypassed(monkeypatch, field):
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, foreign_io=field)
    with pytest.raises(ValueError, match='nicht ausgewählten Teilnehmers'):
        run_reference(reasoner, prepared)
    assert len([row for row in observed if row['output_fields_for_this_stage'] == [field]]) >= 2


def test_port_intent_cannot_overwrite_another_participants_port_id(monkeypatch):
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, duplicate_port_ids=True)
    with pytest.raises(ValueError, match='bereits geplante Port-ID'):
        run_reference(reasoner, prepared)


def test_retry_keeps_selected_owner_after_invalid_port_parameters(monkeypatch):
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, retry_foreign_port=True)
    with pytest.raises(ValueError, match='nicht ausgewählten Teilnehmers'):
        run_reference(reasoner, prepared)
    io = [row for row in observed if row['device_ids_for_this_stage']]
    assert len(io) == 2
    assert all(row['device_ids_for_this_stage'] == ['C'] for row in io)


@pytest.mark.parametrize('mode', ['missing', 'duplicate', 'foreign'])
def test_parameter_merge_rejects_wrong_batch_membership(mode):
    ports = [{'id': 'P', 'device_id': 'C', 'technology': 'can', 'role': 'LOCAL',
              'network_scope': 'local', 'parameters': {}, 'rationale': 'Intent'}]
    row = {**ports[0], 'parameters': {'bitrate_bps': 500000}}
    proposed = [] if mode == 'missing' else [row, deepcopy(row)] if mode == 'duplicate' else [{**row, 'id': 'other'}]
    with pytest.raises(ValueError, match='Port-IDs'):
        _reference_merge_port_parameters(ports, proposed, ('P',))
    assert ports[0]['parameters'] == {}


@pytest.mark.parametrize(('field', 'value'), [
    ('device_id', 'other'), ('technology', 'lin'), ('role', 'BACKBONE'), ('network_scope', 'other')])
def test_parameter_merge_cannot_reassign_port_identity(field, value):
    ports = [{'id': 'P', 'device_id': 'C', 'technology': 'can', 'role': 'LOCAL',
              'network_scope': 'local', 'parameters': {}, 'rationale': 'Intent'}]
    proposed = [{**ports[0], field: value, 'parameters': {'bitrate_bps': 500000}}]
    with pytest.raises(ValueError, match='Portidentität'):
        _reference_merge_port_parameters(ports, proposed, ('P',))
    assert ports[0][field] != value


def test_parameter_merge_preserves_prior_port_reference_sources_without_mutating_input():
    ports = [{'id': 'P', 'device_id': 'C', 'technology': 'can', 'role': 'LOCAL',
              'network_scope': 'local', 'parameters': {}, 'rationale': 'Intent',
              'field_references': {'ports': ['original-clarification']}}]
    proposed = [{**ports[0], 'parameters': {'bitrate_bps': 500000},
                 'field_references': {'ports': ['supplement', 'original-clarification']}}]
    merged = _reference_merge_port_parameters(ports, proposed, ('P',))
    assert merged[0]['field_references'] == {'ports': ['original-clarification', 'supplement']}
    assert merged[0]['parameters'] == {'bitrate_bps': 500000}
    assert ports[0]['parameters'] == {} and ports[0]['field_references'] == {'ports': ['original-clarification']}
    proposed[0]['field_references'] = {'commands': ['supplement']}
    with pytest.raises(ValueError, match='ports-Referenzbelege'):
        _reference_merge_port_parameters(ports, proposed, ('P',))


def test_full_profile_repair_reuses_bounded_phases_and_complete_source(monkeypatch):
    original = intake.validate_reference_design_profile
    checks = []
    def require_repair(value, prepared, profile):
        checks.append(deepcopy(value))
        if len(checks) == 1:
            raise ValueError('Unit finding requires another complete native profile review')
        return original(value, prepared, profile)
    monkeypatch.setattr(intake, 'validate_reference_design_profile', require_repair)
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch)
    result = run_reference(reasoner, prepared)
    assert len(checks) == 2 and result['proposal']['unresolved'] == []
    assert sum(row['planning_stage'] == 'Teilnehmer' for row in observed) == 6
    assert sum(bool(row['port_ids_for_this_stage']) for row in observed) == 6
    assert all(len(row['output_fields_for_this_stage']) <= 3 for row in observed)
    assert all(row['original_source'] == prepared['source_evidence']['source_text'] for row in observed)
    assert any(row['validation_feedback'] for row in observed)


def test_timeout_identifies_actual_stage_without_returning_partial_design(monkeypatch):
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, timeout=True)
    with pytest.raises(ValueError, match='Referenzstufe.*Teilnehmer.*Zeitlimit'):
        run_reference(reasoner, prepared)
    assert observed == []


def test_complete_retry_history_must_fit_without_source_truncation():
    messages = [{'role': 'user', 'content': 'Vollständige Originalquelle äöü 🚗' * 100}]
    before = deepcopy(messages)
    window = _reference_context_window(messages, 131072)
    assert messages == before
    messages += [{'role': 'assistant', 'content': 'invalid response' * 10000}]
    with pytest.raises(ValueError, match='keine Quelle gekürzt'):
        _reference_context_window(messages, 131072)
    assert messages[0] == before[0]


@pytest.mark.parametrize('role', ['SENSOR', 'ACTUATOR'])
def test_missing_native_inventory_cannot_advance_to_any_io(monkeypatch, role):
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, omit_inventory_role=role)
    with pytest.raises(ValueError, match='ein oder zwei eindeutige Teilnehmer'):
        run_reference(reasoner, prepared)
    assert not any(row['device_ids_for_this_stage'] or row['port_ids_for_this_stage'] for row in observed)
    assert observed[-1]['inventory_target_for_this_stage']['fact_id'] in prepared['facts']


def test_inventory_is_native_bounded_and_complete_before_first_port(monkeypatch):
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch)
    result = run_reference(reasoner, prepared)
    inventory = [row for row in observed if row['inventory_target_for_this_stage']]
    assert len(inventory) == 3
    assert {row['inventory_target_for_this_stage']['fact_id'] for row in inventory} == {
        key for key, fact in prepared['facts'].items() if fact['kind'] in {'INSTANCE', 'CATEGORY'}}
    assert len(observed[3]['current_candidate']['devices']) == 3
    assert all(len(row['current_candidate']['devices']) == index for index, row in enumerate(inventory))
    assert result['proposal']['unresolved'] == []
    schema = _reference_schema_for_stage(prepared, {'devices'}, inventory_target=inventory[0]['inventory_target_for_this_stage'])
    assert schema['properties']['devices']['maxItems'] == 2


@pytest.mark.parametrize('field,value', [('name', 'replacement'), ('kind', 'SENSOR'), ('quantity', 2), ('owner_device_id', 'foreign')])
def test_inventory_completion_cannot_reassign_existing_device(field, value):
    prepared = intake.prepare_reference_design(fixture_request())
    row = intake.ReferenceDesignProposal.model_validate(complete_design(prepared)).model_dump(mode='json')['devices'][0]
    changed = {**row, field: value}
    target = {'fact_id': row['source_fact_ids'][0], 'minimum_rows': 1, 'member': None, 'names': []}
    with pytest.raises(ValueError, match='bestehende Teilnehmeridentität'):
        _reference_merge_inventory_devices([row], [changed], target)
    assert row[field] != value


def test_native_type_members_are_planned_separately_before_io(monkeypatch):
    def two_sensors(prepared):
        design = complete_design(prepared)
        first = design['devices'][1]
        fact_id = first['source_fact_ids'][0]
        first['source_member_bindings'] = {fact_id: 'Temperatur links'}
        design['devices'].append({**deepcopy(first), 'id': 'S2', 'name': 'Zweiter Temperatursensor',
                                 'source_member_bindings': {fact_id: 'Temperatur rechts'}})
        design['ports'].append({**deepcopy(design['ports'][1]), 'id': 'PS2', 'device_id': 'S2'})
        design['measurements'].append({**deepcopy(design['measurements'][0]), 'device_id': 'S2'})
        design['communication'].append({**deepcopy(design['communication'][0]), 'id': 'second-temperature',
            'signal_name': 'second-temperature', 'producer_device_id': 'S2', 'source_port_id': 'PS2'})
        return design
    request = fixture_request(sensor_group='Sensortypen (Temperatur links, Temperatur rechts)')
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, request=request, design_factory=two_sensors)
    result = run_reference(reasoner, prepared)
    targets = [row['inventory_target_for_this_stage'] for row in observed if row['inventory_target_for_this_stage']]
    assert [row['member'] for row in targets] == [None, 'Temperatur links', 'Temperatur rechts', None]
    first_port = next(row for row in observed if row['device_ids_for_this_stage'])
    assert len(first_port['current_candidate']['devices']) == 4
    assert result['proposal']['unresolved'] == []
    assert len(result['proposal']['measurements']) == 2
    assert result['source_evidence'] == prepared['source_evidence']


def test_unquantified_category_can_continue_beyond_two_native_participants(monkeypatch):
    def three_sensors(prepared):
        design = complete_design(prepared)
        for number in (2, 3):
            device_id = 'S' + str(number)
            design['devices'].append({**deepcopy(design['devices'][1]), 'id': device_id,
                                     'name': 'Temperatursensor ' + str(number)})
            design['ports'].append({**deepcopy(design['ports'][1]), 'id': 'P' + device_id, 'device_id': device_id})
            design['measurements'].append({**deepcopy(design['measurements'][0]), 'device_id': device_id})
            design['communication'].append({**deepcopy(design['communication'][0]), 'id': 'temperature-' + str(number),
                'signal_name': 'temperature-' + str(number), 'producer_device_id': device_id, 'source_port_id': 'P' + device_id})
        return design
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, design_factory=three_sensors)
    result = run_reference(reasoner, prepared)
    sensor_targets = [row for row in observed if row['inventory_target_for_this_stage']
                      and prepared['facts'][row['inventory_target_for_this_stage']['fact_id']]['role'] == 'SENSOR']
    assert len(sensor_targets) == 2
    assert len(sensor_targets[1]['current_candidate']['devices']) == 3  # Controller plus first two sensors.
    assert len(result['proposal']['devices']) == 5
    assert len(result['proposal']['measurements']) == 3
    assert result['proposal']['unresolved'] == []
    assert 'inventory_complete' not in result['proposal']  # Internal planning protocol grants no public approval.


def test_incomplete_native_inventory_must_progress_instead_of_looping(monkeypatch):
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, never_complete_inventory_role='SENSOR')
    with pytest.raises(ValueError, match='keine fehlende ursprüngliche Geräteabdeckung'):
        run_reference(reasoner, prepared)
    assert len(observed) == 3  # Controller and two sensor attempts, no IO.
    assert not any(row['device_ids_for_this_stage'] for row in observed)
