"""Independent finite-demand counterexamples; no Original/model acceptance."""
from copy import deepcopy
import json

import httpx
import pytest
from jsonschema import Draft202012Validator

from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_port_intent_allocation import intent, prepared_schema
from backend.tests.test_reference_reasoner import (
    complete_design, effective_reference_context, reasoner_with_transport, run_reference,
)


def groups(count=17, owners=('owner-a', 'owner-b')):
    record = {key: value for key, value in intent().items() if key != 'device_id'}
    return {owner: {'connections': [{**deepcopy(record), 'count': count}],
                    'rationale': 'Complete authored physical demand, not hardware qualification.'}
            for owner in owners}


def expand(existing, value, owners=('owner-a', 'owner-b'), complete=True):
    codec = getattr(reasoner, '_reference_expand_port_groups', None)
    assert callable(codec), 'The native complete demand needs a finite lossless NIS codec.'
    return codec(existing, value, owners, complete)


def test_native_group_schema_requires_complete_exact_owner_scope():
    prepared, _ = prepared_schema()
    public = deepcopy(reasoner._reference_schema_for_stage(prepared, {'ports'}))
    schema = reasoner._reference_schema_for_stage(
        prepared, {'ports'}, port_groups=True, device_ids=('owner-a', 'owner-b'))
    wire = {**intake.ReferenceDesignProposal().model_dump(mode='json'),
            'port_groups_by_device': groups(), 'port_plan_complete': True}
    validator = Draft202012Validator(schema)
    validator.validate(wire)
    for value in (False, None, 1):
        assert not validator.is_valid({**wire, 'port_plan_complete': value})
    missing = deepcopy(wire)
    del missing['port_groups_by_device']['owner-b']
    assert not validator.is_valid(missing)
    foreign = deepcopy(wire)
    foreign['port_groups_by_device']['foreign'] = foreign['port_groups_by_device']['owner-a']
    assert not validator.is_valid(foreign)
    assert schema['properties']['ports']['maxItems'] == 0
    assert reasoner._reference_schema_for_stage(prepared, {'ports'}) == public


def test_explicit_identical_parallel_ports_are_all_preserved_without_deduplication():
    value = groups()
    before = deepcopy(value)
    prior = reasoner._reference_expand_port_intents([], [intent()], ('owner-a',))
    prior_before = deepcopy(prior)
    result = expand(prior, value)
    assert len(result) == 34 and len({row['id'] for row in result}) == 34
    assert not {row['id'] for row in result} & {row['id'] for row in prior}
    assert prior == prior_before and value == before
    for owner in ('owner-a', 'owner-b'):
        expected = intent(owner)
        assert [{key: v for key, v in row.items() if key != 'id'}
                for row in result if row['device_id'] == owner] == [expected] * 17
    assert all('count' not in row for row in result)


@pytest.mark.parametrize('count', [None, True, False, 0, -1, '17', 1.0, 10001])
def test_runtime_rejects_invalid_or_unbounded_native_counts(count):
    with pytest.raises(ValueError):
        expand([], groups(count))


@pytest.mark.parametrize('complete', [False, None, 1, 'true'])
def test_runtime_cannot_accept_an_unclosed_native_scope(complete):
    with pytest.raises(ValueError):
        expand([], groups(), complete=complete)


def test_runtime_requires_all_and_only_selected_owners():
    value = groups(1)
    for invalid in ({'owner-a': value['owner-a']}, {**value, 'foreign': value['owner-a']}):
        with pytest.raises(ValueError):
            expand([], invalid)


def test_total_public_port_limit_includes_already_planned_ports():
    existing = [{'id': f'prior-{i}'} for i in range(9999)]
    before = deepcopy(existing)
    with pytest.raises(ValueError):
        expand(existing, groups(1))
    assert existing == before


def test_free_prose_cannot_close_an_empty_physical_participant():
    value = groups(1)
    value['owner-b']['connections'] = []
    with pytest.raises(ValueError):
        expand([], value)
    value['owner-b']['rationale'] = ''
    with pytest.raises(ValueError):
        expand([], value)


@pytest.mark.parametrize('field,value', [('id', 'invented'), ('device_id', 'foreign'),
                                        ('parameters', {'bitrate_bps': 500000})])
def test_group_cannot_supply_identity_owner_or_early_parameters(field, value):
    authored = groups(1)
    authored['owner-a']['connections'][0][field] = value
    with pytest.raises(ValueError):
        expand([], authored)


def test_actual_planner_closes_finite_demand_instead_of_ordinal_only_paging(monkeypatch):
    def design(prepared):
        value = complete_design(prepared)
        value['ports'].extend({**deepcopy(value['ports'][0]), 'id': f'parallel-{i}'}
                              for i in range(16))
        return value

    instance, prepared, observed = reasoner_with_transport(monkeypatch, design_factory=design)
    original = instance.client._transport
    old_pages, group_requests = [], []

    async def provider(request):
        if request.url.path.endswith('/show'):
            return await original.handle_async_request(request)
        payload = json.loads(request.content)
        content = effective_reference_context(payload['messages'])
        if 'port_groups_by_device' in payload['format']['properties']:
            group_requests.append(deepcopy(content))
            owners = content['device_ids_for_this_stage']
            kinds = {row['id']: row['kind'] for row in content['current_candidate']['devices']}
            manifest = {}
            for owner in owners:
                manifest[owner] = {'connections': [{'count': 17 if kinds[owner] == 'CONTROLLER' else 1,
                    'technology': 'can', 'role': 'LOCAL', 'network_scope': 'local', 'parameters': {},
                    'rationale': 'Authored parallel physical connectors; not hardware qualification.',
                    'field_references': {}}], 'rationale': 'Entire authored physical-connection demand.'}
            body = {'port_groups_by_device': manifest, 'port_plan_complete': True}
        elif 'port_intents' in payload['format']['properties']:
            old_pages.append(content)
            assert len(old_pages) <= 3, 'Ordinal-only continuation never closed the selected physical scope.'
            body = {'port_intents': [{**intent(content['device_ids_for_this_stage'][0]),
                'field_references': {}, 'network_scope': 'local',
                'rationale': f'Physical connector number {len(old_pages)}.'}], 'port_intents_complete': False}
        else:
            return await original.handle_async_request(request)
        return httpx.Response(200, json={'message': {'content': json.dumps(body)}, 'done': True,
            'done_reason': 'stop', 'prompt_eval_count': 500, 'eval_count': 200})

    instance.client._transport = httpx.MockTransport(provider)
    from backend.nis.engineering.goal_execution.progress import sink
    progress = []
    token = sink.set(progress.append)
    try:
        result = run_reference(instance, prepared)
    finally:
        sink.reset(token)
    assert old_pages == [] and len(group_requests) == 3
    assert len(result['proposal']['ports']) == 19
    assert len({row['id'] for row in result['proposal']['ports']}) == 19
    assert result['source_evidence']['source_text'] == prepared['source_evidence']['source_text']
    assert result['canonical_writes'] is False
    closed = [row['metadata'] for row in progress
              if row.get('metadata', {}).get('port_plan_complete') is True]
    assert sum(row['planned_port_count'] for row in closed) == 19
    assert all(row['canonical_writes'] is False for row in closed)
