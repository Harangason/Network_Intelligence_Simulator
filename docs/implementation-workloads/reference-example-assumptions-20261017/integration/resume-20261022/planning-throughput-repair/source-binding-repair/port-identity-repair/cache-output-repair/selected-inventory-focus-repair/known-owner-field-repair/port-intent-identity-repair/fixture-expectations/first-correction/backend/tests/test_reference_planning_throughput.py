"""Independent private-wire checks; no original-model or native acceptance claim."""
import asyncio
from copy import deepcopy
import json

import httpx
import pytest
from jsonschema import Draft202012Validator, ValidationError

from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_design import fixture_request


def unpack_context_message(value):
    """Independent receiver for the documented table/copy wire representation."""
    if 'nis_context_snapshot' not in value:
        return value
    document = deepcopy(value['nis_context_snapshot'])

    def location(pointer):
        keys = [key.replace('~1', '/').replace('~0', '~') for key in pointer[1:].split('/')]
        parent = document
        for key in keys[:-1]:
            parent = parent[int(key)] if isinstance(parent, list) else parent[key]
        return parent, int(keys[-1]) if isinstance(parent, list) else keys[-1]

    for path in value['nis_context_tables']:
        parent, key = location(path)
        table = parent[key]
        records = [{**deepcopy(table['constants']), **dict(zip(table['columns'], row, strict=True))}
                   for row in table['rows']]
        parent[key] = dict(zip(table['keys'], records, strict=True)) if 'keys' in table else records
    for operation in value['nis_context_copies']:
        assert operation['op'] == 'copy'
        source, source_key = location(operation['from'])
        parent, key = location(operation['path'])
        parent[key] = deepcopy(source[source_key])
    return document


def context_with_repeated_records():
    rows = [{'id': f'device-{index}', 'name': f'Messgerät {index} µ 🦾', 'kind': 'SENSOR',
             'quantity': 1, 'context_kind': None, 'source_fact_ids': [f'F{index}'],
             'source_context': ['Originalbereich mit unveränderter räumlicher Identität'] * 4,
             'rationale': 'Vollständige unabhängig verfasste Begründung, kein Hardwarebeleg.',
             'owner_device_id': 'controller-original', 'field_references': {}, 'contained_device_ids': []}
            for index in range(80)]
    return {'original_source': 'Unveränderte Quelle\r\nµ 🦾 /~',
            'reference_sources': {'R': {'allowed_fields': ['ports'], 'text': 'Originalreferenz vollständig'}},
            'current_candidate': {'devices': rows}, 'empty': [], 'bool': True, 'number': 1,
            'literal_collision': {'nis_context_snapshot': {'columns': [], 'rows': []}},
            'a/b~c': {'': rows[:2]}}


def test_private_context_transport_is_lossless_and_smaller_without_changing_guard():
    original = context_with_repeated_records()
    before = deepcopy(original)
    assert hasattr(reasoner, '_reference_context_snapshot'), 'Missing lossless repeated-record transport'
    packed = reasoner._reference_context_snapshot(original)
    assert unpack_context_message(packed) == original
    assert original == before
    plain = json.dumps(original, ensure_ascii=False, separators=(',', ':'))
    wire = json.dumps(packed, ensure_ascii=False, separators=(',', ':'))
    assert len(wire.encode()) < len(plain.encode()) * 0.65
    maximum = len(wire.encode()) + 8192 + 2048
    assert reasoner._reference_context_window([{'content': wire}], maximum) == maximum
    with pytest.raises(ValueError, match='keine Quelle gekürzt'):
        reasoner._reference_context_window([{'content': wire}], maximum - 1)


@pytest.mark.parametrize('value', [
    {'rows': [{'x': False}, {'x': 0}, {'x': None}, {'x': '0'}]},
    {'rows': [{'x': 1}, {'y': 2}], 'empty': {}, 'null': None},
    {'maps': {'a': {'field': 'A'}, 'b': {'field': 'B'}}, 'source': 'exact\r\n'},
])
def test_private_transport_preserves_types_missing_keys_and_literal_envelopes(value):
    assert hasattr(reasoner, '_reference_context_snapshot')
    assert json.dumps(unpack_context_message(reasoner._reference_context_snapshot(value)), sort_keys=True) == json.dumps(value, sort_keys=True)


def existing_batch_fixture():
    prepared = intake.prepare_reference_design(fixture_request())
    known, _ = reasoner._reference_declared_instances(prepared, prepared['facts'])
    known = [{**deepcopy(known[0]), 'id': f'existing-{index}', 'name': f'Known controller {index}'} for index in range(9)]
    fact = next(key for key, row in prepared['facts'].items() if row['kind'] == 'FUNCTION')
    choices = [{'choice_kind': 'EXISTING', 'device_id': row['id'], 'source_fact_ids': [fact],
                'rationale': 'Source-bound unit decision', 'field_references': {}} for row in known]
    schema = reasoner._reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=[fact], existing_devices=known)
    base = {**intake.ReferenceDesignProposal().model_dump(mode='json'), 'inventory_complete': False}
    return prepared, known, fact, choices, schema, base


def test_native_decoder_accepts_eight_known_bindings_but_rejects_nine():
    from backend.tests.test_reference_reasoner import native_existing_bindings
    _, known, _, choices, schema, base = existing_batch_fixture()
    validator = Draft202012Validator(schema)
    validator.validate({**base, 'inventory_choices': [native_existing_bindings(choices[:8])]})
    with pytest.raises(ValidationError):
        validator.validate({**base, 'inventory_choices': [native_existing_bindings(choices)]})
    expanded = reasoner._reference_expand_inventory_choices(known, choices[:8])
    assert [row['id'] for row in expanded] == [row['id'] for row in known[:8]]
    assert all(row['name'] == known[index]['name'] for index, row in enumerate(expanded))


@pytest.mark.parametrize('invalid', ['duplicate', 'unknown', 'mixed_new', 'nine'])
def test_existing_binding_batch_runtime_rejects_invalid_without_mutation(invalid):
    _, known, fact, choices, _, _ = existing_batch_fixture()
    rows = deepcopy(choices[:2])
    if invalid == 'duplicate':
        rows[1] = deepcopy(rows[0])
    elif invalid == 'unknown':
        rows[1]['device_id'] = 'not-in-current-inventory'
    elif invalid == 'mixed_new':
        rows[1] = {**deepcopy(known[0]), 'choice_kind': 'NEW_CONTROLLER', 'id': 'new-unit', 'source_fact_ids': [fact]}
    else:
        rows = choices
    before = deepcopy(known)
    with pytest.raises(ValueError):
        reasoner._reference_expand_inventory_choices(known, rows)
    assert known == before


def test_native_reference_stream_reports_only_actual_received_content_and_final_metrics():
    assert hasattr(reasoner, '_reference_stream_response'), 'Blocking POST exposes no actual output progress'
    events = []
    payload = {'stream': True}
    bodies = [{'message': {'content': '{"'}, 'done': False},
              {'message': {'content': 'µ":"🦾"}'}, 'done': False},
              {'message': {'content': ''}, 'done': True, 'eval_count': 7, 'prompt_eval_count': 31}]
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(
                200, content='\n'.join(json.dumps(row, ensure_ascii=False) for row in bodies)))) as client:
            return await reasoner._reference_stream_response(client, 'http://unit/chat', payload, events.append)
    result = asyncio.run(run())
    assert result['message']['content'] == '{"µ":"🦾"}'
    assert result['eval_count'] == 7 and result['prompt_eval_count'] == 31
    assert events and events[-1]['received_characters'] == len('{"µ":"🦾"}')
    assert all(row['received_characters'] >= 0 for row in events)


@pytest.mark.parametrize('body', ['{"message":{"content":"partial"},"done":false}\n', '{"error":"native failed"}\n', 'invalid-json\n'])
def test_native_reference_stream_rejects_incomplete_error_and_malformed_output(body):
    assert hasattr(reasoner, '_reference_stream_response')
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=body))) as client:
            await reasoner._reference_stream_response(client, 'http://unit/chat', {'stream': True}, lambda event: None)
    with pytest.raises((ValueError, RuntimeError)):
        asyncio.run(run())


def test_reference_stream_pulses_during_header_wait_and_stops_after_completion():
    events = []
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        async def handler(request):
            entered.set()
            await release.wait()
            return httpx.Response(200, json={'done': True, 'message': {'content': '{}'}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            task = asyncio.create_task(reasoner._reference_stream_response(client, 'http://unit/chat', {'stream': True}, events.append))
            await entered.wait()
            await asyncio.sleep(10.1)
            waiting = deepcopy(events)
            release.set()
            await task
            completed_count = len(events)
            await asyncio.sleep(0.05)
            assert len(events) == completed_count
            return waiting
    waiting = asyncio.run(run())
    assert len(waiting) >= 2
    assert all(row['request_state'] == 'WAITING_FOR_PROVIDER' and row['received_characters'] == 0 for row in waiting)


def two_sensor_design(prepared):
    from backend.tests.test_reference_reasoner import complete_design
    value = complete_design(prepared)
    sensor = next(row for row in value['devices'] if row['kind'] == 'SENSOR')
    value['devices'].append({**deepcopy(sensor), 'id': 'S2', 'name': 'Second temperature sensor'})
    value['ports'].append({**deepcopy(next(row for row in value['ports'] if row['device_id'] == 'S')), 'id': 'PS2', 'device_id': 'S2'})
    value['measurements'].append({**deepcopy(value['measurements'][0]), 'device_id': 'S2'})
    row = next(row for row in value['communication'] if row['producer_device_id'] == 'S')
    value['communication'].append({**deepcopy(row), 'id': 'temperature-second', 'signal_name': 'temperature-second',
                                   'producer_device_id': 'S2', 'source_port_id': 'PS2'})
    return value


def test_io_batch_keeps_both_sensor_ids_and_complete_validated_result(monkeypatch):
    from backend.tests.test_reference_reasoner import reasoner_with_transport, run_reference
    instance, prepared, observed = reasoner_with_transport(monkeypatch, design_factory=two_sensor_design)
    result = run_reference(instance, prepared)
    sensor_stages = [row for row in observed if row['output_fields_for_this_stage'] == ['measurements']]
    assert len(sensor_stages) == 1
    assert len(sensor_stages[0]['device_ids_for_this_stage']) == 2
    assert len(result['proposal']['measurements']) == 2
    assert result['proposal']['unresolved'] == [] and result['canonical_writes'] is False


def test_io_batch_rejects_foreign_owner_alongside_two_selected_sensors(monkeypatch):
    from backend.tests.test_reference_reasoner import reasoner_with_transport, run_reference
    instance, prepared, _ = reasoner_with_transport(monkeypatch, design_factory=two_sensor_design, foreign_io='measurements')
    with pytest.raises(ValueError, match='nicht ausgewählten Teilnehmers'):
        run_reference(instance, prepared)


def test_io_and_parameter_batches_keep_all_peers_and_prior_parameters(monkeypatch):
    from backend.tests.test_reference_reasoner import reasoner_with_transport, run_reference
    def several_sensors(prepared):
        value = two_sensor_design(prepared)
        sensor = next(row for row in value['devices'] if row['id'] == 'S')
        port = next(row for row in value['ports'] if row['id'] == 'PS')
        tx = next(row for row in value['communication'] if row['producer_device_id'] == 'S')
        for index in range(3, 6):
            key = 'S' + str(index)
            value['devices'].append({**deepcopy(sensor), 'id': key, 'name': f'Additional temperature sensor {index}'})
            value['ports'].append({**deepcopy(port), 'id': 'P' + key, 'device_id': key})
            value['measurements'].append({**deepcopy(value['measurements'][0]), 'device_id': key})
            value['communication'].append({**deepcopy(tx), 'id': 'temperature-' + key, 'signal_name': 'temperature-' + key,
                                           'producer_device_id': key, 'source_port_id': 'P' + key})
        return value
    instance, prepared, observed = reasoner_with_transport(monkeypatch, design_factory=several_sensors)
    result = run_reference(instance, prepared)
    parameter_stages = [row for row in observed if row['port_ids_for_this_stage']]
    before_parameters = parameter_stages[0]['current_candidate']['ports']
    expected = {row['id'] for row in before_parameters}
    assert len(expected) == len(before_parameters) == 7
    assert {row['device_id'] for row in before_parameters} == {
        row['id'] for row in parameter_stages[0]['current_candidate']['devices'] if row['kind'] != 'PHYSICAL_CONTEXT'}
    assert [len(row['port_ids_for_this_stage']) for row in parameter_stages] == [4, 3]
    assert set().union(*(set(row['port_ids_for_this_stage']) for row in parameter_stages)) == expected
    assert all({port['id'] for port in row['current_candidate']['ports']} == expected for row in parameter_stages)
    previous = set(parameter_stages[0]['port_ids_for_this_stage'])
    assert all(port['parameters'] == {'bitrate_bps': 500000}
               for port in parameter_stages[1]['current_candidate']['ports'] if port['id'] in previous)
    identity_fields = ('id', 'device_id', 'technology', 'role', 'network_scope')
    identities = {tuple(row[key] for key in identity_fields) for row in before_parameters}
    assert all({tuple(row[key] for key in identity_fields) for row in stage['current_candidate']['ports']} == identities
               for stage in parameter_stages)
    assert {tuple(row[key] for key in identity_fields) for row in result['proposal']['ports']} == identities
    sensors = [row for row in observed if row['output_fields_for_this_stage'] == ['measurements']]
    assert [len(row['device_ids_for_this_stage']) for row in sensors] == [4, 1]
    assert len(result['proposal']['ports']) == 7 and len(result['proposal']['measurements']) == 5
    assert result['proposal']['unresolved'] == [] and result['canonical_writes'] is False


def test_history_rebase_preserves_actual_native_anchor_and_complete_current_state():
    from backend.tests.test_reference_reasoner import effective_reference_context
    context = context_with_repeated_records()
    first, _, _ = reasoner._reference_context_messages([], None, context, 'system', 131072)
    # Authored unit wire; the actual production anchor must use its real reply.
    anchor_messages = [*deepcopy(first), {'role': 'assistant', 'content': ' {"unit_actual_reply":true}\n'}]
    history = [*deepcopy(anchor_messages), {'role': 'user', 'content': 'x' * 125000}]
    current = deepcopy(context)
    current['current_candidate']['devices'][79]['source_fact_ids'].append('new-source-binding')
    current['planning_stage'] = 'Parameters'
    messages, fallback, rebased = reasoner._reference_context_messages(
        history, context, current, 'system', 131072, anchor=(anchor_messages, context))
    assert rebased
    assert messages[:len(anchor_messages)] == anchor_messages
    assert messages == fallback and effective_reference_context(messages) == current
    assert history[-1]['content'] == 'x' * 125000 and context['current_candidate']['devices'][79]['source_fact_ids'] == ['F79']


def test_complete_snapshot_fallback_refreshes_actual_validated_native_anchor(monkeypatch):
    from backend.tests.test_reference_reasoner import reasoner_with_transport, run_reference
    actual_builder = reasoner._reference_context_messages
    observed_anchors, captured = [], []
    def once_fresh(history, previous, current, system, maximum, *, anchor=None, anchors=()):
        observed_anchors.append(deepcopy(anchor))
        if len(observed_anchors) == 2:
            messages, full, _ = actual_builder([], None, current, system, maximum)
            return messages, full, True
        return actual_builder(history, previous, current, system, maximum, anchor=anchor, anchors=anchors)
    monkeypatch.setattr(reasoner, '_reference_context_messages', once_fresh)
    instance, prepared, observed = reasoner_with_transport(monkeypatch, capture=captured, wire_padding=True)
    result = run_reference(instance, prepared)
    assert observed_anchors[2][1] == observed[1]
    assert observed_anchors[2][0][:-1] == captured[1]['messages']
    assert observed_anchors[2][0][-1]['role'] == 'assistant'
    assert observed_anchors[2][0][-1]['content'].startswith(' \n') and observed_anchors[2][0][-1]['content'].endswith('\n ')
    assert result['proposal']['unresolved'] == [] and result['canonical_writes'] is False
