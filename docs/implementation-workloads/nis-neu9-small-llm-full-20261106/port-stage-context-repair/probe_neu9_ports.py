"""Read-only source-context diagnosis with authored inventory, not an original run."""
import argparse
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
from backend.nis.engineering.communication.device_communication import FUNCTIONAL_DEVICE_REASONING_RULES
from backend.nis.engineering.structure.spatial_architecture import REASONING_RULES
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
from backend.tests.test_reference_reasoner import effective_reference_context

DIR = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--name', required=True)
parser.add_argument('--history', action='store_true')
parser.add_argument('--focus-control', action='store_true')
parser.add_argument('--hardware-history', action='store_true')
parser.add_argument('--history-request', type=Path)
parser.add_argument('--replay-request', type=Path)
parser.add_argument('--product-focus', action='store_true')
args = parser.parse_args()
OUT = DIR/args.name
assert OUT.parent == DIR


def save(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


async def main():
    OUT.mkdir(exist_ok=False)
    request = json.loads((DIR.parent/'attempt-16/plan-reference/request.json').read_text(encoding='utf8'))
    prepared = intake.prepare_reference_design(request)
    source = prepared['source_evidence']['source_text']
    assert hashlib.sha256(source.encode()).hexdigest() == '32c864c91ac85c2884ef0c3c9e62456e6ade59cc2a22cae384bdfe5a2e2eff60'
    tree = ast.parse((ROOT/'backend/nis/agent/orchestration/local_reasoner.py').read_text(encoding='utf8'))
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == 'plan_reference_design')
    system_expr = next(n.value for n in ast.walk(func) if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == 'system' for t in n.targets))
    instruction_expr = next(value for n in ast.walk(func) if isinstance(n, ast.Dict)
        for key, value in zip(n.keys, n.values) if isinstance(key, ast.Constant) and key.value == 'instruction')
    system = eval(compile(ast.Expression(system_expr), '<actual-nis-system>', 'eval'), globals())
    catalog = deepcopy(prepared['catalog'])
    devices = []
    for index, item in enumerate(catalog['source_devices']):
        evidence = item['evidence']
        fact_id = next(k for k, fact in prepared['facts'].items()
                       if fact['kind'] == 'INSTANCE' and fact['source_quote'] == evidence['source_quote'])
        devices.append(intake.ReferenceDevice(id=f'counter-{index:03}', name=item['name'], kind=evidence['device_role'],
            quantity=1, source_fact_ids=[fact_id], rationale='Authored inventory counter record; not an accepted native model.').model_dump(mode='json'))
    assert len(devices) == 251
    owners = tuple(row['id'] for row in devices if row['kind'] == 'CONTROLLER')[:4]
    catalog['source_function_assignments'] = {k: catalog.get('source_function_assignments', {}).get(identity)
        for k, identity in prepared['fact_id_map'].items() if identity in catalog.get('source_function_assignments', {})}
    catalog['source_devices'] = [{k: row[k] for k in ('name','device_type') if k in row} for row in catalog['source_devices']]
    catalog.pop('name_aliases', None)
    catalog['source_technologies'] = {}
    for row in prepared['source_evidence'].get('technologies', []):
        if row['kind'] != 'TRANSPORT': continue
        tech = DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(row['name'])
        profile = DEFAULT_TECHNOLOGY_REGISTRY.profile(tech)
        catalog['source_technologies'][tech] = {k: deepcopy(profile[k]) for k in
            ('layer','hardware_interface','physical_layer_profile_id','implementation_status','rate_model','default_stack') if k in profile}
    base = {'original_source': source, 'original_facts': {k: {f: v.get(f) for f in
        ('name','kind','role','quantity','source_context')} for k,v in prepared['facts'].items()},
        'source_profile': [], 'reserved_project_device_names': [], 'reference_sources': prepared['reference_sources'],
        'registered_catalogs': catalog, 'protected_review_decisions': {k: prepared['source_evidence'].get(k)
            for k in ('answers','function_assignments','excluded_questions')}, 'known_communication': [], 'validation_feedback': None}
    def context(stage, inventory=False, rows=devices, names=None):
        env = dict(inventory_stage=inventory, inventory_closed=False, inventory_target=None, derivation_fact_ids=None,
                   port_groups=not inventory, port_intent=False, port_ids=(), function_ids=(), device_ids=() if inventory else owners,
                   _reference_inventory_batch_names=r._reference_inventory_batch_names)
        instruction = eval(compile(ast.Expression(instruction_expr), '<actual-nis-instruction>', 'eval'), globals(), env)
        candidate = intake.ReferenceDesignProposal().model_dump(mode='json'); candidate['devices'] = deepcopy(rows)
        return {**deepcopy(base), 'current_candidate': candidate, 'planning_stage': stage,
            'producer_device_ids_for_this_stage': [], 'port_ids_for_this_stage': [],
            'device_ids_for_this_stage': [] if inventory else list(owners), 'function_fact_ids_for_this_stage': [],
            'inventory_target_for_this_stage': {'fact_id': 'counter-inventory', 'names': names or []} if inventory else None,
            'derivation_fact_ids_for_this_stage': None, 'output_fields_for_this_stage': ['devices'] if inventory else ['ports'],
            'existing_inventory_for_this_stage': '/current_candidate/devices' if inventory else None, 'instruction': instruction}
    async with httpx.AsyncClient(timeout=1200, trust_env=False) as client:
        budget = ReferenceTokenBudget(client, 'http://127.0.0.1:11434/api/chat', 'qwen3.5:9b', 131072,
                                      bridge_url='http://127.0.0.1:13503/tokenize-chat')
        save('admission.json', json.loads(subprocess.check_output([sys.executable, str(DIR.parent/'read_provider.py'),
            '--model','qwen3.5:9b'], text=True)))
        history, previous = [], None
        if args.history_request:
            saved = json.loads(args.history_request.read_text(encoding='utf8'))
            history = saved['messages'][:-1]
            previous = effective_reference_context(history)
            assert previous['original_source'] == source
        elif args.history:
            for end in range(8, len(devices)+8, 8):
                selected = devices[end-8:min(end,len(devices))]
                current = context('Inventar der deklarierten Teilnehmer', True, devices[:end-8], [r['name'] for r in selected])
                messages, _, _ = await budget.select(r._reference_context_messages, history, previous, current, system, 131072)
                reply = {**intake.ReferenceDesignProposal().model_dump(mode='json'), 'devices': selected}
                history = [*messages, {'role':'assistant','content':json.dumps(reply,ensure_ascii=False)}]
                previous = current
        if args.hardware_history:
            fact_ids = [k for k,v in prepared['facts'].items() if v['kind'] in {'FUNCTION','REQUIREMENT'}]
            for start in range(0,len(fact_ids),r._REFERENCE_HARDWARE_FACT_BATCH):
                current = context('Funktionsbedingte physische Hardware', True)
                current['inventory_target_for_this_stage'] = None
                selected = fact_ids[start:start+r._REFERENCE_HARDWARE_FACT_BATCH]
                current['derivation_fact_ids_for_this_stage'] = selected
                env = dict(inventory_stage=True, inventory_closed=False, inventory_target=None,
                    derivation_fact_ids=selected, port_groups=False, port_intent=False, port_ids=(),
                    function_ids=(),device_ids=(),_reference_inventory_batch_names=r._reference_inventory_batch_names)
                current['instruction'] = eval(compile(ast.Expression(instruction_expr),'<actual-nis-instruction>','eval'),globals(),env)
                messages, _, _ = await budget.select(r._reference_context_messages,history,previous,current,system,131072)
                reply = {**intake.ReferenceDesignProposal().model_dump(mode='json'),
                    'inventory_choices':[],'inventory_complete':True}
                history = [*messages,{'role':'assistant','content':json.dumps(reply,ensure_ascii=False)}]
                previous = current
        current = context('Vollständiger Anschlussbedarf der ausgewählten Teilnehmer')
        if args.replay_request:
            replay = json.loads(args.replay_request.read_text(encoding='utf8'))
            messages = deepcopy(replay['messages'])
            rebased = False
            if args.product_focus:
                history = messages[:-1]
                previous = effective_reference_context(history)
                messages, _, rebased = await budget.select(
                    r._reference_context_messages, history, previous, current, system, 131072)
                assert messages[:-1] == history and not rebased
        else:
            messages, _, rebased = await budget.select(r._reference_context_messages, history, previous, current, system, 131072)
        assert effective_reference_context(messages) == current
        if args.focus_control:
            wire = json.loads(messages[-1]['content'])
            wire['nis_current_selection'] = {k: deepcopy(current[k]) for k in ('planning_stage','instruction',
                'output_fields_for_this_stage','device_ids_for_this_stage','port_ids_for_this_stage',
                'function_fact_ids_for_this_stage','producer_device_ids_for_this_stage')}
            messages[-1]['content'] = json.dumps(wire,ensure_ascii=False,separators=(',',':'))
            assert effective_reference_context(messages) == current
        schema = r._reference_schema_for_stage(prepared, {'ports'}, port_groups=True, device_ids=owners)
        if args.replay_request:
            assert replay['format'] == schema and replay['options']['num_ctx'] == 131072
            assert messages[:-1] == replay['messages'][:-1]
        payload = {'model':'qwen3.5:9b','messages':messages,'format':schema,'think':False,'stream':True,
            'keep_alive':'10m','options':{'temperature':0,'num_predict':8192,'num_ctx':await budget.admit(messages)}}
        save('context.json',current); save('request.json',payload)
        save('scope.json',{'unmodified_original':True,'authored_inventory':True,'authored_history':args.history,
            'full_original_run':False,'canonical_writes':False,'rebased':rebased,'token_proof':budget.evidence(messages)})
        with (OUT/'events.ndjson').open('w',encoding='utf8') as log:
            def report(value):
                log.write(json.dumps({'at':datetime.now(timezone.utc).isoformat(),**value})+'\n'); log.flush()
            body = await r._reference_stream_response(client,'http://127.0.0.1:11434/api/chat',payload,report)
        save('response.json',body)
        await budget.verify_response(messages,body)
    value = intake.document_response_json(body['message']['content'])
    Draft202012Validator(schema).validate(value)
    ports = r._reference_expand_port_groups([],value['port_groups_by_device'],owners,value['port_plan_complete'])
    result = {'status':'OBSERVED_DIAGNOSTIC_ONLY','counts':{key:sum(p['device_id']==key for p in ports) for key in owners},
        'decisions':value['port_groups_by_device'],'unresolved':value.get('unresolved',[]),'history':args.history,
        'focus_control':args.focus_control,'hardware_history':args.hardware_history,
        'product_focus':args.product_focus,
        'history_request':str(args.history_request) if args.history_request else None,
        'replay_request':str(args.replay_request) if args.replay_request else None,
        'actual_inference_requests':1,'original_acceptance':False,
        'metrics':{k:body.get(k) for k in ('prompt_eval_count','eval_count','prompt_eval_duration','eval_duration','total_duration')}}
    save('result.json',result); print(json.dumps(result,ensure_ascii=False),flush=True)


asyncio.run(main())
