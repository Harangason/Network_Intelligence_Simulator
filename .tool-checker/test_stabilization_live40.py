"""Live inference/intake recheck; deliberately not a nine-stage PASS claim."""
import asyncio
import json
from pathlib import Path
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

pytest_plugins = ['backend.tests.conftest']
ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT/'tests/fixtures/industry40.json').read_text(encoding='utf8'))['cases']
OUT = ROOT/'.tool-checker/evidence/industry40-stabilization-intake'

@pytest.mark.parametrize('case', CASES, ids=lambda c:c['id'])
def test_real_agent_intake_retains_inventory(case):
    authority = ToolAuthority('stabilization-' + case['id'] + '-' + uuid4().hex)
    class Observed(LocalEngineeringReasoner):
        responses = []
        async def next(self, *args):
            result = await super().next(*args)
            self.responses.append(result)
            return result
    async def run():
        reasoner = Observed()
        reasoner.responses = []
        try:
            async with EngineeringMCPClient(create_server(authority)) as client:
                result = await EngineeringAgent(client, reasoner=reasoner).run(case['input'], AgentContext(active_project_id=authority.project_id))
            return result, reasoner.responses, reasoner.model
        finally:
            await reasoner.close()
    result, responses, model = asyncio.run(run())
    draft = execute(authority,'read-live-draft',Permission.READ_MODEL,{},inspect)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/(case['id']+'.json')).write_text(json.dumps({'input':case['input'],'result':result,'draft':draft.model_dump(mode='json'),'llm_responses':responses,'model':model,'scope':'FIRST_TURN_INTAKE_ONLY','full_e2e_pass':False},ensure_ascii=False,indent=2),encoding='utf8')
    assert draft.success and draft.data
    assert draft.data['original_requirement'] == case['input']
    assert result['status'] == 'INCOMPLETE'
    assert not result['proposals']
    for key,role in [('sensors','SENSOR'),('actuators','ACTUATOR'),('ecus','CONTROLLER'),('gateways','GATEWAY')]:
        expected=case['counts'][key]
        if expected is not None:
            assert sum(d['role']==role for d in draft.data['devices']) == expected
