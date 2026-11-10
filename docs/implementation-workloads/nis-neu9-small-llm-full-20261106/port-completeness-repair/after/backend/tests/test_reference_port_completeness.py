"""Independent source-participant completion regressions, not original acceptance."""
from copy import deepcopy
import json

import httpx
import pytest
from jsonschema import Draft202012Validator

from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_port_group_completion import groups
from backend.tests.test_reference_port_intent_allocation import prepared_schema
from backend.tests.test_reference_reasoner import (
    effective_reference_context, reasoner_with_transport, run_reference,
)


OWNERS = ('controller-a', 'controller-b', 'controller-c', 'controller-d')


def one_port_for_four_participants():
    value = groups(1, OWNERS)
    for owner in OWNERS[1:]:
        value[owner]['connections'] = []
        value[owner]['rationale'] = 'No individual function mapped yet; omit the connection.'
    return value


def test_native_grammar_rejects_complete_four_participant_scope_with_one_port():
    prepared, _ = prepared_schema()
    schema = reasoner._reference_schema_for_stage(
        prepared, {'ports'}, port_groups=True, device_ids=OWNERS)
    wire = {**intake.ReferenceDesignProposal().model_dump(mode='json'),
            'port_groups_by_device': one_port_for_four_participants(),
            'port_plan_complete': True}
    assert not Draft202012Validator(schema).is_valid(wire)


def test_runtime_rejects_empty_complete_participant_despite_nonempty_rationale():
    value = one_port_for_four_participants()
    before = deepcopy(value)
    with pytest.raises(ValueError):
        reasoner._reference_expand_port_groups([], value, OWNERS, True)
    assert value == before


def test_native_grammar_preserves_explicit_open_decision_without_inventing_ports():
    prepared, _ = prepared_schema()
    schema = reasoner._reference_schema_for_stage(
        prepared, {'ports'}, port_groups=True, device_ids=OWNERS)
    wire = {**intake.ReferenceDesignProposal().model_dump(mode='json'),
            'port_groups_by_device': one_port_for_four_participants(),
            'port_plan_complete': False, 'unresolved': [{
                'code': 'PHYSICAL_CONNECTION_UNDECIDED', 'target_ref': OWNERS[1],
                'message': 'The authored standalone participant has no specified external interface.'}]}
    validator = Draft202012Validator(schema)
    assert validator.is_valid(wire)
    assert not validator.is_valid({**wire, 'port_plan_complete': True})
    assert not validator.is_valid({**wire, 'unresolved': []})
    foreign = deepcopy(wire)
    foreign['unresolved'][0]['target_ref'] = 'not-selected'
    assert not validator.is_valid(foreign)
    with pytest.raises(ValueError):
        reasoner._reference_expand_port_groups([], wire['port_groups_by_device'], OWNERS, False)


def test_complete_scope_keeps_all_authored_parallel_ports_and_public_schema():
    prepared, _ = prepared_schema()
    before = intake.reference_model_output_schema(prepared)
    schema = reasoner._reference_schema_for_stage(
        prepared, {'ports'}, port_groups=True, device_ids=OWNERS)
    wire = {**intake.ReferenceDesignProposal().model_dump(mode='json'),
            'port_groups_by_device': groups(17, OWNERS), 'port_plan_complete': True}
    assert Draft202012Validator(schema).is_valid(wire)
    result = reasoner._reference_expand_port_groups([], wire['port_groups_by_device'], OWNERS, True)
    assert len(result) == 68 and len({row['id'] for row in result}) == 68
    assert intake.reference_model_output_schema(prepared) == before


def test_normal_planner_retries_missing_connection_before_advancing_participants(monkeypatch):
    instance, prepared, _ = reasoner_with_transport(monkeypatch)
    original = instance.client._transport
    selections = []

    class CapturedNextPortRequest(Exception):
        pass

    async def provider(request):
        if request.url.path.endswith('/show'):
            return await original.handle_async_request(request)
        payload = json.loads(request.content)
        if 'port_groups_by_device' not in payload['format']['properties']:
            return await original.handle_async_request(request)
        context = effective_reference_context(payload['messages'])
        owners = context['device_ids_for_this_stage']
        selections.append(deepcopy(owners))
        if len(selections) == 2:
            raise CapturedNextPortRequest
        body = {'port_plan_complete': True, 'port_groups_by_device': {
            owner: {'connections': [], 'rationale': 'No individually mapped function; no port.'}
            for owner in owners}}
        return httpx.Response(200, json={'message': {'content': json.dumps(body)},
            'done': True, 'done_reason': 'stop', 'prompt_eval_count': 500, 'eval_count': 100})

    instance.client._transport = httpx.MockTransport(provider)
    from backend.nis.engineering.goal_execution.progress import sink
    progress = []
    token = sink.set(progress.append)
    try:
        with pytest.raises(CapturedNextPortRequest):
            run_reference(instance, prepared)
    finally:
        sink.reset(token)
    assert len(selections) == 2 and selections[0] == selections[1]
    validations = [row['metadata'] for row in progress
                   if row.get('metadata', {}).get('source') == 'document_reference_validation'
                   and row['metadata'].get('selected_device_ids') == selections[0]]
    assert validations and validations[-1]['validation_status'] == 'REJECTED'
    assert not any(row.get('port_plan_complete') is True for row in validations)
