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
    _reference_declared_instances, _reference_scoped_inventory_delta,
    _reference_expand_inventory_bindings,
    _reference_expand_inventory_choices,
)
from backend.tests.test_reference_design import fixture_request, fixture_design, wire, reference


def effective_reference_context(messages):
    """Independent JSON pointer interpreter for the mocked wire, not product code."""
    context = json.loads(messages[1]['content'])
    for message in messages[2:]:
        if message['role'] != 'user' or not message['content'].startswith('{'):
            continue
        for operation in json.loads(message['content']).get('nis_context_patch', []):
            path = operation['path']
            if path == '':
                assert operation['op'] == 'replace'
                context = deepcopy(operation['value'])
                continue
            keys = [part.replace('~1', '/').replace('~0', '~') for part in path[1:].split('/')]
            parent = context
            for key in keys[:-1]:
                parent = parent[int(key)] if isinstance(parent, list) else parent[key]
            key = keys[-1]
            if isinstance(parent, list):
                index = len(parent) if key == '-' else int(key)
                if operation['op'] == 'remove':
                    parent.pop(index)
                elif operation['op'] == 'add':
                    parent.insert(index, deepcopy(operation['value']))
                else:
                    parent[index] = deepcopy(operation['value'])
            elif operation['op'] == 'remove':
                del parent[key]
            else:
                parent[key] = deepcopy(operation['value'])
    return context


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
                            request=None, design_factory=complete_design, never_complete_inventory_role=None,
                            instance_derived_ids=(), inventory_mutator=None, derivation_mutator=None, binding_mutator=None,
                            wire_padding=False):
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
        content = effective_reference_context(payload['messages'])
        observed.append(content)
        allowed = set(content['output_fields_for_this_stage'])
        # A native provider must use the opaque identities supplied by NIS,
        # including source-compiled devices. No test assumes a particular hash.
        current = content['current_candidate']['devices']
        mapping, claimed = {}, set()
        for row in design['devices']:
            matches = [item for item in current if item['id'] not in claimed and item['name'] == row['name']
                       and item['kind'] == row['kind'] and set(row['source_fact_ids']) & set(item['source_fact_ids'])]
            if matches:
                mapping[row['id']] = matches[0]['id']
                claimed.add(matches[0]['id'])
        active = deepcopy(design)
        for row in active['devices']:
            row['id'] = mapping.get(row['id'], row['id'])
            if row.get('owner_device_id'):
                row['owner_device_id'] = mapping.get(row['owner_device_id'], row['owner_device_id'])
            row['contained_device_ids'] = [mapping.get(key, key) for key in row.get('contained_device_ids', [])]
        for field in ('ports', 'measurements', 'commands'):
            for row in active[field]:
                row['device_id'] = mapping.get(row['device_id'], row['device_id'])
        for row in active['functions']:
            row['executor_device_ids'] = [mapping.get(key, key) for key in row['executor_device_ids']]
        for row in active['communication']:
            row['producer_device_id'] = mapping.get(row['producer_device_id'], row['producer_device_id'])
            row['consumer_device_ids'] = [mapping.get(key, key) for key in row['consumer_device_ids']]
        candidate = {key: deepcopy(value) for key, value in active.items() if key in allowed}
        def use_offered_new_ids(rows, existing):
            items = payload['format']['properties']['inventory_choices']['items']
            variants = items.get('anyOf', [items])
            offered = {item['properties']['choice_kind']['enum'][0]: item['properties']['id']['enum'][0]
                       for item in variants if 'id' in item['properties']}
            for row in rows:
                if row['id'] not in existing:
                    row['id'] = offered['NEW_' + row['kind']]
        if content.get('inventory_target_for_this_stage'):
            target = content['inventory_target_for_this_stage']
            candidate['devices'] = [row for row in candidate['devices']
                if target['fact_id'] in row['source_fact_ids'] and row['kind'] != omit_inventory_role
                and (not target['member'] or row.get('source_member_bindings', {}).get(target['fact_id']) == target['member'])]
            if target['names']:
                candidate['devices'] = [row for row in candidate['devices'] if row['name'] in target['names']]
            existing = {row['id'] for row in content['current_candidate']['devices']}
            fresh = [row for row in candidate['devices'] if row['id'] not in existing]
            candidate['inventory_complete'] = len(fresh) <= 1 and prepared['facts'][target['fact_id']]['role'] != never_complete_inventory_role
            candidate['devices'] = (fresh or candidate['devices'])[:1]
            use_offered_new_ids(candidate['devices'], existing)
            for row in candidate['devices']:
                row['source_fact_ids'] = [target['fact_id']]
                row['source_member_bindings'] = {target['fact_id']: target['member']} if target['member'] else {}
            if inventory_mutator:
                inventory_mutator(candidate, content, payload, prepared)
        if content.get('derivation_fact_ids_for_this_stage') is not None:
            eligible = set(content['derivation_fact_ids_for_this_stage'])
            existing = {row['id'] for row in current}
            fresh = [row for row in active['devices'] if row['id'] not in existing and set(row['source_fact_ids']) <= eligible]
            limit = payload['format']['properties']['inventory_choices']['maxItems']
            candidate['devices'] = deepcopy(fresh[:limit])
            use_offered_new_ids(candidate['devices'], existing)
            candidate['inventory_complete'] = len(fresh) <= limit
            if derivation_mutator:
                derivation_mutator(candidate, content, payload, prepared)
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
        if 'inventory_choices' in payload['format']['properties']:
            candidate['inventory_bindings'] = []
            known = {row['id']: row for row in current}
            new = []
            defaults = {'owner_device_id': None, 'context_kind': None, 'purpose': None, 'contained_device_ids': []}
            for row in candidate['devices']:
                previous = known.get(row['id'])
                if previous and all(row.get(key, defaults.get(key)) == value for key, value in previous.items()
                                    if key not in {'source_fact_ids', 'source_member_bindings', 'rationale', 'field_references'}):
                    candidate['inventory_bindings'].append({'device_id': row['id'], 'source_fact_ids': row['source_fact_ids'],
                        'rationale': row['rationale'], 'field_references': row.get('field_references', {})})
                else:
                    new.append(row)
            candidate['devices'] = new
            if binding_mutator:
                binding_mutator(candidate, content, payload, prepared)
            candidate['inventory_choices'] = [
                *[{'choice_kind': 'NEW_' + row['kind'], **row} for row in candidate['devices']],
                *[{'choice_kind': 'EXISTING', **row} for row in candidate.pop('inventory_bindings')]]
            candidate['devices'] = []
        native_content = (' \n' if wire_padding else '') + json.dumps(candidate) + ('\n ' if wire_padding else '')
        return httpx.Response(200, json={'message': {'content': native_content}, 'done_reason': 'length' if truncate else 'stop',
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


def offered_new_inventory_id(schema, choice_kind):
    items = schema['properties']['inventory_choices']['items']
    choice = next(row for row in items.get('anyOf', [items])
                  if row['properties']['choice_kind']['enum'] == [choice_kind])
    identities = choice['properties']['id']['enum']
    assert len(identities) == 1
    return identities[0]


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
        # Budget the complete text received after HTTP JSON decoding. Wire
        # escaping is not part of the provider's chat-template input.
        required = sum(len(message['content'].encode()) for message in payload['messages']) + 8192 + 2048
        assert required <= payload['options']['num_ctx'] <= 131072
        content = payload['messages'][1]['content']
        assert content == json.dumps(json.loads(content), ensure_ascii=False, separators=(',', ':'))


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
    compiled_id = next(row['id'] for row in observed[0]['current_candidate']['devices'] if row['kind'] == 'CONTROLLER')
    inventory = stages[0]['current_candidate']['devices']
    assert [(row['name'], row['kind']) for row in inventory] == [
        (row['name'], row['kind']) for row in complete_design(prepared)['devices']]
    sensor_id = next(row['id'] for row in inventory if row['kind'] == 'SENSOR')
    actuator_id = next(row['id'] for row in inventory if row['kind'] == 'ACTUATOR')
    assert owners('ports') == [[compiled_id], [sensor_id], [actuator_id]]
    assert owners('measurements') == [[sensor_id]]
    assert owners('commands') == [[actuator_id]]
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
    compiled_id = next(row['id'] for row in observed[0]['current_candidate']['devices'] if row['kind'] == 'CONTROLLER')
    assert all(row['device_ids_for_this_stage'] == [compiled_id] for row in io)


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
    assert sum(row['inventory_target_for_this_stage'] is not None for row in observed) == 4
    assert sum(row['derivation_fact_ids_for_this_stage'] is not None for row in observed) == 2
    assert len(result['declared_inventory_compilation']) == 2  # Same source declaration rechecked for both profile attempts.
    assert sum(bool(row['port_ids_for_this_stage']) for row in observed) == 6
    assert all(len(row['output_fields_for_this_stage']) <= 3 for row in observed)
    assert all(row['original_source'] == prepared['source_evidence']['source_text'] for row in observed)
    assert any(row['validation_feedback'] for row in observed)


def test_timeout_identifies_actual_stage_without_returning_partial_design(monkeypatch):
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, timeout=True)
    with pytest.raises(ValueError, match='Referenzstufe.*Physisches Quelleninventar.*Zeitlimit'):
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


def test_context_counts_model_text_not_escaped_http_json():
    # The provider decodes its HTTP JSON before tokenizing the message text.
    # Nested JSON and quoted source text must not be charged for escaping twice.
    source = '"\\\n ä漢🚗' * 6000
    messages = [{'role': 'user', 'content': json.dumps({'source': source}, ensure_ascii=False)}]
    before = deepcopy(messages)
    actual = len(messages[0]['content'].encode('utf-8')) + 8192 + 2048
    wire = len(json.dumps(messages, ensure_ascii=False).encode('utf-8')) + 8192 + 2048
    assert actual < 131072 < wire
    window = _reference_context_window(messages, 131072)
    assert actual <= window <= 131072
    assert messages == before and json.loads(messages[0]['content'])['source'] == source


@pytest.mark.parametrize('text', ['x', 'ä', '漢', '🚗', '"\\\n'])
def test_context_reserves_full_utf8_text_output_and_framing(text):
    # One byte below the true configured input limit succeeds. One byte above
    # fails even if this is a validation retry rather than the first request.
    maximum = 32768
    prefix = text * 100
    content = prefix + 'x' * (maximum - 8192 - 2048 - len(prefix.encode('utf-8')) - 1)
    messages = [{'role': 'system', 'content': ''}, {'role': 'user', 'content': content}]
    before = deepcopy(messages)
    assert _reference_context_window(messages, maximum) == maximum
    messages.append({'role': 'assistant', 'content': 'xx'})
    with pytest.raises(ValueError, match='keine Quelle gekürzt'):
        _reference_context_window(messages, maximum)
    assert messages[:2] == before


@pytest.mark.parametrize('role', ['SENSOR', 'ACTUATOR'])
def test_missing_native_inventory_cannot_advance_to_any_io(monkeypatch, role):
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, omit_inventory_role=role)
    with pytest.raises(ValueError, match='leer ist nur ein bereits abgedeckter Bereich'):
        run_reference(reasoner, prepared)
    assert not any(row['device_ids_for_this_stage'] or row['port_ids_for_this_stage'] for row in observed)
    assert observed[-1]['inventory_target_for_this_stage']['fact_id'] in prepared['facts']


def test_inventory_is_native_bounded_and_complete_before_first_port(monkeypatch):
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch)
    result = run_reference(reasoner, prepared)
    inventory = [row for row in observed if row['inventory_target_for_this_stage']]
    assert len(inventory) == 2
    assert {row['inventory_target_for_this_stage']['fact_id'] for row in inventory} == {
        key for key, fact in prepared['facts'].items() if fact['kind'] == 'CATEGORY'}
    derivation = next(row for row in observed if row['derivation_fact_ids_for_this_stage'] is not None)
    assert len(derivation['current_candidate']['devices']) == 3
    assert all(len(row['current_candidate']['devices']) == index + 1 for index, row in enumerate(inventory))
    assert len(result['declared_inventory_compilation']) == 1
    assert result['declared_inventory_compilation'][0]['native_model_call'] is False
    assert result['proposal']['unresolved'] == []
    schema = _reference_schema_for_stage(prepared, {'devices'}, inventory_target=inventory[0]['inventory_target_for_this_stage'])
    assert schema['properties']['devices']['maxItems'] == 0
    assert schema['properties']['inventory_choices']['maxItems'] == 1


@pytest.mark.parametrize('field,value', [('name', 'replacement'), ('kind', 'SENSOR'), ('quantity', 2), ('owner_device_id', 'foreign')])
def test_inventory_completion_cannot_reassign_existing_device(field, value):
    prepared = intake.prepare_reference_design(fixture_request())
    row = intake.ReferenceDesignProposal.model_validate(complete_design(prepared)).model_dump(mode='json')['devices'][0]
    changed = {**row, field: value}
    target = {'fact_id': row['source_fact_ids'][0], 'minimum_rows': 1, 'member': None, 'names': []}
    with pytest.raises(ValueError, match='bestehende Teilnehmeridentität'):
        _reference_merge_inventory_devices([row], [changed], target, prepared['facts'])
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
    assert [row['member'] for row in targets] == ['Temperatur links', 'Temperatur rechts', None]
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
    assert len(sensor_targets) == 3
    assert len(sensor_targets[1]['current_candidate']['devices']) == 2  # Compiled controller plus first sensor.
    assert len(result['proposal']['devices']) == 5
    assert len(result['proposal']['measurements']) == 3
    assert result['proposal']['unresolved'] == []
    assert 'inventory_complete' not in result['proposal']  # Internal planning protocol grants no public approval.


def test_incomplete_native_inventory_must_progress_instead_of_looping(monkeypatch):
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, never_complete_inventory_role='SENSOR')
    with pytest.raises(ValueError, match='keine fehlende ursprüngliche Geräteabdeckung'):
        run_reference(reasoner, prepared)
    assert len(observed) == 3  # Compiled controller; sensor, stagnant response and corrective retry.
    assert observed[-1]['inventory_target_for_this_stage'] == observed[-2]['inventory_target_for_this_stage']
    assert not any(row['device_ids_for_this_stage'] for row in observed)


def test_one_explicit_controller_can_continue_for_separately_derived_sensors(monkeypatch):
    def derived_sensors(prepared):
        design = complete_design(prepared)
        function_id = next(key for key, fact in prepared['facts'].items() if fact['name'] == 'Regelung')
        for number in (2, 3):
            device_id = 'S' + str(number)
            design['devices'].append({**deepcopy(design['devices'][1]), 'id': device_id,
                'name': 'Abgeleiteter Temperatursensor ' + str(number), 'source_fact_ids': [function_id]})
            design['ports'].append({**deepcopy(design['ports'][1]), 'id': 'P' + device_id, 'device_id': device_id})
            design['measurements'].append({**deepcopy(design['measurements'][0]), 'device_id': device_id})
            design['communication'].append({**deepcopy(design['communication'][0]), 'id': 'derived-temperature-' + str(number),
                'signal_name': 'derived-temperature-' + str(number), 'producer_device_id': device_id, 'source_port_id': 'P' + device_id})
        return design
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, design_factory=derived_sensors, instance_derived_ids=('S2', 'S3'))
    result = run_reference(reasoner, prepared)
    anchor_id = next(key for key, fact in prepared['facts'].items() if fact['kind'] == 'INSTANCE')
    assert not any((row['inventory_target_for_this_stage'] or {}).get('fact_id') == anchor_id for row in observed)
    stages = [row for row in observed if row['derivation_fact_ids_for_this_stage'] is not None]
    assert len(stages) == 2
    assert len(stages[1]['current_candidate']['devices']) == 4  # Literal C/S/A plus first derived sensor.
    assert sum(anchor_id in row['source_fact_ids'] for row in result['proposal']['devices']) == 1
    assert len(result['proposal']['measurements']) == 3
    assert result['proposal']['unresolved'] == []
    assert len(result['coverage']['derived_device_bindings']) == 1


def test_native_continuation_still_rejects_actual_explicit_source_count_overflow(monkeypatch):
    def overcount(candidate, content, payload, prepared):
        first = next(row for row in content['current_candidate']['devices'] if row['kind'] == 'CONTROLLER')
        candidate['devices'] = [{**deepcopy(first), 'id': 'extra-controller', 'name': 'Unplanned extra controller'}]
        candidate['inventory_complete'] = True
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, derivation_mutator=overcount)
    with pytest.raises(ValueError, match='Funktionale Hardwareergänzung'):
        run_reference(reasoner, prepared)
    attempts = [row for row in observed if row['derivation_fact_ids_for_this_stage'] is not None]
    assert len(attempts) == 2
    source_id = next(key for key, fact in prepared['facts'].items() if fact['kind'] == 'INSTANCE')
    assert all(sum(source_id in node['source_fact_ids'] for node in row['current_candidate']['devices']) == 1 for row in attempts)
    assert not any(row['device_ids_for_this_stage'] for row in observed)


@pytest.mark.parametrize('corruption', ['self_owner', 'instance_member', 'foreign_inventory'])
def test_invalid_native_inventory_prefix_is_corrected_before_accumulation(monkeypatch, corruption):
    def corrupt_first(candidate, content, payload, prepared):
        if content['current_candidate']['devices'] or len(payload['messages']) != 2:
            return
        row = candidate['devices'][0]
        if corruption == 'self_owner':
            row['owner_device_id'] = row['id']
        elif corruption == 'instance_member':
            row['source_member_bindings'] = {row['source_fact_ids'][0]: 'Controller (ECU)'}
        else:
            candidate['devices'].append(deepcopy(complete_design(prepared)['devices'][1]))
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, inventory_mutator=corrupt_first,
        request=fixture_request(controller_category=True))
    result = run_reference(reasoner, prepared)
    assert observed[0]['inventory_target_for_this_stage'] == observed[1]['inventory_target_for_this_stage']
    assert observed[0]['current_candidate']['devices'] == observed[1]['current_candidate']['devices'] == []
    assert not observed[0]['device_ids_for_this_stage'] and not observed[1]['device_ids_for_this_stage']
    first_valid_next_stage = observed[2]['current_candidate']['devices']
    assert len(first_valid_next_stage) == 1
    assert first_valid_next_stage[0]['owner_device_id'] is None
    assert first_valid_next_stage[0]['source_member_bindings'] == {}
    assert result['proposal']['unresolved'] == []
    assert result['source_evidence'] == prepared['source_evidence']


def test_inventory_decoder_scopes_new_sources_and_role_specific_member_keys():
    prepared = intake.prepare_reference_design(fixture_request(sensor_group='Sensortypen (Temperatur, Druck)'))
    facts = prepared['facts']
    target_id = next(key for key, fact in facts.items() if fact['role'] == 'SENSOR')
    controller_id = next(key for key, fact in facts.items() if fact['role'] == 'CONTROLLER')
    actor_id = next(key for key, fact in facts.items() if fact['role'] == 'ACTUATOR')
    schema = _reference_schema_for_stage(prepared, {'devices'}, inventory_target={
        'fact_id': target_id, 'minimum_rows': 1, 'member': 'Temperatur'})
    variants = schema['$defs']['ReferenceDevice']['anyOf']
    for row in variants:
        properties = row['properties']
        ids = properties['source_fact_ids']['items']['enum']
        assert actor_id not in ids and controller_id not in ids
        assert ids == [target_id]
        assert all(facts[key]['role'] in {properties['kind']['enum'][0], 'OTHER'} for key in ids)
    sensor = next(row for row in variants if row['properties']['kind']['enum'] == ['SENSOR'])
    assert sensor['properties']['source_member_bindings']['properties'] == {
        target_id: {'type': 'string', 'enum': ['Temperatur']}}
    assert 'anyOf' not in intake.reference_design_schema(prepared)['$defs']['ReferenceDevice']


def test_existing_inventory_binding_survives_additional_selected_source():
    prepared = intake.prepare_reference_design(fixture_request())
    design = complete_design(prepared)
    row = intake.ReferenceDesignProposal.model_validate(design).model_dump(mode='json')['devices'][1]
    target_id = next(key for key, fact in prepared['facts'].items() if fact['kind'] == 'FUNCTION')
    changed = {**deepcopy(row), 'source_fact_ids': [*row['source_fact_ids'], target_id]}
    target = {'fact_id': target_id, 'minimum_rows': 1, 'member': None, 'names': []}
    merged = _reference_merge_inventory_devices([row], [changed], target, prepared['facts'])
    assert merged == [changed]
    assert row['source_fact_ids'] != changed['source_fact_ids']


def test_declared_controller_count_and_identities_are_compiled_without_native_choices():
    prepared = intake.prepare_reference_design(fixture_request(controller_count=3))
    rows, events = _reference_declared_instances(prepared, prepared['facts'])
    assert len(rows) == 3 and len({row['id'] for row in rows}) == 3
    source_id = next(key for key, fact in prepared['facts'].items() if fact['kind'] == 'INSTANCE')
    expected_names = {row['name'] for row in prepared['catalog']['source_devices']}
    assert {row['name'] for row in rows} == expected_names
    assert all(row['source_fact_ids'] == [source_id] and row['kind'] == 'CONTROLLER'
               and row['quantity'] == 1 and row['owner_device_id'] is None for row in rows)
    assert events[0]['quantity'] == 3 and events[0]['native_model_call'] is False
    assert events[0]['hardware_evidence'] is False
    assert _reference_declared_instances(prepared, prepared['facts']) == (rows, events)
    findings = intake._validate_reference_inventory({'devices': rows}, prepared, [], partial=True)
    assert not any(row['target_ref'] == source_id for row in findings)
    assert findings  # Declared sensors/actors still need native planning; no review/approval.


def test_ambiguous_source_identity_is_not_invented_by_literal_compiler():
    prepared = intake.prepare_reference_design(fixture_request())
    supplied = deepcopy(prepared)
    supplied['catalog']['source_devices'] = []
    assert _reference_declared_instances(supplied, supplied['facts']) == ([], [])
    assert prepared['catalog']['source_devices']  # No input mutation or fabricated fallback name.


def test_source_cursor_appends_old_provenance_without_requiring_a_replacement_row():
    prepared = intake.prepare_reference_design(fixture_request())
    rows, _ = _reference_declared_instances(prepared, prepared['facts'])
    old = rows[0]
    function_id = next(key for key, fact in prepared['facts'].items() if fact['kind'] == 'FUNCTION')
    old['source_fact_ids'].append(function_id)
    incoming = deepcopy(old)
    incoming['source_fact_ids'] = incoming['source_fact_ids'][:1]
    target = {'fact_id': incoming['source_fact_ids'][0], 'member': None, 'minimum_rows': 0, 'names': []}
    delta = _reference_scoped_inventory_delta([old], [incoming], inventory_target=target)
    assert delta[0]['source_fact_ids'] == old['source_fact_ids']
    assert incoming['source_fact_ids'] != old['source_fact_ids']
    assert _reference_merge_inventory_devices([old], delta, target, prepared['facts']) == [old]
    incoming['source_fact_ids'].append(function_id)
    with pytest.raises(ValueError, match='genau den angeforderten Quellenbefund'):
        _reference_scoped_inventory_delta([old], [incoming], inventory_target=target)


def test_empty_source_closure_cannot_skip_missing_declared_coverage():
    prepared = intake.prepare_reference_design(fixture_request())
    rows, _ = _reference_declared_instances(prepared, prepared['facts'])
    target = {'fact_id': rows[0]['source_fact_ids'][0], 'member': None, 'minimum_rows': 0, 'names': []}
    assert _reference_merge_inventory_devices(rows, [], target, prepared['facts']) == rows
    with pytest.raises(ValueError, match='bereits abgedeckter Bereich'):
        _reference_merge_inventory_devices([], [], target, prepared['facts'])


def test_false_empty_functional_hardware_delta_is_not_silently_completed(monkeypatch):
    def stagnant(candidate, content, payload, prepared):
        candidate.update(devices=[], inventory_complete=False)
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, derivation_mutator=stagnant)
    with pytest.raises(ValueError, match='keine fehlende ursprüngliche Geräteabdeckung'):
        run_reference(reasoner, prepared)
    attempts = [row for row in observed if row['derivation_fact_ids_for_this_stage'] is not None]
    assert len(attempts) == 2
    assert not any(row['device_ids_for_this_stage'] for row in observed)


def test_functional_hardware_decoder_never_promotes_declared_inventory():
    prepared = intake.prepare_reference_design(fixture_request())
    supported = [key for key, fact in prepared['facts'].items() if fact['kind'] in {'FUNCTION', 'REQUIREMENT'}]
    schema = _reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=supported)
    assert schema['properties']['devices']['minItems'] == 0
    assert schema['properties']['devices']['maxItems'] == 0
    assert schema['properties']['inventory_choices']['minItems'] == 0
    assert schema['properties']['inventory_choices']['maxItems'] == 1
    assert 'inventory_complete' in schema['required']
    for row in schema['$defs']['ReferenceDevice']['anyOf']:
        assert set(row['properties']['source_fact_ids']['items']['enum']) <= set(supported)
        assert row['properties']['source_member_bindings'] == {
            'type': 'object', 'properties': {}, 'additionalProperties': False}


@pytest.mark.parametrize('field', ['source_fact_ids', 'field_references'])
def test_scoped_delta_must_reject_raw_duplicate_metadata_before_append(field):
    prepared = intake.prepare_reference_design(fixture_request(references=[reference(fields=('quantity',))]))
    rows, _ = _reference_declared_instances(prepared, prepared['facts'])
    old = rows[0]
    old['field_references'] = {'quantity': ['R1']}
    function_id = next(key for key, fact in prepared['facts'].items() if fact['kind'] == 'FUNCTION')
    incoming = deepcopy(old)
    incoming['source_fact_ids'] = [function_id]
    if field == 'source_fact_ids':
        incoming['source_fact_ids'].append(function_id)
    else:
        incoming['field_references']['quantity'].append('R1')
    before = deepcopy(incoming)
    with pytest.raises(ValueError, match='[Dd]oppelte'):
        _reference_scoped_inventory_delta([old], [incoming], derivation_fact_ids=[function_id])
    assert incoming == before


def test_existing_binding_schema_offers_only_identity_selection_and_scoped_metadata():
    prepared = intake.prepare_reference_design(fixture_request())
    devices, _ = _reference_declared_instances(prepared, prepared['facts'])
    fact = next(key for key, row in prepared['facts'].items() if row['kind'] == 'FUNCTION')
    schema = _reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=[fact], existing_devices=devices)
    alternatives = schema['properties']['inventory_choices']['items']['anyOf']
    choice = next(row for row in alternatives if 'device_id' in row.get('properties', {}))
    assert choice['additionalProperties'] is False
    assert set(choice['properties']) == {'choice_kind', 'device_id', 'source_fact_ids', 'rationale', 'field_references'}
    assert choice['properties']['choice_kind']['enum'] == ['EXISTING']
    assert choice['required'][0] == 'choice_kind'
    for candidate in (row for row in alternatives if row is not choice):
        kind = candidate['properties']['kind']['enum'][0]
        original = next(row for row in schema['$defs']['ReferenceDevice']['anyOf']
                        if row['properties']['kind']['enum'] == [kind])
        assert candidate['properties']['choice_kind']['enum'] == ['NEW_' + kind]
        assert {key: value for key, value in candidate['properties'].items() if key != 'choice_kind'} == original['properties']
        assert candidate['required'] == ['choice_kind', *original['required']]
    assert choice['properties']['device_id']['enum'] == [row['id'] for row in devices]
    assert choice['properties']['source_fact_ids']['items']['enum'] == [fact]
    assert set(choice['required']) == set(choice['properties'])
    assert 'inventory_choices' in schema['required']
    assert 'inventory_choices' not in intake.reference_model_output_schema(prepared)['properties']
    assert 'inventory_bindings' not in schema['properties']
    empty = _reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=[fact])
    assert all(row['properties']['choice_kind']['enum'][0].startswith('NEW_')
               and 'device_id' not in row['properties']
               for row in empty['properties']['inventory_choices']['items']['anyOf'])


@pytest.mark.parametrize('mismatch', ['role', 'name', 'member'])
def test_existing_binding_schema_excludes_incompatible_immutable_identities(mismatch):
    prepared = intake.prepare_reference_design(fixture_request(sensor_group='Sensortypen (Temperatur links, Temperatur rechts)'))
    devices = intake.ReferenceDesignProposal.model_validate(complete_design(prepared)).model_dump(mode='json')['devices']
    sensor = next(row for row in devices if row['kind'] == 'SENSOR')
    fact = sensor['source_fact_ids'][0]
    # The compatible positive must add a binding, rather than repeat one.
    sensor['source_fact_ids'] = [next(key for key, row in prepared['facts'].items() if row['kind'] == 'FUNCTION')]
    sensor['source_member_bindings'] = {}
    target = {'fact_id': fact, 'member': 'Temperatur links', 'names': [], 'minimum_rows': 1}
    valid = _reference_schema_for_stage(prepared, {'devices'}, inventory_target=target, existing_devices=devices)
    choices = valid['properties']['inventory_choices']['items']['anyOf']
    binding = next(row for row in choices if 'device_id' in row.get('properties', {}))
    assert binding['properties']['device_id']['enum'] == [sensor['id']]
    if mismatch == 'role':
        target['fact_id'] = next(key for key, row in prepared['facts'].items() if row['role'] == 'CONTROLLER')
        target['member'] = None
    elif mismatch == 'name':
        target['names'] = ['A different explicit original name']
    else:
        sensor['source_fact_ids'].append(fact)
        sensor['source_member_bindings'] = {fact: 'Temperatur links'}
        target['member'] = 'Temperatur rechts'
    schema = _reference_schema_for_stage(prepared, {'devices'}, inventory_target=target, existing_devices=[sensor])
    new_choice = schema['properties']['inventory_choices']['items']
    assert new_choice['properties']['choice_kind']['enum'] == ['NEW_' + prepared['facts'][target['fact_id']]['role']]
    assert 'device_id' not in new_choice['properties']
    assert schema['properties']['inventory_choices']['minItems'] == 1
    assert schema['properties']['devices']['maxItems'] == 0


def test_binding_expansion_preserves_identity_then_appends_source_metadata_without_mutation():
    prepared = intake.prepare_reference_design(fixture_request())
    devices, _ = _reference_declared_instances(prepared, prepared['facts'])
    old = devices[0]
    old['purpose'] = 'Existing reviewed purpose'
    old['field_references'] = {'device_type': ['R_OLD']}
    fact = next(key for key, row in prepared['facts'].items() if row['kind'] == 'FUNCTION')
    target = {'fact_id': fact, 'member': None, 'names': [], 'minimum_rows': 1}
    choice = {'device_id': old['id'], 'source_fact_ids': [fact], 'rationale': 'Reuse actual executor', 'field_references': {}}
    before, raw_choice = deepcopy(devices), deepcopy(choice)
    expanded = _reference_expand_inventory_bindings(devices, [], [choice], inventory_target=target)
    typed = intake.ReferenceDesignProposal.model_validate({'devices': expanded}).model_dump(mode='json')['devices']
    delta = _reference_scoped_inventory_delta(devices, typed, inventory_target=target)
    merged = _reference_merge_inventory_devices(devices, delta, target, prepared['facts'])
    assert devices == before and choice == raw_choice
    assert merged[0]['source_fact_ids'] == [*old['source_fact_ids'], fact]
    assert merged[0]['field_references'] == old['field_references']
    assert all(merged[0][key] == value for key, value in old.items()
               if key not in {'source_fact_ids', 'rationale'})


@pytest.mark.parametrize('field', ['id', 'name', 'kind', 'quantity', 'owner_device_id', 'context_kind', 'purpose', 'contained_device_ids', 'source_member_bindings'])
def test_binding_cannot_write_any_immutable_device_or_cursor_field(field):
    prepared = intake.prepare_reference_design(fixture_request())
    devices, _ = _reference_declared_instances(prepared, prepared['facts'])
    choice = {'device_id': devices[0]['id'], 'source_fact_ids': devices[0]['source_fact_ids'],
              'rationale': 'Invalid unit choice', 'field_references': {}, field: 'foreign'}
    with pytest.raises(ValueError, match='Inventarbindung erlaubt nur'):
        _reference_expand_inventory_bindings(devices, [], [choice])


@pytest.mark.parametrize('mode', ['unknown', 'duplicate', 'joint-limit', 'redeclare'])
def test_binding_rejects_unknown_duplicate_over_budget_and_redeclared_identities(mode):
    prepared = intake.prepare_reference_design(fixture_request())
    devices, _ = _reference_declared_instances(prepared, prepared['facts'])
    choice = {'device_id': devices[0]['id'], 'source_fact_ids': devices[0]['source_fact_ids'],
              'rationale': 'Unit choice', 'field_references': {}}
    target = {'fact_id': devices[0]['source_fact_ids'][0], 'member': None}
    if mode == 'unknown':
        choice['device_id'] = 'not-an-existing-device'
        proposed, bindings, target = [], [choice], None
    elif mode == 'duplicate':
        proposed, bindings, target = [], [choice, deepcopy(choice)], None
    elif mode == 'joint-limit':
        proposed, bindings = [{**devices[0], 'id': 'new-device'}], [choice]
    else:
        proposed, bindings, target = [devices[0]], [], None
    with pytest.raises(ValueError):
        _reference_expand_inventory_bindings(devices, proposed, bindings, inventory_target=target)


@pytest.mark.parametrize('field', ['source_fact_ids', 'field_references'])
def test_binding_expansion_does_not_hide_duplicate_native_metadata(field):
    prepared = intake.prepare_reference_design(fixture_request())
    devices, _ = _reference_declared_instances(prepared, prepared['facts'])
    fact = next(key for key, row in prepared['facts'].items() if row['kind'] == 'FUNCTION')
    choice = {'device_id': devices[0]['id'], 'source_fact_ids': [fact], 'rationale': 'Unit choice', 'field_references': {}}
    if field == 'source_fact_ids':
        choice[field].append(fact)
    else:
        choice[field] = {'device_type': ['R1', 'R1']}
    expanded = _reference_expand_inventory_bindings(devices, [], [choice])
    with pytest.raises(ValueError, match='[Dd]oppelte'):
        _reference_scoped_inventory_delta(devices, expanded, derivation_fact_ids=[fact])


def test_full_reference_protocol_reuses_existing_id_without_echoing_identity(monkeypatch):
    captured = []
    def reuse(candidate, content, payload, prepared):
        old = next(row for row in content['current_candidate']['devices'] if row['kind'] == 'CONTROLLER')
        fact = content['derivation_fact_ids_for_this_stage'][0]
        candidate.update(devices=[{**old, 'source_fact_ids': [fact], 'source_member_bindings': {},
                                  'rationale': 'Reuse existing physical executor'}], inventory_complete=True)
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, derivation_mutator=reuse, capture=captured)
    result = run_reference(reasoner, prepared)
    step = next(row for row in observed if row['derivation_fact_ids_for_this_stage'] is not None)
    old = next(row for row in step['current_candidate']['devices'] if row['kind'] == 'CONTROLLER')
    saved = [row for row in result['proposal']['devices'] if row['name'] == old['name'] and row['kind'] == old['kind']]
    assert len(saved) == 1
    assert all(saved[0][key] == old[key]
               for key in ('name', 'kind', 'quantity', 'context_kind', 'purpose', 'owner_device_id', 'contained_device_ids'))
    native = next(row for row in captured if 'inventory_choices' in row['format']['properties']
                  and effective_reference_context(row['messages'])['derivation_fact_ids_for_this_stage'] is not None)
    variants = native['format']['properties']['inventory_choices']['items']['anyOf']
    binding = next(row for row in variants if 'device_id' in row.get('properties', {}))
    assert set(binding['properties']) == {
        'choice_kind', 'device_id', 'source_fact_ids', 'rationale', 'field_references'}
    assert all('choice_kind' not in row for row in result['proposal']['devices'])
    assert result['proposal']['unresolved'] == [] and result['canonical_writes'] is False


def overlapping_inventory_request():
    """Unit source with one literal controller and another category for it."""
    import hashlib
    request = fixture_request()
    envelope = json.loads(request['prompt'].split('\n- Dokument-Geräte: ', 1)[1])
    quote = 'Steuergeräte (ECU)'
    envelope['source_text'] += '\n' + quote
    envelope['source_chars'] = len(envelope['source_text'])
    envelope['source_sha256'] = hashlib.sha256(envelope['source_text'].encode()).hexdigest()
    envelope['facts'].append({'name': 'Steuergeräte', 'kind': 'CATEGORY', 'role': 'CONTROLLER',
                             'quantity': None, 'source_quote': quote, 'source_context': []})
    request['prompt'] = envelope['source_text'] + '\n- Dokument-Geräte: ' + json.dumps(envelope, ensure_ascii=False)
    return request


@pytest.mark.parametrize('missing', ['source_count', 'canonical_name'])
def test_native_choice_grammar_rejects_empty_missing_coverage_even_with_existing_devices(missing):
    from jsonschema import Draft202012Validator, ValidationError
    prepared = intake.prepare_reference_design(overlapping_inventory_request())
    known, _ = _reference_declared_instances(prepared, prepared['facts'])
    fact = next(key for key, row in prepared['facts'].items() if row['kind'] == 'CATEGORY' and row['role'] == 'CONTROLLER')
    assert known and all(fact not in row['source_fact_ids'] for row in known)
    target = {'fact_id': fact, 'member': None, 'names': [], 'minimum_rows': 1}
    if missing == 'canonical_name':
        target.update(minimum_rows=0, names=['Required original canonical name'])
    schema = _reference_schema_for_stage(prepared, {'devices'}, inventory_target=target, existing_devices=known)
    value = {**intake.ReferenceDesignProposal().model_dump(mode='json'),
             'inventory_complete': True, 'inventory_choices': []}
    with pytest.raises(ValidationError) as error:
        Draft202012Validator(schema).validate(value)
    assert list(error.value.path) == ['inventory_choices']
    with pytest.raises(ValueError, match='bereits abgedeckter Bereich'):
        _reference_expand_inventory_choices(known, [], inventory_target=target)


def test_shared_source_choice_accepts_either_binding_or_new_device_but_never_both():
    from jsonschema import Draft202012Validator, ValidationError
    prepared = intake.prepare_reference_design(overlapping_inventory_request())
    known, _ = _reference_declared_instances(prepared, prepared['facts'])
    fact = next(key for key, row in prepared['facts'].items() if row['kind'] == 'CATEGORY' and row['role'] == 'CONTROLLER')
    target = {'fact_id': fact, 'member': None, 'names': [], 'minimum_rows': 1}
    schema = _reference_schema_for_stage(prepared, {'devices'}, inventory_target=target, existing_devices=known)
    binding = {'choice_kind': 'EXISTING', 'device_id': known[0]['id'], 'source_fact_ids': [fact], 'rationale': 'Same source controller', 'field_references': {}}
    new = {'choice_kind': 'NEW_CONTROLLER', **deepcopy(known[0]),
           'id': offered_new_inventory_id(schema, 'NEW_CONTROLLER'),
           'name': 'Additional reference controller', 'source_fact_ids': [fact]}
    base = {**intake.ReferenceDesignProposal().model_dump(mode='json'), 'inventory_complete': True}
    validator = Draft202012Validator(schema)
    for choice in (binding, new):
        validator.validate({**base, 'inventory_choices': [choice]})
        before = deepcopy(choice)
        expanded = _reference_expand_inventory_choices(known, [choice], inventory_target=target)
        assert len(expanded) == 1 and 'choice_kind' not in expanded[0]
        assert choice == before
        intake.ReferenceDesignProposal.model_validate({'devices': expanded})
    with pytest.raises(ValidationError) as error:
        validator.validate({**base, 'inventory_choices': [binding, new]})
    assert list(error.value.path) == ['inventory_choices']
    with pytest.raises(ValueError, match='innerhalb ihrer Grenze'):
        _reference_expand_inventory_choices(known, [binding, new], inventory_target=target)


def test_zero_minimum_choice_still_cannot_claim_uncovered_source_closure():
    prepared = intake.prepare_reference_design(overlapping_inventory_request())
    known, _ = _reference_declared_instances(prepared, prepared['facts'])
    fact = next(key for key, row in prepared['facts'].items() if row['kind'] == 'CATEGORY' and row['role'] == 'CONTROLLER')
    target = {'fact_id': fact, 'member': None, 'names': [], 'minimum_rows': 0}
    empty = _reference_expand_inventory_choices(known, [], inventory_target=target)
    with pytest.raises(ValueError, match='bereits abgedeckter Bereich'):
        _reference_merge_inventory_devices(known, empty, target, prepared['facts'])


def test_inventory_progress_records_actual_cursor_and_unaccepted_role_counts(monkeypatch):
    from backend.nis.engineering.goal_execution.progress import sink
    events = []
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch)
    token = sink.set(events.append)
    try:
        result = run_reference(reasoner, prepared)
    finally:
        sink.reset(token)
    inventory = [row['metadata'] for row in events if 'inventory_target' in row.get('metadata', {})]
    assert len(inventory) == 3
    first = inventory[0]
    assert prepared['facts'][first['inventory_target']['fact_id']]['role'] == 'SENSOR'
    assert first['inventory_target']['minimum_rows'] == 1
    assert first['draft_inventory_by_kind'] == {
        'CONTROLLER': 1, 'GATEWAY': 0, 'SENSOR': 0, 'ACTUATOR': 0, 'PHYSICAL_CONTEXT': 0}
    assert inventory[1]['draft_inventory_by_kind']['SENSOR'] == 1
    assert inventory[-1]['inventory_target'] is None
    assert all(row['canonical_writes'] is False for row in inventory)
    assert result['canonical_writes'] is False


def test_reference_capacity_stays_at_configured_maximum_without_weakening_overflow():
    for length in (10, 5000, 22000):
        assert _reference_context_window([{'content': 'x' * length}], 131072) == 131072
    with pytest.raises(ValueError, match='keine Quelle gekürzt'):
        _reference_context_window([{'content': 'ä' * 66000}], 131072)


def test_reference_continuation_keeps_prior_native_wire_prefix(monkeypatch):
    captured = []
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, capture=captured)
    result = run_reference(reasoner, prepared)
    assert len(captured) > 3
    for previous, current in zip(captured, captured[1:]):
        assert current['messages'][:len(previous['messages'])] == previous['messages']
        assert current['messages'][-2]['role'] == 'assistant'
        assert 'nis_context_patch' in json.loads(current['messages'][-1]['content'])
    assert [effective_reference_context(row['messages']) for row in captured] == observed
    assert result['canonical_writes'] is False


def test_reference_visible_progress_reports_actual_calls_scope_and_retry(monkeypatch):
    from backend.nis.engineering.goal_execution.progress import sink
    events, captured = [], []
    reasoner, prepared, _ = reasoner_with_transport(monkeypatch, capture=captured, retry_foreign_port=True, wire_padding=True)
    token = sink.set(events.append)
    try:
        with pytest.raises(ValueError, match='nicht ausgewählten Teilnehmers'):
            run_reference(reasoner, prepared)
    finally:
        sink.reset(token)
    progress = [event for event in events if event.get('metadata', {}).get('source') == 'document_reference_design']
    assert len(progress) == len(captured)
    for index, event in enumerate(progress):
        assert event['metadata']['completed_calls'] == index
        assert f'{index} Modellantworten empfangen' in event['text']
        assert event['metadata']['canonical_writes'] is False
    scopes = [event for event in progress if event['metadata'].get('derivation_fact_ids')]
    assert scopes and all('Quellenbereich 1 von 1' in event['text'] for event in scopes)
    assert progress[-1]['metadata']['attempt'] == 2
    assert 'Korrekturversuch 2' in progress[-1]['text']


@pytest.mark.parametrize(('previous', 'current'), [
    ({'a/b~c': {'old': 1, 'list': [1, 2, 3]}, 'removed': None},
     {'a/b~c': {'list': [False, None]}, 'new': 'Gerät ä 🦾'}),
    ({'items': [1]}, {'items': [1, {'nested': ['µ', True]}, 3]}),
    ({'items': [1, 2, 3]}, {'items': []}),
    ({'value': True}, {'value': 1}),
    ({'value': 1}, {'value': 1.0}),
    ({}, {'': {'~/': None}}),
    ({'old': ['all original source', 42]}, {'old': ['all original source', 42]}),
])
def test_reference_context_patch_roundtrip_is_lossless_and_does_not_mutate(previous, current):
    from backend.nis.agent.orchestration.local_reasoner import _reference_context_patch
    old, new = deepcopy(previous), deepcopy(current)
    messages = [{'role': 'system', 'content': 'unit'}, {'role': 'user', 'content': json.dumps(previous)},
                {'role': 'user', 'content': json.dumps({'nis_context_patch': _reference_context_patch(previous, current)})}]
    assert json.dumps(effective_reference_context(messages), sort_keys=True) == json.dumps(current, sort_keys=True)
    assert previous == old and current == new


def test_reference_history_rebase_keeps_full_current_sources_and_catalogs():
    from backend.nis.agent.orchestration.local_reasoner import _reference_context_messages
    current = {'original_source': 'Quelle vollständig µ', 'registered_catalogs': {'all': [1, 2]},
               'current_candidate': {'devices': [{'id': 'C'}]}}
    history = [{'role': 'system', 'content': 'system'}, {'role': 'user', 'content': 'x' * 120000},
               {'role': 'assistant', 'content': 'y' * 10000}]
    messages, full, rebased = _reference_context_messages(history, {}, current, 'system', 131072)
    assert rebased and messages == full
    assert effective_reference_context(messages) == current
    assert _reference_context_window(messages, 131072) == 131072
    with pytest.raises(ValueError, match='keine Quelle gekürzt'):
        _reference_context_messages(history, {}, {**current, 'original_source': 'x' * 131072}, 'system', 131072)


def test_reference_retry_keeps_exact_invalid_reply_and_same_current_context(monkeypatch):
    captured = []
    reasoner, prepared, _ = reasoner_with_transport(monkeypatch, capture=captured, retry_foreign_port=True, wire_padding=True)
    with pytest.raises(ValueError, match='nicht ausgewählten Teilnehmers'):
        run_reference(reasoner, prepared)
    previous, retry = captured[-2:]
    assert retry['messages'][:-2] == previous['messages']
    assert retry['messages'][-2]['role'] == 'assistant'
    assert retry['messages'][-2]['content'].startswith(' \n')
    assert retry['messages'][-2]['content'].endswith('\n ')
    assert 'Validierungsfehler:' in retry['messages'][-1]['content']
    assert effective_reference_context(retry['messages']) == effective_reference_context(previous['messages'])
    assert retry['format'] == previous['format']


@pytest.mark.parametrize('bad', ['missing', 'unknown', 'mismatched_role', 'existing_with_new_fields', 'new_with_existing_id', 'unregistered_role'])
def test_private_choice_tag_cannot_hide_or_reinterpret_a_device(bad):
    prepared = intake.prepare_reference_design(fixture_request())
    known, _ = _reference_declared_instances(prepared, prepared['facts'])
    row = {'choice_kind': 'NEW_CONTROLLER', **deepcopy(known[0]), 'id': 'new-unit-device'}
    if bad == 'missing':
        row.pop('choice_kind')
    elif bad == 'unknown':
        row['choice_kind'] = 'EXISTING_OR_NEW'
    elif bad == 'mismatched_role':
        row['choice_kind'] = 'NEW_SENSOR'
    elif bad == 'existing_with_new_fields':
        row['choice_kind'] = 'EXISTING'
    elif bad == 'new_with_existing_id':
        row['id'] = known[0]['id']
    else:
        row.update(choice_kind='NEW_UNKNOWN_ROLE', kind='UNKNOWN_ROLE')
    before = deepcopy(row)
    with pytest.raises(ValueError):
        _reference_expand_inventory_choices(known, [row])
    assert row == before


def test_native_choice_marker_and_public_device_kind_cannot_disagree():
    from jsonschema import Draft202012Validator, ValidationError
    prepared = intake.prepare_reference_design(fixture_request())
    known, _ = _reference_declared_instances(prepared, prepared['facts'])
    fact = next(key for key, row in prepared['facts'].items() if row['kind'] == 'FUNCTION')
    schema = _reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=[fact], existing_devices=known)
    row = {'choice_kind': 'NEW_SENSOR', **deepcopy(known[0]), 'id': 'new-unit-device', 'source_fact_ids': [fact]}
    assert row['kind'] == 'CONTROLLER'
    value = {**intake.ReferenceDesignProposal().model_dump(mode='json'), 'inventory_complete': True, 'inventory_choices': [row]}
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(value)
    with pytest.raises(ValueError, match='passende NEW_'):
        _reference_expand_inventory_choices(known, [row])


def wide_derivation_request(functions=5, requirements=6):
    """Authored unit source, never an amended original or product project."""
    import hashlib
    request = fixture_request(references=[reference()])
    source, envelope = request['prompt'].split('\n- Dokument-Geräte: ')
    envelope = json.loads(envelope)
    extras = [
        {'name': f'Zusatzfunktion {number}', 'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None,
         'source_quote': f'Funktion: Zusatzfunktion {number}', 'source_context': []}
        for number in range(functions)]
    extras += [
        {'name': f'REQ-EXTRA-{number}', 'kind': 'REQUIREMENT', 'role': 'OTHER', 'quantity': None,
         'source_quote': f'REQ-EXTRA-{number}: Das System MUSS Zustand {number} beobachten.', 'source_context': []}
        for number in range(requirements)]
    source += '\n' + '\n'.join(row['source_quote'] for row in extras)
    envelope.update(source_text=source, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                    source_chars=len(source))
    envelope['facts'].extend(extras)
    request['prompt'] = source + '\n- Dokument-Geräte: ' + json.dumps(envelope, ensure_ascii=False)
    return request


def wide_derivation_design(prepared):
    value = complete_design(prepared)
    represented = {row['source_fact_id'] for row in value['functions']}
    value['functions'].extend(
        {'source_fact_id': key, 'realization': 'ATOMIC', 'executor_device_ids': ['C'],
         'rationale': 'Mocked-wire unit function, not original model evidence'}
        for key, fact in prepared['facts'].items() if fact['kind'] == 'FUNCTION' and key not in represented)
    return value


@pytest.mark.parametrize(('functions', 'requirements'), [(0, 1), (5, 6), (9, 8)])
def test_derived_hardware_scopes_cover_every_fact_with_full_source_context(monkeypatch, functions, requirements):
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch,
        request=wide_derivation_request(functions, requirements), design_factory=wide_derivation_design)
    result = run_reference(reasoner, prepared)
    expected = [key for key, fact in prepared['facts'].items() if fact['kind'] in {'FUNCTION', 'REQUIREMENT'}]
    stages = [row for row in observed if row['derivation_fact_ids_for_this_stage'] is not None]
    visited = [key for row in stages for key in row['derivation_fact_ids_for_this_stage']]
    assert visited == expected and len(visited) == len(set(visited))
    assert all(1 <= len(row['derivation_fact_ids_for_this_stage']) <= 4 for row in stages)
    assert all(row['original_source'] == prepared['source_evidence']['source_text']
               and row['reference_sources'] == prepared['reference_sources']
               and set(row['original_facts']) == set(prepared['facts']) for row in stages)
    first_io = next(index for index, row in enumerate(observed) if row['device_ids_for_this_stage'])
    assert all(observed.index(row) < first_io for row in stages)
    assert set(result['coverage']['function_fact_ids']) | set(result['coverage']['requirement_fact_ids']) == set(expected)
    assert result['proposal']['unresolved'] == [] and result['canonical_writes'] is False


def test_derived_hardware_late_scopes_can_extend_existing_identity_bindings(monkeypatch):
    def reuse(candidate, content, payload, prepared):
        controller = next(row for row in content['current_candidate']['devices'] if row['kind'] == 'CONTROLLER')
        candidate['devices'] = [{**deepcopy(controller),
            'source_fact_ids': content['derivation_fact_ids_for_this_stage']}]
        candidate['inventory_complete'] = True
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch,
        request=wide_derivation_request(), design_factory=wide_derivation_design, derivation_mutator=reuse)
    result = run_reference(reasoner, prepared)
    stages = [row for row in observed if row['derivation_fact_ids_for_this_stage'] is not None]
    assert len(stages) > 1
    source_controller = next(key for key, fact in prepared['facts'].items() if fact['kind'] == 'INSTANCE')
    controllers = [row for row in result['proposal']['devices'] if source_controller in row['source_fact_ids']]
    assert len(controllers) == 1 and controllers[0]['quantity'] == 1
    expected = {key for key, fact in prepared['facts'].items() if fact['kind'] in {'FUNCTION', 'REQUIREMENT'}}
    assert set(controllers[0]['source_fact_ids']) == expected | {source_controller}
    assert len(result['proposal']['devices']) == 3


def test_repeated_early_hardware_additions_do_not_skip_remaining_fact_scopes(monkeypatch):
    def additional_sensors(prepared):
        design = wide_derivation_design(prepared)
        fact = next(key for key, row in prepared['facts'].items() if row['name'] == 'Regelung')
        for number in (2, 3, 4):
            device = 'S' + str(number)
            design['devices'].append({**deepcopy(design['devices'][1]), 'id': device,
                'name': 'Unit derived sensor ' + str(number), 'source_fact_ids': [fact]})
            design['ports'].append({**deepcopy(design['ports'][1]), 'id': 'P' + device, 'device_id': device})
            design['measurements'].append({**deepcopy(design['measurements'][0]), 'device_id': device})
            design['communication'].append({**deepcopy(design['communication'][0]), 'id': 'derived-' + device,
                'signal_name': 'derived-' + device, 'producer_device_id': device, 'source_port_id': 'P' + device})
        return design
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch,
        request=wide_derivation_request(), design_factory=additional_sensors)
    result = run_reference(reasoner, prepared)
    stages = [row for row in observed if row['derivation_fact_ids_for_this_stage'] is not None]
    scopes = [tuple(row['derivation_fact_ids_for_this_stage']) for row in stages]
    assert scopes[0] == scopes[1] == scopes[2] and len(set(scopes)) > 1
    assert all(scope != scopes[0] for scope in scopes[3:])
    assert {key for scope in scopes for key in scope} == {
        key for key, fact in prepared['facts'].items() if fact['kind'] in {'FUNCTION', 'REQUIREMENT'}}
    assert len(result['proposal']['measurements']) == 4
    assert result['proposal']['unresolved'] == []


@pytest.mark.parametrize('failure', ['no_progress', 'timeout'])
def test_derived_hardware_late_scope_failure_prevents_all_io_and_partial_result(monkeypatch, failure):
    scopes = []
    def fail_later(candidate, content, payload, prepared):
        scope = tuple(content['derivation_fact_ids_for_this_stage'])
        if not scopes or scopes[-1] != scope:
            scopes.append(scope)
        if len(scopes) > 1:
            if failure == 'timeout':
                raise httpx.ReadTimeout('Mocked late hardware stage timeout')
            candidate.update(devices=[], inventory_complete=False)
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch,
        request=wide_derivation_request(), design_factory=wide_derivation_design, derivation_mutator=fail_later)
    expected = 'Funktionsbedingte physische Hardware.*Zeitlimit' if failure == 'timeout' else 'keine fehlende ursprüngliche Geräteabdeckung'
    with pytest.raises(ValueError, match=expected):
        run_reference(reasoner, prepared)
    assert len(scopes) == 2
    assert not any(row['device_ids_for_this_stage'] or row['port_ids_for_this_stage'] for row in observed)


@pytest.mark.parametrize('kind', ['NEW_SENSOR', 'EXISTING'])
def test_derived_hardware_decoder_bounds_source_selection_and_rejects_foreign_scope(kind):
    from jsonschema import Draft202012Validator, ValidationError
    prepared = intake.prepare_reference_design(wide_derivation_request())
    known, _ = _reference_declared_instances(prepared, prepared['facts'])
    eligible = [key for key, fact in prepared['facts'].items() if fact['kind'] in {'FUNCTION', 'REQUIREMENT'}]
    selected = eligible[:4]
    schema = _reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=selected, existing_devices=known)
    if kind == 'EXISTING':
        row = {'choice_kind': kind, 'device_id': known[0]['id'], 'source_fact_ids': selected,
               'rationale': 'Mocked source binding', 'field_references': {}}
    else:
        row = {**deepcopy(known[0]), 'choice_kind': kind,
               'id': offered_new_inventory_id(schema, kind), 'name': 'Unit scoped sensor',
               'kind': 'SENSOR', 'owner_device_id': known[0]['id'], 'source_fact_ids': selected}
    value = {**intake.ReferenceDesignProposal().model_dump(mode='json'), 'inventory_complete': True, 'inventory_choices': [row]}
    validator = Draft202012Validator(schema)
    validator.validate(value)
    overlong = deepcopy(value)
    overlong['inventory_choices'][0]['source_fact_ids'] += [selected[0]]
    with pytest.raises(ValidationError):
        validator.validate(overlong)
    foreign = deepcopy(value)
    foreign['inventory_choices'][0]['source_fact_ids'][-1] = eligible[4]
    with pytest.raises(ValidationError):
        validator.validate(foreign)


@pytest.mark.parametrize('pair', ['duplicate_existing', 'distinct_existing', 'new_and_existing'])
def test_native_hardware_choice_decides_one_identity_before_continuing(pair):
    from jsonschema import Draft202012Validator, ValidationError
    prepared = intake.prepare_reference_design(fixture_request())
    known, _ = _reference_declared_instances(prepared, prepared['facts'])
    known.append({**deepcopy(known[0]), 'id': 'unit-second-existing', 'name': 'Second unit executor'})
    fact = next(key for key, row in prepared['facts'].items() if row['kind'] == 'FUNCTION')
    schema = _reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=[fact], existing_devices=known)
    first = {'choice_kind': 'EXISTING', 'device_id': known[0]['id'], 'source_fact_ids': [fact],
             'rationale': 'Authored unit identity selection, not a native original response', 'field_references': {}}
    second = deepcopy(first)
    if pair == 'distinct_existing':
        second['device_id'] = known[1]['id']
    elif pair == 'new_and_existing':
        second = {**deepcopy(known[0]), 'choice_kind': 'NEW_SENSOR', 'kind': 'SENSOR',
                  'id': offered_new_inventory_id(schema, 'NEW_SENSOR'), 'name': 'Unit derived sensor',
                  'owner_device_id': known[0]['id'], 'source_fact_ids': [fact]}
    base = {**intake.ReferenceDesignProposal().model_dump(mode='json'), 'inventory_complete': False}
    validator = Draft202012Validator(schema)
    validator.validate({**base, 'inventory_choices': [first]})
    validator.validate({**base, 'inventory_choices': [second]})
    validator.validate({**base, 'inventory_complete': True, 'inventory_choices': []})
    with pytest.raises(ValidationError) as error:
        validator.validate({**base, 'inventory_choices': [first, second]})
    assert list(error.value.path) == ['inventory_choices']


@pytest.mark.parametrize('mode', ['unknown', 'duplicate'])
def test_invalid_binding_feedback_identifies_the_actual_unknown_or_repeated_id(mode):
    prepared = intake.prepare_reference_design(fixture_request())
    known, _ = _reference_declared_instances(prepared, prepared['facts'])
    choice = {'device_id': known[0]['id'], 'source_fact_ids': known[0]['source_fact_ids'],
              'rationale': 'Authored invalid binding', 'field_references': {}}
    if mode == 'unknown':
        choice['device_id'] = 'unit-missing-identity'
        choices, expected = [choice], 'Unbekannte Teilnehmer-ID.*unit-missing-identity'
    else:
        choices, expected = [choice, deepcopy(choice)], 'Mehrfache Inventarbindung.*' + known[0]['id']
    before = deepcopy(known)
    with pytest.raises(ValueError, match=expected):
        _reference_expand_inventory_bindings(known, [], choices)
    assert known == before


@pytest.mark.parametrize('mode', ['empty', 'already_bound'])
def test_native_inventory_decoder_rejects_incomplete_without_coverage_progress(mode):
    from jsonschema import Draft202012Validator, ValidationError
    prepared = intake.prepare_reference_design(fixture_request())
    known, _ = _reference_declared_instances(prepared, prepared['facts'])
    fact = next(key for key, row in prepared['facts'].items() if row['kind'] == 'FUNCTION')
    known[0]['source_fact_ids'].append(fact)
    schema = _reference_schema_for_stage(prepared, {'devices'},
        derivation_fact_ids=[fact], existing_devices=known)
    choice = {'choice_kind': 'EXISTING', 'device_id': known[0]['id'],
              'source_fact_ids': [fact], 'rationale': 'Repeated existing binding', 'field_references': {}}
    value = {**intake.ReferenceDesignProposal().model_dump(mode='json'),
             'inventory_complete': False, 'inventory_choices': [] if mode == 'empty' else [choice]}
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(value)
    Draft202012Validator(schema).validate({**value, 'inventory_complete': True, 'inventory_choices': []})


def test_native_inventory_decoder_binds_only_missing_facts_to_each_existing_identity():
    from jsonschema import Draft202012Validator, ValidationError
    prepared = intake.prepare_reference_design(wide_derivation_request())
    known, _ = _reference_declared_instances(prepared, prepared['facts'])
    facts = [key for key, row in prepared['facts'].items() if row['kind'] == 'FUNCTION'][:2]
    assert len(facts) == 2
    known[0]['source_fact_ids'].append(facts[0])
    schema = _reference_schema_for_stage(prepared, {'devices'},
        derivation_fact_ids=facts, existing_devices=known)
    validator = Draft202012Validator(schema)
    base = {**intake.ReferenceDesignProposal().model_dump(mode='json'), 'inventory_complete': False}
    choice = {'choice_kind': 'EXISTING', 'device_id': known[0]['id'],
              'source_fact_ids': [facts[1]], 'rationale': 'Additional source binding', 'field_references': {}}
    validator.validate({**base, 'inventory_choices': [choice]})
    with pytest.raises(ValidationError):
        validator.validate({**base, 'inventory_choices': [{**choice, 'source_fact_ids': [facts[0]]}]})
    expanded = _reference_expand_inventory_choices(known, [choice])
    delta = _reference_scoped_inventory_delta(known, expanded, derivation_fact_ids=facts)
    assert set(delta[0]['source_fact_ids']) == set(known[0]['source_fact_ids']) | {facts[1]}


def test_native_inventory_terminal_failure_retains_exact_local_response_diagnostic(monkeypatch, caplog):
    import hashlib
    def no_progress(candidate, content, payload, prepared):
        candidate.update(devices=[], inventory_complete=False)
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch, derivation_mutator=no_progress)
    with pytest.raises(ValueError, match='keine fehlende ursprüngliche Geräteabdeckung'):
        run_reference(reasoner, prepared)
    records = [row for row in caplog.records if row.msg == 'Native reference validation failed: %s']
    assert len(records) == 1
    diagnostic = json.loads(records[0].args[0])
    assert diagnostic['stage'] == 'Funktionsbedingte physische Hardware'
    assert diagnostic['derivation_fact_ids']
    raw = diagnostic['response']
    assert hashlib.sha256(raw.encode()).hexdigest() == diagnostic['response_sha256']
    assert json.loads(raw)['inventory_complete'] is False
    assert json.loads(raw)['inventory_choices'] == []


@pytest.mark.parametrize('collision', ['same_kind', 'cross_kind', 'already_bound'])
def test_native_new_identity_decoder_excludes_every_existing_id(collision):
    """Authored probe: decoder admission must agree with the unchanged guard."""
    from jsonschema import Draft202012Validator
    prepared = intake.prepare_reference_design(fixture_request())
    known = complete_design(prepared)['devices']
    fact = next(key for key, item in prepared['facts'].items() if item['kind'] == 'FUNCTION')
    sensor = next(row for row in known if row['kind'] == 'SENSOR')
    old_id = next(row['id'] for row in known if row['kind'] == 'CONTROLLER') if collision == 'cross_kind' else sensor['id']
    if collision == 'already_bound':
        sensor['source_fact_ids'].append(fact)
    row = {**deepcopy(sensor), 'choice_kind': 'NEW_SENSOR', 'id': old_id,
           'name': 'Authored probe sensor', 'source_fact_ids': [fact],
           'source_member_bindings': {}, 'rationale': 'Independent decoder counterexample'}
    value = {**intake.ReferenceDesignProposal().model_dump(mode='json'),
             'inventory_complete': False, 'inventory_choices': [row]}
    schema = _reference_schema_for_stage(prepared, {'devices'},
        derivation_fact_ids=[fact], existing_devices=known)
    before = deepcopy(known)
    with pytest.raises(ValueError, match='Vorhandene Teilnehmer ausschließlich als ID-Bindung'):
        _reference_expand_inventory_choices(known, [row])
    assert known == before
    assert not Draft202012Validator(schema).is_valid(value), 'NEW must not emit any allocated identity.'


def test_inventory_prompt_exposes_exact_existing_identity_projection(monkeypatch):
    reasoner, prepared, observed = reasoner_with_transport(monkeypatch)
    run_reference(reasoner, prepared)
    inventory = [content for content in observed
                 if content['inventory_target_for_this_stage'] is not None
                 or content['derivation_fact_ids_for_this_stage'] is not None]
    assert inventory
    for content in inventory:
        assert content['existing_inventory_for_this_stage'] == [
            {key: row[key] for key in ('id', 'name', 'kind')}
            for row in content['current_candidate']['devices']]


def test_rejected_new_identity_feedback_identifies_the_existing_participant():
    prepared = intake.prepare_reference_design(fixture_request())
    known = complete_design(prepared)['devices']
    sensor = next(row for row in known if row['kind'] == 'SENSOR')
    with pytest.raises(ValueError) as error:
        _reference_expand_inventory_choices(known, [{**deepcopy(sensor), 'choice_kind': 'NEW_SENSOR'}])
    assert sensor['id'] in str(error.value)
    assert sensor['name'] in str(error.value)
    assert sensor['kind'] in str(error.value)


@pytest.mark.parametrize('used', [[], ['a', 'ab', 'ba'], ['a\n', 'é', '[x]', '🙂', 'a\\b'], ['x' * 120]])
def test_native_fresh_inventory_ids_are_stable_distinct_and_preserve_existing_ids(used):
    from backend.nis.agent.orchestration.local_reasoner import _reference_fresh_inventory_id
    from backend.nis.agent.orchestration.project_intake import ReferenceDevice
    prepared = intake.prepare_reference_design(fixture_request())
    facts = list(prepared['facts'])[:2]
    before = deepcopy(used)
    first = _reference_fresh_inventory_id(prepared, 'SENSOR', facts, set(used))
    assert first not in used and 1 <= len(first) <= 120
    assert first == _reference_fresh_inventory_id(prepared, 'SENSOR', reversed(facts), set(reversed(used)))
    assert first != _reference_fresh_inventory_id(prepared, 'ACTUATOR', facts, set(used))
    assert first != _reference_fresh_inventory_id(prepared, 'SENSOR', facts[:1], set(used))
    # Public persisted identities keep the complete original domain. Existing
    # arbitrary identities are not rewritten to the newly offered private ID.
    sensor = next(row for row in complete_design(prepared)['devices'] if row['kind'] == 'SENSOR')
    for identifier in used + ['quoted"id', 'a\n', 'a\\b', 'é', '🙂']:
        ReferenceDevice.model_validate({**sensor, 'id': identifier})
    assert used == before


def test_native_fresh_inventory_id_resolves_actual_allocated_collision(monkeypatch):
    import hashlib
    from backend.nis.agent.orchestration.local_reasoner import _reference_fresh_inventory_id
    prepared = intake.prepare_reference_design(fixture_request())
    class Digest:
        def hexdigest(self):
            return 'a' * 64
    monkeypatch.setattr(hashlib, 'sha256', lambda value: Digest())
    used = {'derived-' + 'a' * 24, 'derived-' + 'a' * 24 + '-1'}
    assert _reference_fresh_inventory_id(prepared, 'SENSOR', list(prepared['facts'])[:1], used) == 'derived-' + 'a' * 24 + '-2'
