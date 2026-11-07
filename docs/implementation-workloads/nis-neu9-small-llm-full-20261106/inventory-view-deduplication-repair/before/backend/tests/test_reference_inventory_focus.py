"""Independent source-member and anchored-selection regressions; no native acceptance."""
from copy import deepcopy
import json

import pytest

from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_design import fixture_request
from backend.tests.test_reference_reasoner import effective_reference_context


def typed_device(name, member):
    prepared = intake.prepare_reference_design(fixture_request(sensor_group='Sensorik (Radar, Lidar)'))
    fact = next(key for key, value in prepared['facts'].items() if value['role'] == 'SENSOR')
    row = intake.ReferenceDevice(id='independent-sensor', name=name, kind='SENSOR', quantity=1,
        source_fact_ids=[fact], source_member_bindings={fact: member},
        rationale='Independent source-bound example, no physical evidence.').model_dump(mode='json')
    return prepared, fact, row


@pytest.mark.parametrize(('name', 'member'), [('Radar Sensor', 'Lidar'), ('Lidar front unit', 'Radar')])
def test_a_different_literal_type_in_the_name_cannot_count_as_selected_member(name, member):
    prepared, _, row = typed_device(name, member)
    with pytest.raises(ValueError, match='Typenbindung'):
        intake._validate_reference_inventory({'devices': [row]}, prepared, (), partial=True)


@pytest.mark.parametrize(('name', 'member'), [('Radar Sensor', 'Radar'), ('Lidar front unit', 'Lidar'),
    ('Optical ranging unit', 'Lidar'), ('Radarless optical unit', 'Lidar')])
def test_matching_or_noncontradictory_names_still_need_the_normal_full_review(name, member):
    prepared, _, row = typed_device(name, member)
    findings = intake._validate_reference_inventory({'devices': [row]}, prepared, (), partial=True)
    assert findings, 'A partial example must never become a complete reference approval.'
    assert intake.reference_inventory_members(prepared['facts'][row['source_fact_ids'][0]]) == ['Radar', 'Lidar']


def test_current_inventory_selection_and_coverage_are_literal_after_the_cached_prefix():
    prepared, fact, radar = typed_device('Radar Sensor', 'Radar')
    original = prepared['request']['original_requirement'] if 'original_requirement' in prepared['request'] else prepared['source_evidence']
    first = {'original_source': deepcopy(original), 'planning_stage': 'Physisches Quelleninventar',
        'inventory_target_for_this_stage': {'fact_id': fact, 'member': 'Radar', 'names': [], 'minimum_rows': 1, 'max_rows': 1},
        'derivation_fact_ids_for_this_stage': None, 'current_candidate': {'devices': []}}
    messages, _, _ = reasoner._reference_context_messages([], None, first, 'Independent protocol', 131072)
    history = [*messages, {'role': 'assistant', 'content': '{"independent_fixture_reply":true}'}]
    current = deepcopy(first)
    current['inventory_target_for_this_stage']['member'] = 'Lidar'
    current['current_candidate']['devices'] = [radar]
    wire, _, _ = reasoner._reference_context_messages(history, first, current, 'Independent protocol', 131072,
        anchor=(history, first))
    assert wire[:2] == messages, 'Keep the already processed exact original prefix.'
    assert effective_reference_context(wire) == current, 'All complete original data and current state must survive.'
    focus = json.loads(wire[-1]['content'])['nis_current_selection']
    assert focus['inventory_target'] == current['inventory_target_for_this_stage']
    assert focus['planning_stage'] == 'Physisches Quelleninventar'
    assert focus['existing_inventory'] == [{key: radar[key] for key in
        ('id', 'name', 'kind', 'source_fact_ids', 'source_member_bindings')}]
    assert focus['derivation_fact_ids'] is None
    assert focus['inventory_target']['member'] != focus['existing_inventory'][0]['source_member_bindings'][fact]


def test_live_inventory_output_identifies_the_current_original_selection(monkeypatch):
    from backend.nis.engineering.goal_execution.progress import sink
    from backend.tests.test_reference_reasoner import reasoner_with_transport, run_reference
    instance, prepared, _ = reasoner_with_transport(monkeypatch)
    events = []
    token = sink.set(events.append)
    try:
        result = run_reference(instance, prepared)
    finally:
        sink.reset(token)
    outputs = [event for event in events if event.get('metadata', {}).get('source') == 'document_reference_output'
               and event['metadata'].get('inventory_target')]
    assert outputs
    for event in outputs:
        metadata = event['metadata']
        target = metadata['inventory_target']
        label = target['member'] or prepared['facts'][target['fact_id']]['name']
        assert label in event['text'], 'The visible output must identify this original selection, not only a repeated phase.'
        assert metadata['selected_inventory_fact_ids'] == [target['fact_id']]
        assert metadata['selection_labels'] == [label]
        assert metadata['canonical_writes'] is False
    assert result['canonical_writes'] is False
