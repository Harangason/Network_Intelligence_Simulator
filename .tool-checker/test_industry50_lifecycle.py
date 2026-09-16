import json,asyncio
from pathlib import Path
from uuid import uuid4
import pytest
pytest_plugins=['backend.tests.conftest']
OUT=Path(__file__).resolve().parent/'evidence/industry50'
def test_finding_lifecycle_probe():
 from backend.agent_core.api.agent_response import AgentResponse
 from backend.agent_core.context.agent_context import AgentContext
 from backend.engineering.agent_tools.runtime import ToolAuthority,execute
 from backend.agent_core.api.tool_contract import Permission
 from backend.engineering.agent_tools import conversation
 from backend.engineering.repository import create_object
 a=ToolAuthority('nis-e2e-industry50-s29-core-'+uuid4().hex)
 def call(f):return execute(a,'s29-lifecycle',Permission.READ_MODEL,{},lambda _:f())
 start=call(lambda:conversation.begin('Finding bewerten',AgentContext(active_project_id=a.project_id))).data
 finding=AgentResponse(type='FINDING',title='SINGLE_POINT_OF_FAILURE',text='CentralGateway is articulation point of topology.',severity='WARNING').model_dump(mode='json',exclude_none=True)
 call(lambda:conversation.record_event(start['run_id'],finding));call(lambda:conversation.finish(start['run_id']))
 before=call(conversation.inspect).model_dump(mode='json');empty=call(lambda:conversation.decide(finding['id'],'ACCEPTED_RISK','',True)).model_dump(mode='json')
 accepted=call(lambda:conversation.decide(finding['id'],'ACCEPTED_RISK','SCRIPTED_TEST: bewusst begrenzter Labortest, Review bei Architekturänderung.',True)).model_dump(mode='json')
 after=call(conversation.inspect).model_dump(mode='json')
 call(lambda:create_object('HardwareNode',{'name':'AdditionalController','device_type':'ECU'}))
 changed=call(conversation.inspect).model_dump(mode='json')
 d=OUT/'S29';d.mkdir(exist_ok=True);(d/'core-lifecycle.json').write_text(json.dumps({'fixture_origin':'Source-specified existing finding, injected as baseline via core record_event, not algorithmic detection','finding':finding,'before':before,'empty_reason':empty,'accepted':accepted,'after':after,'changed':changed},ensure_ascii=False,indent=2),encoding='utf8')
 assert not empty['success'] and accepted['success']
 assert changed['data']['decisions'][finding['id']]['status']=='NEEDS_REVIEW'
def test_trace_fault_probe(tmp_path,monkeypatch):
 from backend.tests.test_transport_integrity import gateway_config
 from hardware_profile import normalize_hardware_config
 from universal_trace import generate_universal_events
 from backend.app.runtime_analysis import analyze_runtime_trace
 from backend.engineering.agent_tools.runtime import ToolAuthority
 from backend.agent_core.api.mcp_client import EngineeringMCPClient
 from backend.simulator_engineering_mcp.server import create_server
 cfg=gateway_config.__wrapped__(monkeypatch)
 cfg.update(duration_s=15,max_events=10000,output_dir=str(tmp_path))
 cfg['scenario']={'mode':'USER_DEFINED_FAULT','faults':[{'scope':'NETWORK','type':'GATEWAY_DELAY','target':{'id':'gateway'},'start_s':12,'end_s':15,'delay_ms':100}]}
 events=generate_universal_events(cfg,normalize_hardware_config(cfg),start_utc=1700000000)[1]
 summary=analyze_runtime_trace({'model_simulation':{'frames':events}},cfg)
 async def run():
  async with EngineeringMCPClient(create_server(ToolAuthority('nis-e2e-industry50-s28-core-'+uuid4().hex))) as client:
   return (await client.call('find_trace_root_cause',{'events':events,'configuration':cfg})).model_dump(mode='json')
 result=asyncio.run(run());d=OUT/'S28';d.mkdir(exist_ok=True)
 (d/'generated-trace.json').write_text(json.dumps({'fixture_origin':'Real simulator events; transport config from explicit test fixture with mocked model reads, not full product job; no fabricated events','configuration':cfg,'events':events,'metrics':summary,'root_cause':result},ensure_ascii=False,indent=2),encoding='utf8')
 assert events
