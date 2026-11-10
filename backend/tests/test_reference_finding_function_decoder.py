"""Independent decoder/validator parity cases from terminal native failures."""
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, ValidationError

from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_design import fixture_request, fixture_design


def function_case():
    prepared = intake.prepare_reference_design(fixture_request())
    design = intake.ReferenceDesignProposal.model_validate(fixture_design(prepared)).model_dump(mode='json')
    identities = [row['source_fact_id'] for row in design['functions']]
    schema = reasoner._reference_schema_for_stage(prepared, {'functions'}, function_ids=identities)
    body = intake.ReferenceDesignProposal().model_dump(mode='json')
    body['functions_by_fact'] = {row['source_fact_id']: {
        key: deepcopy(value) for key, value in row.items() if key != 'source_fact_id'
    } for row in design['functions']}
    return prepared, design, schema, body, identities


@pytest.mark.parametrize('realization,executors,children', [
    ('COMPOSITE', ['C'], ['child']), ('COMPOSITE', [], []),
    ('COMPOSITE', [], ['unknown']), ('COMPOSITE', [], ['self']),
    ('ATOMIC', [], []), ('ATOMIC', ['C'], ['child']),
])
def test_decoder_rejects_function_choices_already_forbidden_by_public_validator(realization, executors, children):
    prepared, design, schema, body, identities = function_case()
    children = [identities[1] if key == 'child' else identities[0] if key == 'self' else key for key in children]
    change = dict(realization=realization, executor_device_ids=executors, realized_by_fact_ids=children)
    design['functions'][0].update(change)
    with pytest.raises(ValueError):
        intake.validate_reference_design(design, prepared)
    body['functions_by_fact'][identities[0]].update(change)
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(body)


@pytest.mark.parametrize('composite', [False, True])
def test_valid_atomic_and_composite_choices_preserve_source_bound_public_contract(composite):
    prepared, design, schema, body, identities = function_case()
    before = deepcopy(intake.reference_design_schema(prepared))
    if composite:
        change = dict(realization='COMPOSITE', executor_device_ids=[], realized_by_fact_ids=identities[1:])
        body['functions_by_fact'][identities[0]].update(change)
        design['functions'][0].update(change)
    Draft202012Validator(schema).validate(body)
    result = intake.validate_reference_design(design, prepared)
    assert result['canonical_writes'] is False
    assert intake.reference_design_schema(prepared) == before


@pytest.mark.parametrize('field,size', [('message', 2001), ('code', 121)])
def test_native_finding_cannot_spend_output_on_publicly_invalid_unbounded_strings(field, size):
    prepared = intake.prepare_reference_design(fixture_request())
    schema = reasoner._reference_schema_for_stage(prepared, {'devices'})
    body = intake.ReferenceDesignProposal().model_dump(mode='json')
    finding = {'code': 'MISSING_HARDWARE_EVIDENCE', 'target_ref': '/devices/C', 'message': 'A real unresolved question.'}
    finding[field] = 'x' * size
    body['unresolved'] = [finding]
    with pytest.raises(ValueError):
        intake.ReferenceDesignProposal.model_validate(body)
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(body)


def test_full_target_identity_keeps_original_projection_and_strict_public_length_gate():
    prepared = intake.prepare_reference_design(fixture_request())
    schema = reasoner._reference_schema_for_stage(prepared, {'devices'})
    body = intake.ReferenceDesignProposal().model_dump(mode='json')
    body['unresolved'] = [{'code': 'MISSING_EVIDENCE', 'target_ref': '/' + 'x' * 1999, 'message': 'Missing evidence.'}]
    Draft202012Validator(schema).validate(body)
    assert intake.ReferenceDesignProposal.model_validate(body).unresolved[0].target_ref == body['unresolved'][0]['target_ref']
    body['unresolved'][0]['target_ref'] += 'x'
    with pytest.raises(ValueError):
        intake.ReferenceDesignProposal.model_validate(body)


def test_many_distinct_concise_findings_remain_available_without_source_truncation():
    prepared = intake.prepare_reference_design(fixture_request())
    before = deepcopy(prepared)
    schema = reasoner._reference_schema_for_stage(prepared, {'devices'})
    body = intake.ReferenceDesignProposal().model_dump(mode='json')
    body['unresolved'] = [{'code': 'MISSING_EVIDENCE', 'target_ref': f'/devices/D{n}',
        'message': f'Hardware evidence for independently required device {n} is absent.'} for n in range(80)]
    Draft202012Validator(schema).validate(body)
    assert intake.ReferenceDesignProposal.model_validate(body).model_dump(mode='json')['unresolved'] == body['unresolved']
    assert prepared == before


def test_cycle_is_retried_in_same_function_stage_before_downstream_planning(monkeypatch):
    import json
    import httpx
    from backend.tests.test_reference_reasoner import reasoner_with_transport, run_reference, effective_reference_context

    captured = []
    instance, prepared, _ = reasoner_with_transport(monkeypatch, capture=captured)
    provider = instance.client._transport.handler
    changed = False
    bad_raw = None

    def respond(request):
        nonlocal changed, bad_raw
        response = provider(request)
        if not request.url.path.endswith('/show') and not changed and 'functions_by_fact' in captured[-1]['format']['properties']:
            changed = True
            body = response.json()
            value = json.loads(body['message']['content'])
            keys = list(value['functions_by_fact'])
            for index in (0, 1):
                value['functions_by_fact'][keys[index]].update(realization='COMPOSITE', executor_device_ids=[], realized_by_fact_ids=[keys[1-index]])
            bad_raw = json.dumps(value)
            return httpx.Response(200, json={**body, 'message': {'content': bad_raw}})
        return response

    monkeypatch.setattr(instance.client._transport, 'handler', respond)
    result = run_reference(instance, prepared)
    first = next(i for i, row in enumerate(captured) if 'functions_by_fact' in row['format']['properties'])
    initial, retry = captured[first:first+2]
    assert 'functions_by_fact' in retry['format']['properties'], 'Do not plan communication or restart source inventory before correcting this cycle.'
    assert retry['messages'][:-2] == initial['messages']
    assert retry['messages'][-2] == {'role': 'assistant', 'content': bad_raw}
    assert 'zyklische' in retry['messages'][-1]['content']
    assert effective_reference_context(initial['messages']) == effective_reference_context(retry['messages'])
    assert initial['format'] == retry['format'] and initial['options'] == retry['options']
    assert result['canonical_writes'] is False
