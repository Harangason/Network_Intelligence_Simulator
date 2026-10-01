"""Real MCP/SQL checks for the repaired read paths; not browser E2E."""
import asyncio
from uuid import uuid4
import pytest



def test_saved_signal_and_finding_read_paths():
    from backend.agent_core.api.agent_response import AgentResponse
    from backend.agent_core.api.mcp_client import EngineeringMCPClient
    from backend.agent_core.api.tool_contract import Permission
    from backend.agent_core.context.agent_context import AgentContext
    from backend.agent_core.core.engineering_agent import EngineeringAgent
    from backend.engineering.agent_tools.runtime import ToolAuthority, execute
    from backend.engineering.agent_tools import conversation
    from backend.engineering.repository import create_object
    from backend.simulator_engineering_mcp.server import create_server
    authority = ToolAuthority('nis-test-fixed-read-' + uuid4().hex)
    def call(fn):
        result = execute(authority, 'test-fixture', Permission.READ_MODEL, {}, lambda _: fn())
        assert result.success, result.model_dump()
        return result.data
    gateway = call(lambda: create_object('HardwareNode', {'name': 'CentralGateway', 'device_type': 'Gateway'}))
    function = call(lambda: create_object('Function', {'name': 'SpeedMonitoring', 'hardware_node_id': gateway['id']}))
    interface = call(lambda: create_object('Interface', {'name': 'SpeedOutput', 'function_id': function['id'], 'interface_type': 'CAN_FD'}))
    message = call(lambda: create_object('Message', {'name': 'SpeedStatus', 'interface_id': interface['id'], 'cycle_ms': 10, 'dlc': 1, 'direction': 'tx'}))
    signal = call(lambda: create_object('Signal', {'name': 'MotorRPM', 'message_id': message['id'], 'length_bits': 4, 'start_bit': 0,
        'byte_order': 'little_endian', 'data_type': 'unsigned', 'factor': 50, 'offset_value': 0,
        'min_value': 0, 'max_value': 5000, 'unit': 'rpm', 'semantic': {'semantic_type': 'PHYSICAL_SCALAR'}, 'configuration': {'resolution': 50}}))
    context = AgentContext(active_project_id=authority.project_id)
    turn = call(lambda: conversation.begin('Befund prüfen', context))
    finding = AgentResponse(type='FINDING', title='SINGLE_POINT_OF_FAILURE', text='CentralGateway ist ein zentraler Ausfallpunkt.',
        severity='WARNING', context_refs=[{'id': str(gateway['id']), 'type': 'HardwareNode'}]).model_dump(mode='json', exclude_none=True)
    call(lambda: conversation.record_event(turn['run_id'], finding))
    call(lambda: conversation.finish(turn['run_id']))
    from backend.engineering.goal_execution.graph import ModelGraphService
    assert str(call(lambda: ModelGraphService.load().find_object('CentralGateway'))['id']) == str(gateway['id'])
    async def run():
        async with EngineeringMCPClient(create_server(authority)) as client:
            agent = EngineeringAgent(client)
            checked = await agent.run('Prüfe MotorRPM: 0 bis 5000 rpm, Auflösung 50 rpm, Zyklus 10 ms, CAN-FD; MessageBinding 4 bit.', context)
            assert checked['status'] == 'ANSWERED'
            assert any('7' in e.get('text', '') for e in checked['events']), checked
            assert any(e['type'] == 'FINDING' and e['severity'] == 'ERROR' for e in checked['events'])
            assessed = await agent.run('Bewerte SINGLE_POINT_OF_FAILURE am CentralGateway.', context)
            assert assessed['status'] == 'ANSWERED', str(assessed['events'])
            assert any(e['id'] == finding['id'] and e['title'] == 'SINGLE_POINT_OF_FAILURE' for e in assessed['events'])
            assert all(not e.get('metadata', {}).get('contract_error') for e in assessed['events'])
    asyncio.run(run())
    call(lambda: conversation.decide(finding['id'], 'ACCEPTED_RISK', 'Isolierter Labortest; bei Modelländerung neu prüfen.', True))
    assert call(conversation.inspect)['decisions'][finding['id']]['status'] == 'ACCEPTED_RISK'
    call(lambda: create_object('HardwareNode', {'name': 'AdditionalController', 'device_type': 'ECU'}))
    assert call(conversation.inspect)['decisions'][finding['id']]['status'] == 'NEEDS_REVIEW'

