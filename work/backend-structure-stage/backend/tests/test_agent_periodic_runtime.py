"""The direct 30 s ECU chat path uses real project evidence and review."""
from __future__ import annotations

import asyncio
from uuid import uuid4

from backend.nis.agent.api.mcp_client import EngineeringMCPClient
from backend.nis.agent.api.tool_contract import Permission
from backend.nis.agent.context.agent_context import AgentContext
from backend.nis.agent.runtime.service import EngineeringAssistantService
from backend.nis.agent.tools.runtime import ToolAuthority
from backend.nis.agent.tools.runtime import execute
from backend.nis.infrastructure.persistence.repository import create_object
from backend.nis.interfaces.mcp.server import create_server


PROMPT = 'Lege eine ECU an, die mir die Stellgliedpositionen im System alle 30 Sekunden abfragt.'


def test_free_chat_30s_acquisition_uses_existing_canopen_status_evidence():
    authority = ToolAuthority('periodic-acquisition-' + uuid4().hex)

    def seed():
        actuator = create_object('HardwareNode', {'name': 'Servoantrieb1', 'device_type': 'ActuatorController'})
        controller = create_object('HardwareNode', {'name': 'ControlECU', 'device_type': 'ECU'})
        create_object('Interface', {'name': 'ServoCANopen', 'hardware_node_id': str(actuator['id']),
                                    'interface_type': 'CANopen'})
        interface = create_object('Interface', {'name': 'ControlCANopen', 'hardware_node_id': str(controller['id']),
                                                'interface_type': 'CANopen'})
        create_object('Message', {'name': 'ControlStatus', 'interface_id': str(interface['id']),
                                  'cycle_ms': 100, 'dlc': 1,
                                  'configuration': {'generation_role': 'DEVICE_STATUS'}})

    seeded = execute(authority, 'seed_periodic', Permission.READ_MODEL, {}, lambda _: seed())
    assert seeded.success, seeded.findings

    async def invoke():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAssistantService(client).execute(
                PROMPT, AgentContext(active_project_id=authority.project_id))

    result = asyncio.run(invoke())
    assert result['runtime']['goal']['goal_type'] == 'PERIODIC_ACQUISITION'
    assert result['runtime']['status'] == 'READY_FOR_REVIEW', result['events']
    assert not result['runtime']['completed']
    proposal = result['proposals'][0]
    assert proposal['status'] == 'VALIDATED', proposal
    assert any(change['object_type'] == 'HardwareNode' and
               change['data']['name'].startswith('StellgliedAbfrage') and
               change['data']['device_type'] == 'ECU'
               for change in proposal['changes']), proposal['changes']
    assert any(change['object_type'] == 'Function' and
               change['data'].get('configuration', {}).get('cycle_time_ms') == 30000
               for change in proposal['changes'])
