"""Independent selected-identity regressions; no native/original acceptance claim."""
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, ValidationError

from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_design import fixture_request, fixture_design, reference


def selected_ports():
    return [{'id': f'P{index}', 'device_id': f'owner-{index}',
             'technology': 'can', 'role': 'LOCAL', 'network_scope': 'original-network',
             'parameters': {}, 'rationale': 'Original intent', 'field_references': {}}
            for index in range(4)]


def test_private_port_decoder_rejects_same_id_with_different_values():
    prepared = intake.prepare_reference_design(fixture_request())
    ports = selected_ports()
    schema = reasoner._reference_schema_for_stage(prepared, {'ports'},
        port_ids=tuple(row['id'] for row in ports))
    # Independently authored counterpart of actual38025: four rows, two IDs.
    rows = [deepcopy(ports[index]) for index in (0, 0, 2, 2)]
    for index, row in enumerate(rows):
        row.update(rationale=f'Distinct row {index}', parameters={'bitrate_bps': 500000 + index})
    body = {**intake.ReferenceDesignProposal().model_dump(mode='json'), 'ports': rows}
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(body)


def test_private_function_decoder_rejects_repeated_source_identity():
    prepared = intake.prepare_reference_design(fixture_request())
    functions = fixture_design(prepared)['functions'][:2]
    identities = tuple(row['source_fact_id'] for row in functions)
    schema = reasoner._reference_schema_for_stage(prepared, {'functions', 'functional_dependencies'},
        function_ids=identities)
    rows = [deepcopy(functions[0]), deepcopy(functions[0])]
    rows[1]['rationale'] = 'Different authored decision, same forbidden source identity'
    body = {**intake.ReferenceDesignProposal().model_dump(mode='json'), 'functions': rows}
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(body)


def test_selected_port_wire_contains_only_mutable_parameter_decisions():
    prepared = intake.prepare_reference_design(fixture_request())
    public_before = deepcopy(intake.reference_design_schema(prepared))
    identities = tuple(row['id'] for row in selected_ports())
    schema = reasoner._reference_schema_for_stage(prepared, {'ports'}, port_ids=identities)
    assert 'port_parameters' in schema['properties'], 'Exact required ID keys are missing'
    keyed = schema['properties']['port_parameters']
    assert set(keyed['required']) == set(keyed['properties']) == set(identities)
    assert keyed['additionalProperties'] is False
    assert schema['properties']['ports']['maxItems'] == 0
    for value in keyed['properties'].values():
        assert set(value['properties']) == {'parameters', 'rationale', 'field_references'}
        assert value['additionalProperties'] is False
    assert intake.reference_design_schema(prepared) == public_before


def test_progress_identifies_actual_port_and_function_selections(monkeypatch):
    from backend.nis.engineering.goal_execution.progress import sink
    from backend.tests.test_reference_reasoner import reasoner_with_transport, run_reference
    instance, prepared, _ = reasoner_with_transport(monkeypatch)
    events = []
    token = sink.set(events.append)
    try:
        result = run_reference(instance, prepared)
    finally:
        sink.reset(token)
    progress = [event for event in events
                if (event.get('metadata') or {}).get('source') == 'document_reference_design']
    ports = [event for event in progress if event['metadata'].get('selected_port_ids')]
    functions = [event for event in progress if event['metadata'].get('selected_function_fact_ids')]
    assert ports and functions, 'Selected identities must remain visible across a long stage'
    assert all(event['metadata']['selection_labels'] for event in ports + functions)
    assert all(event['metadata']['canonical_writes'] is False for event in ports + functions)
    assert result['canonical_writes'] is False


def parameter_values(ports):
    return {row['id']: {'parameters': {'bitrate_bps': 500000},
            'rationale': 'Independent parameter decision', 'field_references': {'ports': ['R-after']}}
            for row in ports}


def test_selected_port_expansion_preserves_mixed_technology_identity_and_bindings():
    ports = selected_ports()
    ports[0].update(technology='ethernet', role='BACKBONE', network_scope='original-backbone')
    ports[1].update(technology='can_fd', network_scope='original-local')
    ports[0]['field_references'] = {'ports': ['R-before']}
    before = deepcopy(ports)
    chosen = [ports[0], ports[1]]
    values = parameter_values(chosen)
    values['P0']['parameters'] = {'bitrate_bps': 1000000000}
    expanded = reasoner._reference_expand_selected_ports(ports, values, ('P0', 'P1'))
    merged = reasoner._reference_merge_port_parameters(ports, expanded, ('P0', 'P1'))
    immutable = ('id', 'device_id', 'technology', 'role', 'network_scope')
    assert [{key: row[key] for key in immutable} for row in merged] == [
        {key: row[key] for key in immutable} for row in before]
    assert merged[0]['parameters'] == {'bitrate_bps': 1000000000}
    assert merged[0]['field_references']['ports'] == ['R-before', 'R-after']
    assert merged[2:] == before[2:]
    assert ports == before


@pytest.mark.parametrize('corruption', ['missing', 'foreign', 'duplicate_selection',
    'id', 'device_id', 'technology', 'role', 'network_scope', 'foreign_reference_field'])
def test_selected_port_expansion_never_normalizes_invalid_selections(corruption):
    ports = selected_ports()[:2]
    before = deepcopy(ports)
    values = parameter_values(ports)
    selected = ('P0', 'P1')
    if corruption == 'missing':
        values.pop('P1')
    elif corruption == 'foreign':
        values['foreign'] = deepcopy(values['P0'])
    elif corruption == 'duplicate_selection':
        selected = ('P0', 'P0')
    elif corruption == 'foreign_reference_field':
        values['P0']['field_references'] = {'quantity': ['R-after']}
    else:
        values['P0'][corruption] = 'rewritten-identity'
    with pytest.raises(ValueError):
        expanded = reasoner._reference_expand_selected_ports(ports, values, selected)
        reasoner._reference_merge_port_parameters(ports, expanded, selected)
    assert ports == before


def test_required_port_keys_reject_missing_foreign_and_immutable_wire_values():
    source = reference(('ports',))
    source['id'] = 'R-after'
    prepared = intake.prepare_reference_design(fixture_request(references=[source]))
    ports = selected_ports()
    identities = tuple(row['id'] for row in ports)
    schema = reasoner._reference_schema_for_stage(prepared, {'ports'}, port_ids=identities)
    validator = Draft202012Validator(schema)
    body = {**intake.ReferenceDesignProposal().model_dump(mode='json'),
            'port_parameters': parameter_values(ports)}
    validator.validate(body)
    for mode in ('missing', 'foreign', 'technology', 'reference_field'):
        wrong = deepcopy(body)
        if mode == 'missing':
            wrong['port_parameters'].pop('P1')
        elif mode == 'foreign':
            wrong['port_parameters']['foreign'] = deepcopy(wrong['port_parameters']['P0'])
        elif mode == 'technology':
            wrong['port_parameters']['P0']['technology'] = 'lin'
        else:
            wrong['port_parameters']['P0']['field_references'] = {'device_id': ['R-after']}
        with pytest.raises(ValidationError):
            validator.validate(wrong)


def test_selected_function_keys_preserve_each_original_fact_without_guessing_data():
    prepared = intake.prepare_reference_design(fixture_request())
    rows = fixture_design(prepared)['functions']
    identities = tuple(row['source_fact_id'] for row in rows)
    values = {row['source_fact_id']: {key: deepcopy(value) for key, value in row.items()
                                   if key != 'source_fact_id'} for row in rows}
    before = deepcopy(values)
    schema = reasoner._reference_schema_for_stage(prepared, {'functions', 'functional_dependencies'},
        function_ids=identities)
    body = {**intake.ReferenceDesignProposal().model_dump(mode='json'), 'functions_by_fact': values}
    Draft202012Validator(schema).validate(body)
    assert reasoner._reference_expand_selected_functions(values, identities) == rows
    assert values == before
    assert all('source_fact_id' not in value['properties'] for value in
               schema['properties']['functions_by_fact']['properties'].values())


@pytest.mark.parametrize('corruption', ['missing', 'foreign', 'source_fact_id'])
def test_selected_function_keys_do_not_rewrite_or_drop_original_facts(corruption):
    prepared = intake.prepare_reference_design(fixture_request())
    rows = fixture_design(prepared)['functions']
    identities = tuple(row['source_fact_id'] for row in rows)
    values = {row['source_fact_id']: {key: deepcopy(value) for key, value in row.items()
                                   if key != 'source_fact_id'} for row in rows}
    if corruption == 'missing':
        values.pop(identities[-1])
    elif corruption == 'foreign':
        values['foreign'] = deepcopy(values[identities[0]])
    else:
        values[identities[0]]['source_fact_id'] = identities[-1]
    with pytest.raises(ValueError):
        reasoner._reference_expand_selected_functions(values, identities)
