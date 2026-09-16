"""Real MCP negative path, disposable SQL fixture, not product data."""
import asyncio
import json
from pathlib import Path
from uuid import uuid4

pytest_plugins = ['backend.tests.conftest']


def test_s25_full_controller_rejects_real_create_port_call():
    from backend.tests.test_goal_execution_sql import fixture
    from backend.engineering.agent_tools.runtime import ToolAuthority, execute
    from backend.agent_core.api.tool_contract import Permission
    from backend.engineering.repository import create_object, list_objects
    from backend.engineering.goal_execution import service
    from backend.agent_core.api.mcp_client import EngineeringMCPClient
    from backend.simulator_engineering_mcp.server import create_server
    authority = ToolAuthority('nis-e2e-industry60-s25-' + uuid4().hex)
    def seed(_):
        data = fixture()
        create_object('HardwareNetworkInterface', {'name': 'Occupied CAN channel', 'hardware_node_id': data['dst']['id'],
            'technology': 'CAN_FD', 'controller_ref': 'controller-' + data['dst']['id'],
            'channel_index': 1, 'physical_port_ref': 'occupied-connector', 'network_ref': 'different-network'})
        return data
    seeded = execute(authority, 'test-fixture', Permission.GENERATE_PROPOSAL, {}, seed)
    assert seeded.success, seeded.findings
    data = seeded.data
    plan = execute(authority, 'test-prepare', Permission.GENERATE_PROPOSAL, {},
        lambda _: service.prepare('Verbinde ParkAssist mit DriverAssistance', data['sf']['id'], data['df']['id']))
    assert plan.success, plan.findings
    assert plan.data['status'] == 'BLOCKED', plan.data
    def inventory():
        return execute(authority, 'test-read', Permission.READ_MODEL, {}, lambda _: list_objects('HardwareNetworkInterface')).data
    before = inventory()
    async def calls():
        async with EngineeringMCPClient(create_server(authority)) as client:
            capacity = await client.call('inspect_controller_capacity', {'controller_ref': 'controller-' + data['dst']['id']})
            created = await client.call('create_physical_port', {'workload_id': plan.data['workload_id']})
            return capacity.model_dump(mode='json'), created.model_dump(mode='json')
    capacity, created = asyncio.run(calls())
    after = inventory()
    assert capacity['success']
    assert not created['success']
    assert after == before
    target = Path(__file__).resolve().parents[1] / 'evidence/industry60-completion/S25'
    target.mkdir(parents=True, exist_ok=True)
    (target / 'full-channel-mcp.json').write_text(json.dumps({'fixture': data, 'plan': plan.data,
        'capacity': capacity, 'create_physical_port': created, 'before': before, 'after': after}, ensure_ascii=False, indent=2), encoding='utf8')
