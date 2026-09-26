"""A named message question uses scoped calculation evidence, not an LLM guess."""
from __future__ import annotations

import asyncio
from uuid import uuid4

from backend.agent_core.api.mcp_client import EngineeringMCPClient
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.runtime.service import EngineeringAssistantService
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.agent_core.api.tool_contract import Permission
from backend.engineering.repository import create_object
from backend.simulator_engineering_mcp.server import create_server


def test_named_message_without_route_reports_precise_gap(monkeypatch):
    class OfflineReasoner:
        async def next(self, *args):
            raise AssertionError('Message timing diagnosis must not require an LLM')

        async def close(self):
            pass

    authority = ToolAuthority('timing-diagnosis-' + uuid4().hex)

    def make_message():
        hardware = create_object('HardwareNode', {'name': 'Controller', 'device_type': 'ECU'})
        function = create_object('Function', {'name': 'PressureControl', 'hardware_node_id': str(hardware['id'])})
        interface = create_object('Interface', {'name': 'PressureInterface', 'function_id': str(function['id']),
                                                'interface_type': 'CAN_FD'})
        return create_object('Message', {'name': 'PressureCommand', 'interface_id': str(interface['id']),
                                         'dlc': 2, 'cycle_ms': 20})

    fixture = execute(authority, 'timing-fixture', Permission.READ_MODEL, {}, lambda _: make_message())
    assert fixture.success, fixture.findings

    async def invoke():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAssistantService(client, reasoner=OfflineReasoner()).execute(
                'Warum kommt PressureCommand zu spät an?', AgentContext(active_project_id=authority.project_id))

    result = asyncio.run(invoke())
    assert result['runtime']['goal']['goal_type'] == 'DIAGNOSE'
    assert result['runtime']['status'] == 'BLOCKED_WITH_EXPLICIT_CAUSE'
    answer = next(item for item in result['events'] if item['type'] == 'RESULT')
    assert answer['metadata']['failure_code'] == 'NO_ROUTE'
    assert answer['metadata']['details']['message']['id'] == fixture.data['id']
    assert 'keine berechenbare Route' in answer['text']


def test_calculated_deadline_failure_is_explicitly_not_observed(monkeypatch):
    from backend.engineering.agent_tools import timing_diagnosis

    monkeypatch.setattr(timing_diagnosis.model, 'objects', lambda _kind: [
        {'id': 'message-1', 'name': 'PressureCommand'}])
    monkeypatch.setattr(timing_diagnosis.model, 'model_revision', lambda: 'revision-1')
    monkeypatch.setattr(timing_diagnosis, 'simulation_sequence', lambda _routes: {'status': 'NOT_OBSERVED', 'transactions': []})

    class Calculation:
        def __init__(self, _project_id):
            pass

        def calculate(self, *, persist):
            assert persist is False
            return {'status': 'WARNING', 'provenance': {'calculation_version': 'v1'},
                    'results': {'routes': [
                        {'route_id': 'route-1', 'message_id': 'message-1', 'network_id': 'bus-1',
                         'protocol': 'CAN_FD', 'end_to_end_latency_ms': 12.5,
                         'max_latency_ms': 10, 'latency_status': 'FAIL',
                         'breakdown': {'sender_queue_ms': 9.0, 'propagation_ms': 0.5},
                         'bottleneck': {'component': 'sender_queue_ms', 'delay_ms': 9.0}},
                        {'route_id': 'route-1', 'message_id': 'message-1', 'network_id': 'bus-2',
                         'protocol': 'ETHERNET', 'end_to_end_latency_ms': 12.5,
                         'max_latency_ms': 10, 'latency_status': 'FAIL',
                         'breakdown': {'sender_queue_ms': 9.0},
                         'bottleneck': {'component': 'sender_queue_ms', 'delay_ms': 9.0}},
                    ]}}

    monkeypatch.setattr(timing_diagnosis, 'CapacityTimingService', Calculation)
    monkeypatch.setattr(timing_diagnosis, 'current_project_id', lambda: 'project-1')
    result = timing_diagnosis.inspect_message_timing({'request': 'Warum kommt PressureCommand zu spät an?'})
    assert result['status'] == 'MODEL_DEADLINE_FAIL'
    assert result['evidence_kind'] == 'CALCULATED_MODEL'
    assert result['observed_trace_available'] is False
    assert result['routes'][0]['network_ids'] == ['bus-1', 'bus-2']
    assert len(result['routes']) == 1
