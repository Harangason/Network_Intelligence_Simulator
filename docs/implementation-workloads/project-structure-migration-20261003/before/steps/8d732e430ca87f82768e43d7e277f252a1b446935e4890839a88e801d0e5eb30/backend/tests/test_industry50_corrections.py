"""Regressions derived from the observed 50-case report, not its old oracle."""
import asyncio
import json
from pathlib import Path
from uuid import uuid4
from unittest.mock import AsyncMock

from backend.agent_core.api.mcp_client import EngineeringMCPClient
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.context.input_adapter import adapt_input
from backend.agent_core.core.engineering_agent import EngineeringAgent
from backend.agent_core.orchestration.capability_intent import connection_request
from backend.engineering.agent_tools.project_draft import parse_requirement
from backend.engineering.agent_tools.runtime import ToolAuthority
from backend.simulator_engineering_mcp.server import create_server

CASES = {c['id']: c for c in json.loads((Path(__file__).parents[2] / 'tests/fixtures/industry40.json').read_text(encoding='utf8'))['cases']}


def test_explicit_canopen_devices_survive_intake():
    draft = parse_requirement(CASES['S03-A']['input'])
    endpoints = [d for d in draft['devices'] if d['role'] in {'SENSOR', 'ACTUATOR'}]
    assert len(endpoints) == 4
    assert all(d['known_kind'] and d['technology'] == 'CANopen' for d in endpoints)
    assert sum('Positionssensor' in d['name'] for d in endpoints) == 2
    assert sum('Servoantrieb' in d['name'] for d in endpoints) == 2
    # There is both a controller and a gateway; no owner is invented.
    assert all(d['owner_id'] is None for d in endpoints)


def test_separate_communication_mapping_preserves_device_families():
    draft = parse_requirement(CASES['S07-A']['input'])
    assert any(d['name'] == 'RobotController' for d in draft['devices'])
    for device in draft['devices']:
        expected = next((tech for stem, tech in [('LiDAR', 'Ethernet'), ('Kamera', 'Ethernet'),
            ('MotorDrives', 'EtherCAT'), ('Encoder', 'CAN_FD'), ('IMU', 'CAN_FD')] if device['name'].startswith(stem)), None)
        if expected: assert device['technology'] == expected, device
    assert all(d['technology'] == 'EtherCAT' for d in parse_requirement(CASES['S05-A']['input'])['devices'])


def test_selected_signal_mode_does_not_resume_other_work():
    from backend.agent_core.api.tool_contract import ToolResult
    class Client:
        async def call(self, name, arguments=None):
            assert name == 'inspect_signal_definition'
            assert arguments == {'reference': 'selected-signal'}
            return ToolResult(data={'signal': {'name': 'MotorRPM'}, 'required_bits': 7, 'validation': {}})
    context = AgentContext(active_project_id='test', requested_mode='VALIDATE_SIGNAL', current_workload='goal-old',
        selected_object_refs=[{'object_type': 'Signal', 'id': 'selected-signal'}])
    result = asyncio.run(EngineeringAgent(Client()).run('Signal prüfen', context))
    assert result['status'] == 'ANSWERED'


def test_finding_assessment_recognizes_original_case():
    from backend.agent_core.orchestration.capability_intent import finding_assessment
    assert finding_assessment('Bewerte SINGLE_POINT_OF_FAILURE am CentralGateway.') == ('SINGLE_POINT_OF_FAILURE', 'CentralGateway')


def test_compute_nodes_are_additional_and_keep_their_identity():
    for case, count in [('S07-A', 2), ('S07-B', 2), ('S11-A', 3), ('S11-B', 3), ('S20-A', 56)]:
        draft = parse_requirement(CASES[case]['input'])
        assert sum(d['role'] == 'CONTROLLER' for d in draft['devices']) == count, case
    large = parse_requirement(CASES['S20-A']['input'])
    assert sum('EdgeCompute' in d['name'] for d in large['devices']) == 4
    assert sum('HighPerformanceCompute' in d['name'] for d in large['devices']) == 2


def test_explicit_section_items_are_not_added_to_the_total():
    draft = parse_requirement(CASES['S01-A']['input'])
    assert len(draft['devices']) == 8
    assert {d['technology'] for d in draft['devices'] if d['role'] == 'SENSOR'} == {'SPI', 'I2C', 'GPIO'}
    assert len({d['id'] for d in draft['devices']}) == 8
    open_draft = parse_requirement(CASES['S09-A']['input'])
    assert sum(d['role'] == 'SENSOR' for d in open_draft['devices']) == 20
    assert all(not d['known_kind'] for d in open_draft['devices'] if d['role'] == 'SENSOR')


def test_compound_goal_keeps_target_separate_from_followups():
    prompt = 'Verbinde ParkAssist mit DriverAssistance, prüfe die Kommunikation in einer kurzen Simulation und analysiere auftretende Timingprobleme.'
    assert connection_request(prompt) == ('ParkAssist', 'DriverAssistance')
    from backend.engineering.goal_execution.followups import requested_followups
    assert requested_followups(prompt) == ['SIMULATE_SCENARIO', 'ANALYZE_TRACE']


def test_architecture_intent_is_explicit():
    context = AgentContext(active_project_id='test')
    envelope = adapt_input(CASES['S01-A']['input'], context, run_id='test-run')
    assert envelope.user_intent == 'CREATE_ARCHITECTURE'


def test_mcp_metadata_unsupported_and_timeout_contract():
    async def run():
        async with EngineeringMCPClient(create_server(ToolAuthority('industry50-' + uuid4().hex))) as client:
            tools = await client.tools()
            assert all(t['output_schema'] and t['metadata']['version'] and t['metadata']['permission'] for t in tools)
            missing = await client.call('no_such_engineering_tool')
            assert missing.status == 'TOOL_NOT_FOUND' and not missing.success
            unknown = await client.call('calculate_message_size', {'technology': 'UNKNOWN-TEST', 'payload_bytes': 8})
            assert unknown.status == 'NOT_SUPPORTED' and not unknown.success
            client.client.call_tool = AsyncMock(side_effect=TimeoutError)
            timeout = await client.call('inspect_project')
            assert timeout.status == 'TOOL_TIMEOUT' and not timeout.success
            assert timeout.findings[0]['retryable'] is False
    asyncio.run(run())


def test_signal_inspection_does_not_create_a_generation_workload():
    from backend.agent_core.api.tool_contract import ToolResult
    class Client:
        calls = []
        async def call(self, name, arguments=None):
            self.calls.append(name)
            assert name == 'inspect_signal_definition'
            return ToolResult(data={'signal': {'name': 'MotorRPM'}, 'required_bits': 7, 'validation': {}})
    client = Client()
    context = AgentContext(active_project_id='test', current_workload='stale-signal-workload')
    result = asyncio.run(EngineeringAgent(client).run('Prüfe Signal MotorRPM: 0–5000 rpm, Auflösung 50 rpm, 10 ms.', context))
    assert result['status'] == 'ANSWERED'
    assert client.calls == ['inspect_signal_definition']


def test_connectivity_read_does_not_enter_reasoning_or_resume_old_goal():
    from backend.agent_core.api.tool_contract import ToolResult
    class Client:
        async def call(self, name, arguments=None):
            assert name == 'inspect_object_connectivity'
            assert arguments['references'] == ['ParkAssist', 'DriverAssistance']
            return ToolResult(data={'items': [{'object': {'name': 'ParkAssist'}, 'hardware': {'name': 'ECU'}, 'ports': [], 'networks': []}]})
    result = asyncio.run(EngineeringAgent(Client()).run('Wie sind ParkAssist und DriverAssistance aktuell angebunden?', AgentContext(active_project_id='test', current_workload='goal-old')))
    assert result['status'] == 'ANSWERED'
    assert not result['proposals']
