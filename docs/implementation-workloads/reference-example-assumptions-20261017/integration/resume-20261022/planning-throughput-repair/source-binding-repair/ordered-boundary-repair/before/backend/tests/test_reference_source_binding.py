"""Independent reproductions of actual native source/identity failures."""
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, ValidationError

from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_planning_throughput import existing_batch_fixture


@pytest.mark.parametrize('caption', ['1. Einleitung und Zweck', 'Introduction and purpose', 'Index', 'Table of contents'])
def test_introduction_is_a_semantic_chapter_not_a_separate_system(caption):
    assert intake.document_system_scope([caption]) == []
    assert intake.document_system_scope(['Robot 054', caption]) == ['Robot 054']
    assert intake.document_system_scope(['Medical introduction gateway']) == ['Medical introduction gateway']


def test_source_projection_retains_unrecognized_sections_and_separates_profiles():
    source = '# Portfolio\r\nShared µ\r\n## Robot 054\r\nA\r\n### Unknown purpose\r\nExact 🦾\r\n## Vehicle 021\r\nB\r\n### Unusual section\r\nMedical gateway\r\n'
    profiles = [('Portfolio', 'Robot 054'), ('Portfolio', 'Vehicle 021')]
    actual = reasoner._reference_profile_sources(source, profiles)
    assert actual[profiles[0]] == '# Portfolio\r\nShared µ\r\n## Robot 054\r\nA\r\n### Unknown purpose\r\nExact 🦾\r\n'
    assert actual[profiles[1]] == '# Portfolio\r\nShared µ\r\n## Vehicle 021\r\nB\r\n### Unusual section\r\nMedical gateway\r\n'
    assert reasoner._reference_profile_sources('Preamble\r\n## Unknown intro\r\nText\r\n', [()])[()] == 'Preamble\r\n## Unknown intro\r\nText\r\n'
    with pytest.raises(ValueError, match='Quellenabschnitt'):
        reasoner._reference_profile_sources(source + '## Unowned system\nUnreviewed\n', profiles)


def test_native_keyed_bindings_preserve_eight_identities_and_missing_fact_sets():
    _, known, fact, choices, schema, base = existing_batch_fixture()
    keyed = {'choice_kind': 'EXISTING_BATCH', 'bindings': {
        row['device_id']: {key: value for key, value in row.items() if key not in {'choice_kind', 'device_id'}}
        for row in choices[:8]}}
    Draft202012Validator(schema).validate({**base, 'inventory_choices': [keyed]})
    expanded = reasoner._reference_expand_inventory_choices(known, [keyed])
    assert [row['id'] for row in expanded] == [row['id'] for row in known[:8]]
    assert all(fact in row['source_fact_ids'] for row in expanded)
    assert all(row['name'] == known[index]['name'] for index, row in enumerate(expanded))
    nine = deepcopy(keyed)
    nine['bindings'][choices[8]['device_id']] = keyed['bindings'][choices[0]['device_id']]
    for invalid in (nine, {'choice_kind': 'EXISTING_BATCH', 'bindings': {'foreign': next(iter(keyed['bindings'].values()))}}):
        with pytest.raises(ValidationError):
            Draft202012Validator(schema).validate({**base, 'inventory_choices': [invalid]})
        with pytest.raises(ValueError):
            reasoner._reference_expand_inventory_choices(known, [invalid])


def test_native_decoder_rejects_duplicate_identity_even_when_facts_differ():
    prepared, known, fact, choices, _, base = existing_batch_fixture()
    other = 'F-independent-second-function'
    prepared['facts'][other] = deepcopy(prepared['facts'][fact])
    prepared['fact_id_map'][other] = 'independent-source-identity-second-function'
    schema = reasoner._reference_schema_for_stage(prepared, {'devices'}, derivation_fact_ids=[fact, other], existing_devices=known)
    second = {**deepcopy(choices[0]), 'source_fact_ids': [other]}
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate({**base, 'inventory_choices': [choices[0], second]})
    with pytest.raises(ValueError, match='Mehrfache Inventarbindung'):
        reasoner._reference_expand_inventory_choices(known, [choices[0], second])
    combined = {'choice_kind': 'EXISTING_BATCH', 'bindings': {known[0]['id']: {
        'source_fact_ids': [fact, other], 'rationale': 'Both distinct source obligations on one existing participant', 'field_references': {}}}}
    Draft202012Validator(schema).validate({**base, 'inventory_choices': [combined]})
    duplicate_keys = '{"inventory_choices":[{"choice_kind":"EXISTING_BATCH","bindings":{"same":{},"same":{}}}]}'
    with pytest.raises(ValueError):
        intake.document_response_json(duplicate_keys)


def test_each_rejected_native_answer_is_visible_and_prior_validations_remain_visible(monkeypatch):
    from backend.nis.engineering.goal_execution.progress import sink
    from backend.tests.test_reference_reasoner import reasoner_with_transport, run_reference
    events = []
    instance, prepared, _ = reasoner_with_transport(monkeypatch, retry_foreign_port=True, wire_padding=True)
    token = sink.set(events.append)
    try:
        with pytest.raises(ValueError, match='nicht ausgewählten Teilnehmers'):
            run_reference(instance, prepared)
    finally:
        sink.reset(token)
    validations = [row for row in events if row.get('metadata', {}).get('source') == 'document_reference_validation']
    rejected = [row for row in validations if row['metadata']['validation_status'] == 'REJECTED']
    assert len(rejected) == 2
    assert all(row['metadata']['validation_error'] and 'abgelehnt' in row['text'] for row in rejected)
    assert validations[-1]['metadata']['validation_status'] == 'REJECTED'
    assert any(row['metadata']['validation_status'] == 'VALIDATED' for row in validations)
    assert all(row['metadata']['canonical_writes'] is False for row in validations)
