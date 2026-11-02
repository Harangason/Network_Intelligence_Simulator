"""Independent context/output counterexamples, never original acceptance evidence."""
from copy import deepcopy
import inspect
import hashlib
import json

import pytest
from jsonschema import Draft202012Validator, ValidationError

from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_design import fixture_request, reference


def anchor_fixture():
    early = {'original_source': 'Original\r\nµ 🦾 /~' + 's' * 30000,
             'current_candidate': {'devices': []}, 'typed': [False, 0, None]}
    messages, _, _ = reasoner._reference_context_messages([], None, early, 'system', 131072)
    older = ([*messages, {'role': 'assistant', 'content': ' {"unit_actual_reply":true}\n'}], early)
    latest = deepcopy(early)
    latest['current_candidate']['notes'] = 'l' * 65000
    messages, _, _ = reasoner._reference_context_messages([], None, latest, 'system', 131072)
    # Authored whitespace models the exact native text that must be retained.
    newer = ([*messages, {'role': 'assistant', 'content': ' ' * 35000 + '{"unit_actual_reply":true}\n'}], latest)
    current = deepcopy(latest)
    current['planning_stage'] = 'Following complete decision'
    return older, newer, current


def with_older_anchor(history, previous, current, newest, older):
    kwargs = {'anchor': newest}
    # Exercise the old implementation too: its sole anchor loses this prefix.
    if 'anchors' in inspect.signature(reasoner._reference_context_messages).parameters:
        kwargs['anchors'] = (older,)
    return reasoner._reference_context_messages(history, previous, current, 'system', 131072, **kwargs)


def test_fitting_older_native_anchor_precedes_full_snapshot_fallback():
    from backend.tests.test_reference_reasoner import effective_reference_context
    older, newer, current = anchor_fixture()
    original = deepcopy((older, newer, current))
    history = [*newer[0], {'role': 'user', 'content': 'x' * 125000}]
    messages, fallback, rebased = with_older_anchor(history, newer[1], current, newer, older)
    assert rebased and messages == fallback
    assert messages[:len(older[0])] == older[0], 'A fitting complete native prefix was discarded'
    assert effective_reference_context(messages) == current
    assert reasoner._reference_context_window(messages, 131072) == 131072
    assert (older, newer, current) == original


def test_no_fitting_anchor_uses_complete_snapshot_without_dropping_source():
    from backend.tests.test_reference_reasoner import effective_reference_context
    older, newer, current = anchor_fixture()
    oversized = ([*older[0], {'role': 'user', 'content': 'x' * 125000}], older[1])
    messages, _, rebased = with_older_anchor(newer[0], newer[1], current, newer, oversized)
    assert rebased and len(messages) == 2
    assert effective_reference_context(messages) == current


def test_no_anchor_can_make_oversized_complete_source_acceptable():
    older, newer, current = anchor_fixture()
    current['original_source'] += 'm' * 131072
    with pytest.raises(ValueError, match='keine Quelle gekürzt'):
        with_older_anchor(newer[0], newer[1], current, newer, older)


def test_compact_complete_anchor_avoids_duplicate_history_even_when_both_fit():
    from backend.tests.test_reference_reasoner import effective_reference_context
    context = {'original_source': 'Complete unchanged original\r\nµ 🦾' + 's' * 30000,
               'current_candidate': {'notes': ''}, 'typed': [False, 0, None]}
    first, _, _ = reasoner._reference_context_messages([], None, context, 'system', 131072)
    anchor_messages = [*first, {'role': 'assistant', 'content': ' {"unit_actual_reply":true}\n'}]
    previous = deepcopy(context)
    previous['current_candidate']['notes'] = 'x' * 10000
    before, _, _ = reasoner._reference_context_messages(
        anchor_messages, context, previous, 'system', 131072, anchor=(anchor_messages, context))
    history = [*before, {'role': 'assistant', 'content': ' ' * 8000 + '{"unit_actual_reply":true}\n'}]
    unchanged_history = deepcopy(history)
    current = deepcopy(previous)
    current['planning_stage'] = 'Next bounded source decision'
    messages, _, rebased = reasoner._reference_context_messages(
        history, previous, current, 'system', 131072, anchor=(anchor_messages, context))
    assert reasoner._reference_context_window(history, 131072) == 131072
    assert rebased, 'A fitting but unnecessarily duplicated reply history was replayed'
    assert sum(len(row['content'].encode('utf8')) for row in messages) < sum(
        len(row['content'].encode('utf8')) for row in history)
    assert messages[:len(anchor_messages)] == anchor_messages
    assert effective_reference_context(messages) == current
    assert history == unchanged_history


def measurement_case(fields=('measurements',)):
    prepared = intake.prepare_reference_design(fixture_request(references=[reference(fields)]))
    schema = reasoner._reference_schema_for_stage(prepared, {'measurements'}, device_ids=('sensor',))
    body = intake.ReferenceDesignProposal().model_dump(mode='json')
    body['measurements'] = [{'device_id': 'sensor', 'measurement_id': 'temperature',
                             'rationale': 'Registered measurement for the original source.',
                             'field_references': {}}]
    return prepared, schema, body


def decoder_without_property_names(value):
    """Independent counterpart of the observed unsupported-key native reply."""
    if isinstance(value, dict):
        return {key: decoder_without_property_names(item) for key, item in value.items()
                if key != 'propertyNames'}
    if isinstance(value, list):
        return [decoder_without_property_names(item) for item in value]
    return value


def test_literal_field_keys_exclude_actual_factid_key_without_property_names():
    prepared, schema, body = measurement_case()
    fact = next(iter(prepared['facts']))
    body['measurements'][0]['field_references'] = {fact: ['R1']}
    with pytest.raises(ValidationError):
        Draft202012Validator(decoder_without_property_names(schema)).validate(body)


@pytest.mark.parametrize('references', [{'measurements': ['unknown']}, {'commands': ['R1']}])
def test_decoder_excludes_unknown_or_field_disallowed_reference(references):
    _, schema, body = measurement_case()
    body['measurements'][0]['field_references'] = references
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(body)


def test_allowed_reference_pair_and_empty_map_survive_private_projection():
    prepared, schema, body = measurement_case()
    Draft202012Validator(schema).validate(body)
    body['measurements'][0]['field_references'] = {'measurements': ['R1']}
    Draft202012Validator(schema).validate(body)
    references = schema['$defs']['ReferenceMeasurement']['properties']['field_references']
    assert references['additionalProperties'] is False
    assert references['properties']['measurements']['items']['enum'] == ['R1']
    assert prepared['reference_sources']['R1']['allowed_fields'] == ['measurements']


def test_private_rationale_rejects_observed_verbose_size_public_schema_unchanged():
    prepared, schema, body = measurement_case()
    public = deepcopy(intake.reference_design_schema(prepared))
    body['measurements'][0]['rationale'] = 'a' * 641
    intake.ReferenceDesignProposal.model_validate(body)
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(body)
    assert intake.reference_design_schema(prepared) == public
    assert public['$defs']['ReferenceMeasurement']['properties']['rationale']['maxLength'] == 2000


def test_concise_private_rationale_preserves_complete_public_choice():
    _, schema, body = measurement_case()
    body['measurements'][0]['rationale'] = 'a' * 240
    Draft202012Validator(schema).validate(body)
    validated = intake.ReferenceDesignProposal.model_validate(body).model_dump(mode='json')
    assert validated['measurements'] == body['measurements']


@pytest.mark.parametrize('additional_functions', [0, 6])
def test_function_progress_reports_actual_group_and_all_original_ids(monkeypatch, additional_functions):
    from backend.nis.engineering.goal_execution.progress import sink
    from backend.tests.test_reference_reasoner import complete_design, reasoner_with_transport, run_reference
    request = fixture_request()
    source, raw = request['prompt'].split('\n- Dokument-Geräte: ')
    envelope = json.loads(raw)
    for index in range(additional_functions):
        name = f'Zusatzfunktion {index}'
        quote = 'Funktion: ' + name
        source += '\n' + quote
        envelope['facts'].append({'name': name, 'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None,
                                  'source_quote': quote, 'source_context': []})
    envelope.update(source_text=source, source_chars=len(source),
                    source_sha256=hashlib.sha256(source.encode()).hexdigest())
    request['prompt'] = source + '\n- Dokument-Geräte: ' + json.dumps(envelope, ensure_ascii=False)
    def design(prepared):
        value = complete_design(prepared)
        value['functions'] = [{'source_fact_id': key, 'realization': 'ATOMIC', 'executor_device_ids': ['C'],
                               'rationale': 'Independent authored function fixture'}
                              for key, fact in prepared['facts'].items() if fact['kind'] == 'FUNCTION']
        return value
    instance, prepared, _ = reasoner_with_transport(monkeypatch, request=request, design_factory=design)
    events = []
    token = sink.set(events.append)
    try:
        result = run_reference(instance, prepared)
    finally:
        sink.reset(token)
    functions = [event for event in events if event.get('metadata', {}).get('source') == 'document_reference_design'
                 and event['metadata'].get('selected_function_fact_ids')]
    expected = {key for key, fact in prepared['facts'].items() if fact['kind'] == 'FUNCTION'}
    assert functions
    assert {key for event in functions for key in event['metadata']['selected_function_fact_ids']} == expected
    count = 1 if additional_functions == 0 else 3
    assert [event['metadata'].get('scope_index') for event in functions] == list(range(1, count + 1))
    for index, event in enumerate(functions, 1):
        assert event['metadata'].get('scope_count') == count
        assert f'Funktionsgruppe {index} von {count}' in event['text']
        assert event['metadata']['canonical_writes'] is False
    assert result['canonical_writes'] is False


def test_planner_retains_bounded_original_and_recent_actual_native_anchors(monkeypatch):
    from backend.tests.test_reference_reasoner import reasoner_with_transport, run_reference
    actual_builder = reasoner._reference_context_messages
    observed = []
    def fresh(history, previous, current, system, maximum, *, anchor=None, anchors=()):
        observed.append(deepcopy((anchor, anchors)))
        if history:
            messages, full, _ = actual_builder([], None, current, system, maximum)
            return messages, full, True
        return actual_builder(history, previous, current, system, maximum, anchor=anchor, anchors=anchors)
    monkeypatch.setattr(reasoner, '_reference_context_messages', fresh)
    instance, prepared, _ = reasoner_with_transport(monkeypatch, wire_padding=True)
    result = run_reference(instance, prepared)
    first_native_anchor = observed[1][0]
    assert len(observed) > 8
    assert observed[3][1][0] == first_native_anchor
    assert observed[-1][1][0] == first_native_anchor
    assert all(len(older) <= 7 for _, older in observed)
    assert first_native_anchor[0][-1]['content'].startswith(' \n')
    assert result['canonical_writes'] is False
