"""Port-stage dependency regressions; authored fixtures, not original acceptance."""
from copy import deepcopy

import pytest

from backend.nis.agent.orchestration.local_reasoner import _reference_port_function_context
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_design import fixture_request
from backend.tests.test_reference_reasoner import complete_design
from backend.tests.test_reference_reasoner import reasoner_with_transport, run_reference


def test_physical_port_planning_receives_completed_original_function_ownership(monkeypatch):
    instance, prepared, observed = reasoner_with_transport(monkeypatch)
    result = run_reference(instance, prepared)
    required = {key for key, fact in prepared['facts'].items() if fact['kind'] == 'FUNCTION'}
    demand = [row for row in observed if row['device_ids_for_this_stage']
              and row['output_fields_for_this_stage'] == ['ports'] and not row['port_ids_for_this_stage']]
    assert demand
    for request in demand:
        functions = request['current_candidate']['functions']
        assert {row['source_fact_id'] for row in functions} == required
        assert all(row['executor_device_ids'] or row['realized_by_fact_ids'] for row in functions)
    assert {row['source_fact_id'] for row in result['proposal']['functions']} == required


def test_selected_port_context_preserves_atomic_and_parent_composite_source_facts(monkeypatch):
    instance, prepared, observed = reasoner_with_transport(monkeypatch)
    run_reference(instance, prepared)
    demands = [row for row in observed if row['device_ids_for_this_stage']
               and row['output_fields_for_this_stage'] == ['ports'] and not row['port_ids_for_this_stage']]
    for request in demands:
        selected = request['device_ids_for_this_stage']
        focus = request['selected_port_function_context']
        assert set(focus) == set(selected)
        devices = {row['id']: row for row in request['current_candidate']['devices']}
        functions = {row['source_fact_id']: row for row in request['current_candidate']['functions']}
        def hosts(key):
            row = functions[key]
            return set(row['executor_device_ids']).union(*(hosts(child) for child in row['realized_by_fact_ids']))
        for device_id in selected:
            expected = {key for key in functions if device_id in hosts(key)}
            assert set(focus[device_id]['functions']) == expected
            assert focus[device_id]['device'] == devices[device_id]
            for key in expected:
                assert focus[device_id]['functions'][key] == {
                    'source_fact': prepared['facts'][key], 'realization': functions[key]}
        # The focused view supplements the complete candidate, never replaces it.
        assert request['current_candidate']['devices']
        assert set(functions) == {key for key, fact in prepared['facts'].items() if fact['kind'] == 'FUNCTION'}


def test_owner_functions_are_separate_from_sensor_ownership_and_projection_is_lossless():
    prepared = intake.prepare_reference_design(fixture_request())
    value = intake.ReferenceDesignProposal.model_validate(complete_design(prepared)).model_dump(mode='json')
    before = deepcopy(value)
    facts_before = deepcopy(prepared['facts'])
    focus = _reference_port_function_context(value['devices'], value['functions'], prepared['facts'], ('C', 'S'))
    assert focus['S']['functions'] == {}
    assert focus['S']['owner_device']['id'] == 'C'
    assert focus['S']['owner_functions'] == focus['C']['functions']
    assert focus['C']['owner_device'] is None and focus['C']['owner_functions'] == {}
    focus['S']['owner_device']['name'] = 'mutated projection'
    next(iter(focus['C']['functions'].values()))['source_fact']['name'] = 'mutated projection'
    assert value == before and prepared['facts'] == facts_before


@pytest.mark.parametrize('corruption', ['foreign_selection', 'foreign_executor', 'foreign_child',
                                      'foreign_fact', 'duplicate_function', 'cycle', 'unknown_owner'])
def test_invalid_function_graph_cannot_become_port_context(corruption):
    prepared = intake.prepare_reference_design(fixture_request())
    value = intake.ReferenceDesignProposal.model_validate(complete_design(prepared)).model_dump(mode='json')
    selected = ('C',)
    first = value['functions'][0]
    if corruption == 'foreign_selection': selected = ('absent',)
    elif corruption == 'foreign_executor': first['executor_device_ids'] = ['absent']
    elif corruption == 'foreign_child': first['realized_by_fact_ids'] = ['absent']
    elif corruption == 'foreign_fact': first['source_fact_id'] = 'absent'
    elif corruption == 'duplicate_function': value['functions'].append(deepcopy(first))
    elif corruption == 'cycle': first['realized_by_fact_ids'] = [first['source_fact_id']]
    elif corruption == 'unknown_owner': value['devices'][0]['owner_device_id'] = 'absent'
    with pytest.raises(ValueError):
        _reference_port_function_context(value['devices'], value['functions'], prepared['facts'], selected)


def test_project_without_declared_functions_does_not_invent_function_or_transport():
    devices = [{'id': 'plain', 'name': 'Device without functional declaration', 'owner_device_id': None}]
    assert _reference_port_function_context(devices, [], {}, ('plain',)) == {
        'plain': {'device': devices[0], 'functions': {}, 'owner_device': None, 'owner_functions': {}}}
