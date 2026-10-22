"""Mocked local-wire regressions, explicitly not a native model/E2E proof."""
import asyncio
from copy import deepcopy
import json

import httpx
import pytest

from backend.nis.agent.orchestration import project_intake as intake
from backend.nis.agent.orchestration.local_reasoner import LocalEngineeringReasoner
from backend.tests.test_reference_design import fixture_request, fixture_design, wire


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


def reasoner_with_transport(monkeypatch, *, family='qwen3', truncate=False):
    prepared = intake.prepare_reference_design(fixture_request())
    design = complete_design(prepared)
    observed = []
    monkeypatch.setenv('LOCAL_AI_CONTEXT_TOKENS', '131072')
    def handler(request):
        if request.url.path.endswith('/show'):
            return httpx.Response(200, json={'details': {'family': family}, 'model_info': {'general.parameter_count': 27000000000}})
        payload = json.loads(request.content)
        content = json.loads(payload['messages'][1]['content'])
        observed.append(content)
        allowed = set(content['output_fields_for_this_stage'])
        candidate = {key: deepcopy(value) for key, value in design.items() if key in allowed}
        if allowed == {'communication'}:
            selected = set(content['producer_device_ids_for_this_stage'])
            candidate['communication'] = [row for row in candidate['communication'] if row['producer_device_id'] in selected]
        return httpx.Response(200, json={'message': {'content': json.dumps(candidate)}, 'done_reason': 'length' if truncate else 'stop',
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
