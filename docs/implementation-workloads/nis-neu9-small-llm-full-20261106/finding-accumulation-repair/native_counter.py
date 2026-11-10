"""Authored small-model finding-delta counter using actual product instructions/schema.

No original-run resume, canonical writes, or hardware qualification.
"""
import ast
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import httpx
from jsonschema import Draft202012Validator

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration import local_reasoner as r, project_intake as intake
from backend.nis.agent.orchestration.reference_token_budget import ReferenceTokenBudget
from backend.tests.test_reference_port_intent_allocation import prepared_schema
from backend.nis.engineering.communication.device_communication import FUNCTIONAL_DEVICE_REASONING_RULES
from backend.nis.engineering.structure.spatial_architecture import REASONING_RULES

OUT = Path(__file__).resolve().parent / 'native-v3'

def save(name, value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')

async def main():
    OUT.mkdir(exist_ok=False)
    tree = ast.parse((ROOT/'backend/nis/agent/orchestration/local_reasoner.py').read_text(encoding='utf8'))
    method = next(n for n in ast.walk(tree) if isinstance(n,ast.AsyncFunctionDef) and n.name=='plan_reference_design')
    system_expr = next(n.value for n in ast.walk(method) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='system' for t in n.targets))
    instruction_expr = next(value for n in ast.walk(method) if isinstance(n,ast.Dict) for key,value in zip(n.keys,n.values) if isinstance(key,ast.Constant) and key.value=='instruction')
    env = dict(inventory_stage=False,inventory_closed=False,inventory_target=None,derivation_fact_ids=None,
               port_groups=True,port_intent=False,port_ids=(),function_ids=(),device_ids=('offline-a','offline-b'),
               _reference_inventory_batch_names=r._reference_inventory_batch_names)
    system = eval(compile(ast.Expression(system_expr),'<actual-product-system>','eval'),globals())
    instruction = eval(compile(ast.Expression(instruction_expr),'<actual-product-instruction>','eval'),globals(),env)
    existing = {'code':'MISSING_HARDWARE_EVIDENCE','target_ref':'offline-a','message':'No measured hardware qualification evidence for offline-a.'}
    new = {**existing,'target_ref':'offline-b','message':'No measured hardware qualification evidence for offline-b.'}
    source = ('Authored independent test only, not a real installation: offline-a and offline-b are local controllers with explicitly zero physical network connections. '
              'Keep its existing hardware-evidence finding open. A separate new fact concerns offline-b: it has no measured hardware qualification evidence either. '
              'For that different open decision use exactly code MISSING_HARDWARE_EVIDENCE, target_ref offline-b, message No measured hardware qualification evidence for offline-b. '
              'Do not resolve any evidence gaps or invent hardware. Both controllers are in the selected physical-port group.')
    prepared,_ = prepared_schema(('offline-a',))
    current = intake.ReferenceDesignProposal().model_dump(mode='json')
    current['devices'] = [intake.ReferenceDevice(id=name,name=name,kind='CONTROLLER',quantity=1,source_fact_ids=['AUTHORED-OFFLINE'],rationale='Authored isolated counter.').model_dump(mode='json') for name in ('offline-a','offline-b')]
    current['unresolved'] = [existing]
    context = {'original_source':source,'original_facts':{'AUTHORED-OFFLINE':{'kind':'REQUIREMENT','name':source}},'current_candidate':current,
               'planning_stage':'Vollständiger Anschlussbedarf der ausgewählten Teilnehmer',
               'inventory_target_for_this_stage':None,'derivation_fact_ids_for_this_stage':None,
               'device_ids_for_this_stage':['offline-a','offline-b'],'port_ids_for_this_stage':[],
               'function_fact_ids_for_this_stage':[],'producer_device_ids_for_this_stage':[],
               'output_fields_for_this_stage':['ports'],'instruction':instruction}
    messages,_,_ = r._reference_context_messages([],None,context,system,131072)
    schema=r._reference_schema_for_stage(prepared,{'ports'},port_groups=True,device_ids=('offline-a','offline-b'))
    async with httpx.AsyncClient(timeout=1200,trust_env=False) as client:
        ps=(await client.get('http://127.0.0.1:11434/api/ps')).json()
        save('before-loaded-models.json',ps)
        if not ps.get('models'):
            # Explicitly reload the authorized small model with zero output;
            # no worker kill, provider restart, or parameter-limit change.
            warm=await client.post('http://127.0.0.1:11434/api/generate',json={'model':'qwen3.5:9b','stream':False,'keep_alive':'10m','options':{'num_ctx':131072,'num_predict':0}})
            warm.raise_for_status();save('empty-load.json',warm.json())
        save('provider.json',json.loads(subprocess.check_output([sys.executable,str(OUT.parent.parent/'read_provider.py'),'--model','qwen3.5:9b'],text=True)))
        budget=ReferenceTokenBudget(client,'http://127.0.0.1:11434/api/chat','qwen3.5:9b',131072,bridge_url='http://127.0.0.1:13503/tokenize-chat')
        payload={'model':'qwen3.5:9b','messages':messages,'format':schema,'think':False,'stream':True,'keep_alive':'10m',
                 'options':{'temperature':0,'num_predict':8192,'num_ctx':await budget.admit(messages)}}
        save('request.json',payload)
        with (OUT/'events.ndjson').open('w',encoding='utf8') as stream:
            def progress(value):
                stream.write(json.dumps({'at':datetime.now(timezone.utc).isoformat(),**value})+'\n');stream.flush()
            response=await r._reference_stream_response(client,'http://127.0.0.1:11434/api/chat',payload,progress)
        save('response.json',response)
        value=intake.document_response_json(response['message']['content'])
        Draft202012Validator(schema).validate(value)
        assert response.get('done_reason')!='length'
        assert value['port_plan_complete'] is True and all(value['port_groups_by_device'][k]['connections']==[] for k in ('offline-a','offline-b'))
        assert value['unresolved']==[new],value['unresolved']
        assert context['current_candidate']['unresolved']==[existing]
        save('result.json',{'status':'PASS','scope':'Actual product prompt/schema; authored offline and distinct missing-evidence counter. Runtime accumulation separately covered by full mocked planner regression.',
             'actual_generation_requests':1,'original_acceptance':False,'canonical_writes':False,
             'existing_preserved':existing,'new_finding':new,'source_sha256':hashlib.sha256((ROOT/'backend/nis/agent/orchestration/local_reasoner.py').read_bytes()).hexdigest(),
             'metrics':{k:response.get(k) for k in ('prompt_eval_count','eval_count','total_duration')}})
        print('PASS: native finding delta; original and release acceptance remain open',flush=True)

asyncio.run(main())
