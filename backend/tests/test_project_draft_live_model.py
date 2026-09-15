"""Opt-in local-model quality smoke test; SQL still requires the isolated launcher."""
import asyncio
import os
from uuid import uuid4

import pytest

from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.core.engineering_agent import EngineeringAgent
from backend.agent_core.api.mcp_client import EngineeringMCPClient
from backend.agent_core.api.tool_contract import Permission
from backend.agent_core.orchestration.local_reasoner import LocalEngineeringReasoner
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.agent_tools.project_draft import inspect
from backend.simulator_engineering_mcp.server import create_server


@pytest.mark.skipif(os.environ.get('NIS_LIVE_MODEL') != '1', reason='Explicit local-model quality run only')
def test_real_local_model_preserves_small_project_and_calls_real_intake():
    authority = ToolAuthority('live-draft-' + uuid4().hex)
    class ObservedReasoner(LocalEngineeringReasoner):
        responses = []
        async def next(self, *args):
            result = await super().next(*args)
            self.responses.append(result)
            return result
    async def run():
        reasoner = ObservedReasoner()
        try:
            async with EngineeringMCPClient(create_server(authority)) as client:
                result = await EngineeringAgent(client, reasoner=reasoner).run(
                    'Ich möchte ein kleines Projekt mit Raspberry Pi, drei Temperatursensoren und fünf Ventilen. Keine Automotive-Anlage.',
                    AgentContext(active_project_id=authority.project_id))
            assert reasoner.responses, 'A real HTTP model response is required; fallback alone does not pass.'
            assert any(response.get('calls') or response.get('text') for response in reasoner.responses)
            print({'model': reasoner.model, 'responses': len(reasoner.responses), 'status': result['status']})
            return result
        finally:
            await reasoner.client.aclose()
    result = asyncio.run(run())
    assert result['status'] == 'INCOMPLETE'
    loaded = execute(authority, 'read-live-draft', Permission.READ_MODEL, {}, inspect)
    assert loaded.success
    assert loaded.data['industry'] == 'embedded_systems'
    assert len(loaded.data['devices']) == 9
    assert sum(device['role'] == 'ACTUATOR' for device in loaded.data['devices']) == 5
    assert all(device['technology'] is None for device in loaded.data['devices'])
