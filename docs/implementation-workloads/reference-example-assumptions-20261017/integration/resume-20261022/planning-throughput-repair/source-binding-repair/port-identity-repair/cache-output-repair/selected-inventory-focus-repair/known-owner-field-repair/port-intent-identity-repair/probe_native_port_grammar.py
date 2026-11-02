"""One authored native port-intent decoder counterprobe; no project writes."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
parser = argparse.ArgumentParser()
parser.add_argument('--attempt', default='native-grammar')
parser.add_argument('--owner-first-diagnostic', action='store_true')
parser.add_argument('--repeat-original-prompt', action='store_true')
parser.add_argument('--port-pages', action='store_true')
parser.add_argument('--prefix-cache', action='store_true')
parser.add_argument('--port-groups', action='store_true')
parser.add_argument('--context-delta', action='store_true')
parser.add_argument('--evidence-dir', type=Path)
args=parser.parse_args()
assert not (args.port_groups and (args.port_pages or args.prefix_cache))
assert not (args.context_delta and any((args.port_groups, args.port_pages, args.prefix_cache,
                                      args.owner_first_diagnostic, args.repeat_original_prompt)))
assert args.attempt.replace('-', '').isalnum()
OUT = (args.evidence_dir.resolve() if args.evidence_dir else Path(__file__).resolve().parent) / args.attempt
OUT.mkdir(exist_ok=False)
from backend.nis.agent.orchestration.local_reasoner import _reference_schema_for_stage, _reference_context_window, _reference_expand_port_intents, _reference_port_page_complete, _reference_context_messages, _reference_expand_port_groups
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_design import fixture_request, reference
from jsonschema import Draft202012Validator

def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def get(url, payload=None, headers=None):
    raw = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    with urlopen(Request(url, data=raw, headers={'Content-Type':'application/json', **(headers or {})}), timeout=1200) as response:
        return json.load(response)

source = ROOT / 'backend/nis/agent/orchestration/local_reasoner.py'
source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
nonce = secrets.token_hex(16) if args.prefix_cache or args.port_groups or args.context_delta else None
write('waiting.json', {'pid':os.getpid(), 'at_utc':datetime.now(timezone.utc).isoformat(),
                      'source_sha256':source_hash, 'actual_model_requests':0,
                      **({'nonce':nonce} if args.prefix_cache or args.port_groups or args.context_delta else {})})
print(json.dumps({'status':'WAITING_FOR_EXACT_PROCESS_GUARD','pid':os.getpid()}), flush=True)
deadline = time.monotonic() + 120
while not (OUT / 'go.json').exists():
    assert time.monotonic() < deadline, 'No actual process-bound guard GO received; no inference sent.'
    time.sleep(0.5)
go = json.loads((OUT / 'go.json').read_text())
assert go['pid'] == os.getpid() and go['source_sha256'] == source_hash
if args.prefix_cache or args.port_groups or args.context_delta:
    assert go['nonce'] == nonce, 'A fresh exact-process nonce is required.'
command = "$mainId=@(Get-NetTCPConnection -LocalPort 11434 | Where-Object {$_.OwningProcess -gt 0} | Select-Object -ExpandProperty OwningProcess -Unique);if($mainId.Count -ne 1){throw 'Ambiguous main provider'};$main=Get-CimInstance Win32_Process -Filter ('ProcessId='+$mainId[0]);if($main.Name -ne 'ollama.exe' -or $main.CommandLine -notmatch '(?:^|\\s)serve(?:\\s|$)'){throw 'Unexpected main provider identity'};[ordered]@{main_owner=$mainId[0];workers=@(Get-CimInstance Win32_Process | Where-Object {$_.ParentProcessId -eq $mainId[0] -and $_.Name -eq 'llama-server.exe'} | Select-Object ProcessId,CommandLine)} | ConvertTo-Json -Depth 5 -Compress"
provider = json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',command],text=True))
for worker in provider['workers']:
    port = re.search(r'--port\s+(\d+)', worker['CommandLine']).group(1)
    worker['slots'] = get('http://127.0.0.1:' + port + '/slots')
    assert all(not row['is_processing'] for row in worker['slots']), 'Actual model request active; do not compete.'
product = {}
for project in ('20261021094952722-147a3d72','20261020103707202-0fda8601'):
    headers={'X-Project-ID':project}
    product[project] = {name:get('http://127.0.0.1:13500' + endpoint,headers=headers)
                       for name,endpoint in (('draft','/api/engineering/agent/project-draft'),
                                             ('conversation','/api/engineering/agent/conversation'))}
    conversation = product[project]['conversation'].get('data') or {}
    assert conversation.get('active_workload') is None and conversation.get('active_proposal') is None
info = get('http://127.0.0.1:11434/api/show',{'model':'qwen3.8:27b'})
assert str(info['details']['family']).startswith('qwen') and not info.get('remote_host') and not info.get('remote_model')
write('preflight.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'provider':provider,'product':product,
                        'main_ps':get('http://127.0.0.1:11434/api/ps'),'qwen_details':info['details'],
                        'product_observation_is_not_global_queue_enumeration':True})
prepared = intake.prepare_reference_design(fixture_request(references=[reference(('ports',))]))
owners=('owner-a','owner-b','owner-c') if args.prefix_cache else ('owner-a','owner-b')
schema = _reference_schema_for_stage(prepared, {'ports'}, port_intent=not args.port_groups,
                                    port_groups=args.port_groups, device_ids=owners)
known=[{'id':'port-'+hashlib.sha256(b'owner-a').hexdigest()[:24]+'-1','device_id':'earlier-owner'},
       {'id':'port-idc-eth-01','device_id':'another-earlier-owner'}]
known_before=json.loads(json.dumps(known))
technology=prepared['catalog']['technology_ids'][0]
messages=[{'role':'user','content':'Authored native port identity counterprobe, no project writes. '
    'Return port_intents containing exactly two '+technology+' LOCAL physical port records: '
    'one for owner-a and one for owner-b. Each has network_scope authored-network, parameters {}, '
    'a short rationale and empty field_references. Select device_id first. Never supply id; '
    'NIS assigns new IDs afterward. All ordinary model arrays, including ports, remain empty. /no_think'}]
if args.port_pages or args.prefix_cache:
    messages=[{'role':'user','content':'Authored native port-page counterprobe, no project writes. '
        'There are exactly two required physical ports in total, one for owner-a and one for owner-b. '
        'For this first reply emit only the owner-a port in port_intents and port_intents_complete=false, '
        'because owner-b remains for the next reply. Technology '+technology+', role LOCAL, '
        'network_scope authored-network, parameters {}, a short rationale, empty field_references. '
        'Do not supply id. Every ordinary model array, including ports, remains empty. /no_think'}]
if args.port_groups:
    technology = 'ethernet'
    assert technology in prepared['catalog']['technology_ids']
    messages = [{'role': 'user', 'content':
        'Authored finite physical-demand counterexample only: no Original model or hardware qualification. '
        'There are exactly SEVENTEEN separate physical ethernet BACKBONE connectors for owner-a and '
        'exactly TWO for owner-b. These deliberately identical parallel physical connections are explicitly '
        'required by this authored scenario, not inferred from VLANs or logical functions. '
        'Produce ONE COMPLETE port_groups_by_device object with exactly both literal owner keys. '
        'Each owner has connections containing exactly one group: technology ethernet, role BACKBONE, '
        'network_scope authored-backbone, parameters {}, a short rationale, empty field_references, '
        'and count exactly17 for owner-a or exactly2 for owner-b. Each owner also has a short rationale. '
        'Set port_plan_complete=true. NIS expands these exact finite counts into individual IDs; '
        'do not supply IDs, device_id fields, ordinary ports or a never-ending next connector. '
        'All ordinary arrays including devices/ports/unresolved remain empty. /no_think'}]
if args.context_delta:
    from backend.tests.test_reference_context_delta_capacity import complete_authored_context
    context_fixture_source = ROOT / 'backend/tests/test_reference_context_delta_capacity.py'
    context_fixture_hash = hashlib.sha256(context_fixture_source.read_bytes()).hexdigest()
    context = complete_authored_context()
    selected_channels = {index: secrets.randbelow(1000000000) for index in (0, 17, 31)}
    selected_address = 'authored-' + secrets.token_hex(12)
    selected_typed_values = [secrets.randbelow(1000000000), False, None]
    inherited_values = ['authored-base-' + secrets.token_hex(12), 'authored-late-' + secrets.token_hex(12)]
    for index, row in enumerate(context['current_candidate']['ports']):
        row['parameters']['inherited_value'] = inherited_values[index >= 16]
    for index, channel in selected_channels.items():
        context['current_candidate']['ports'][index]['parameters']['local_channel_index'] = channel
    context['current_candidate']['ports'][31]['parameters']['address_binding'] = selected_address
    context['current_candidate']['ports'][31]['parameters'][''] = selected_typed_values
    context['instruction'] = (
        'This is an authored private context reconstruction counter, never a real model or hardware decision. '
        'Reconstruct the complete current context using the documented tables and ordered RFC6902 operations. '
        'Return ONLY the requested facts: ports_count and devices_count from current_candidate; '
        'first_channel, middle_channel and last_channel from ports at indices0,17,31 parameters.local_channel_index; '
        'last_address from ports[31].parameters.address_binding; '
        'last_typed_values from ports[31].parameters[the empty-string key]; '
        'first_inherited_value and last_inherited_value from ports[0] and ports[31] '
        'parameters.inherited_value, tracing their actual copy bases and later replacements; '
        'last_zero_literal is the original JSON numeric spelling as a STRING for ports[31].parameters["a/b~c"]; '
        'source_role from reference_sources.R.role. Do not infer another ordinal, use actual reconstructed fields. /no_think')
    messages, _, _ = _reference_context_messages([], None, context,
        'Read the complete private context faithfully and answer the exact authored read-only query.', 131072)
    packed = json.loads(messages[1]['content'])
    assert any(operation['op'] == 'replace' for operation in packed['nis_context_copies'])
    expected = {'ports_count': 32, 'devices_count': 80, 'first_channel': selected_channels[0],
                'middle_channel': selected_channels[17], 'last_channel': selected_channels[31],
                'last_address': selected_address, 'last_typed_values': selected_typed_values,
                'first_inherited_value': inherited_values[0], 'last_inherited_value': inherited_values[1],
                'last_zero_literal': '-0.0', 'source_role': 'REFERENCE_SUPPLEMENT'}
    schema = {'type': 'object', 'properties': {
        **{key: {'type': 'integer'} for key in ('ports_count', 'devices_count', 'first_channel',
                                               'middle_channel', 'last_channel')},
        **{key: {'type': 'string'} for key in ('last_address', 'last_zero_literal', 'source_role',
                                              'first_inherited_value', 'last_inherited_value')},
        'last_typed_values': {'type': 'array', 'items': {'anyOf': [
            {'type': 'integer'}, {'type': 'boolean'}, {'type': 'null'}]}}},
        'required': list(expected), 'additionalProperties': False}
    write('authored-complete-context.json', context)
    write('expected-reconstructed-values.json', expected)
payload={'model':'qwen3.8:27b','messages':messages,'format':schema,'think':False,'stream':False,
         'keep_alive':'10m','options':{'temperature':0,'num_predict':8192,
                                      'num_ctx':_reference_context_window(messages,131072)}}
if not args.prefix_cache:
    write('request.json',payload)
write('started.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'pid':os.getpid(),'actual_model_requests':1})
if args.context_delta:
    response = get('http://127.0.0.1:11434/api/chat', payload)
    write('response.json', response)
    assert response.get('done_reason') == 'stop'
    value = json.loads(response['message']['content'])
    Draft202012Validator(schema).validate(value)
    assert json.dumps(value, sort_keys=True) == json.dumps(expected, sort_keys=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    assert hashlib.sha256(context_fixture_source.read_bytes()).hexdigest() == context_fixture_hash
    result = {'status': 'PASSED', 'at_utc': datetime.now(timezone.utc).isoformat(),
        'actual_model_requests': 1, 'authored_complete_context_reconstructed': True,
        'input_utf8_bytes': sum(len(row['content'].encode('utf-8')) for row in messages),
        'source_sha256': source_hash, 'eval_count': response.get('eval_count'),
        'authored_fixture_sha256': context_fixture_hash,
        'prompt_eval_count': response.get('prompt_eval_count'), 'canonical_writes': False,
        'original_model_acceptance': False, 'provider_model_context_output_timeout_unchanged': True}
    write('result.json', result)
    print(json.dumps(result), flush=True)
    sys.exit(0)
if args.port_groups:
    response = get('http://127.0.0.1:11434/api/chat', payload)
    write('response.json', response)
    assert response.get('done_reason') == 'stop'
    value = json.loads(response['message']['content'])
    Draft202012Validator(schema).validate(value)
    native_groups = value.pop('port_groups_by_device')
    complete = value.pop('port_plan_complete')
    assert complete is True and set(native_groups) == set(owners)
    for owner, count in (('owner-a', 17), ('owner-b', 2)):
        decisions = native_groups[owner]['connections']
        assert len(decisions) == 1 and decisions[0]['count'] == count
        assert decisions[0]['technology'] == technology and decisions[0]['role'] == 'BACKBONE'
        assert decisions[0]['network_scope'] == 'authored-backbone' and decisions[0]['parameters'] == {}
    assert all(value.get(field, []) == [] for field in
        ('devices', 'ports', 'measurements', 'commands', 'functions', 'communication', 'functional_dependencies', 'unresolved'))
    value['ports'] = _reference_expand_port_groups(known, native_groups, owners, complete)
    public = intake.ReferenceDesignProposal.model_validate(value).model_dump(mode='json')
    Draft202012Validator(intake.reference_design_schema(prepared)).validate(public)
    assert len(public['ports']) == len({row['id'] for row in public['ports']}) == 19
    assert not {row['id'] for row in public['ports']} & {row['id'] for row in known}
    for owner, count in (('owner-a', 17), ('owner-b', 2)):
        native = {key: v for key, v in native_groups[owner]['connections'][0].items() if key != 'count'}
        expected = intake.ReferencePort.model_validate({'id': 'comparison', 'device_id': owner, **native}).model_dump(mode='json')
        rows = [row for row in public['ports'] if row['device_id'] == owner]
        assert len(rows) == count
        assert all({key: v for key, v in row.items() if key != 'id'} ==
                   {key: v for key, v in expected.items() if key != 'id'} for row in rows)
    assert known == known_before and hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    write('normal-public-port-records.json', public['ports'])
    result = {'status': 'PASSED', 'at_utc': datetime.now(timezone.utc).isoformat(),
        'actual_model_requests': 1, 'complete_native_demand': True,
        'explicit_native_counts': {'owner-a': 17, 'owner-b': 2}, 'individual_ports_preserved': 19,
        'all_native_technical_choices_preserved': True, 'existing_ports_unmodified': True,
        'source_sha256': source_hash, 'eval_count': response.get('eval_count'),
        'canonical_writes': False, 'original_model_acceptance': False,
        'provider_model_context_output_timeout_unchanged': True}
    write('result.json', result)
    print(json.dumps(result), flush=True)
    sys.exit(0)
if args.port_pages or args.prefix_cache:
    all_intents=[]
    rows=[]
    responses=[]
    history, previous, native_anchor = [], None, None
    context = {'original_source': 'Authored counterexample only, no real hardware or Original acceptance. '
               'Exactly three physical ports are required: one each for owner-a, owner-b, owner-c. '
               'Each uses technology '+technology+', role LOCAL, network_scope authored-network, '
               'parameters {}, short rationale and empty field_references. NIS assigns IDs.',
               'current_candidate': {'ports': []}, 'typed': [False, 0, 0.0, None]}
    for index, owner in enumerate(owners):
        if args.prefix_cache:
            context = deepcopy(context)
            context['current_candidate']['ports'] = deepcopy(rows)
            context['planning_stage'] = 'Authored bounded physical port page'
            context['device_ids_for_this_stage'] = list(owners)
            context['instruction'] = ('Emit exactly one port_intents record for '+owner+'. '
                'Set port_intents_complete='+('true' if index==len(owners)-1 else 'false')+'. '
                'All ordinary arrays, including ports and unresolved, remain empty. '
                'Apply the actual NIS context patch; preserve earlier ports, never repeat one. /no_think')
            if index:
                # A complete stable authored review record enters on page2.
                # Page3 must reuse it, not process it again from an old anchor.
                context['stable_reviewed_context'] = 'Authored cache data, no physical evidence: ' + 'K' * 10000
            built, _, rebased = _reference_context_messages(
                history, previous, context, 'Execute only the supplied authored native decoder counterexample.',
                131072, anchor=native_anchor)
            if index:
                assert not rebased and built[:-1] == history
            payload['messages'] = built
            write('context-'+str(index+1)+'.json',context)
            write('context-build-'+str(index+1)+'.json',{
                'context_rebased':rebased,'exact_prior_native_history_prefix':bool(index and built[:-1]==history),
                'total_input_utf8_bytes':sum(len(row['content'].encode('utf8')) for row in built)})
        elif index:
            payload['messages'].extend([
                {'role':'assistant','content':responses[-1]['message']['content']},
                {'role':'user','content':'The owner-a port has now been planned. Emit only the remaining owner-b port, '
                 'same technology '+technology+' and same other technical facts. Set port_intents_complete=true '
                 'because both required ports are now covered. All ordinary model arrays remain empty. /no_think'}])
        payload['options']['num_ctx']=_reference_context_window(payload['messages'],131072)
        if args.prefix_cache and index==0:
            write('request.json',payload)
        write('request-'+str(index+1)+'.json',payload)
        response=get('http://127.0.0.1:11434/api/chat',payload)
        write('response-'+str(index+1)+'.json',response)
        responses.append(response)
        if args.prefix_cache:
            history = [*deepcopy(payload['messages']), {'role':'assistant','content':response['message']['content']}]
            previous = deepcopy(context)
            if native_anchor is None:
                native_anchor = (deepcopy(history), deepcopy(context))
        assert response.get('done_reason')!='length'
        value=json.loads(response['message']['content'])
        Draft202012Validator(schema).validate(value)
        intents=value.pop('port_intents')
        complete=_reference_port_page_complete(intents,value.pop('port_intents_complete'))
        assert complete is (index==len(owners)-1) and len(intents)==1
        assert intents[0]['device_id']==owner and intents[0]['technology']==technology
        assert intents[0]['role']=='LOCAL' and intents[0]['network_scope']=='authored-network'
        assert not intents[0]['parameters'] and 'id' not in intents[0]
        assert all(value.get(field,[])==[] for field in ('devices','ports','measurements','commands','functions','communication','functional_dependencies','unresolved'))
        new=_reference_expand_port_intents([*known,*rows],intents,owners)
        value['ports']=new
        public=intake.ReferenceDesignProposal.model_validate(value).model_dump(mode='json')
        Draft202012Validator(intake.reference_design_schema(prepared)).validate(public)
        for actual,native in zip(public['ports'],intents):
            expected=intake.ReferencePort.model_validate({'id':'comparison',**native}).model_dump(mode='json')
            assert {k:v for k,v in actual.items() if k!='id'}=={k:v for k,v in expected.items() if k!='id'}
        all_intents.extend(intents);rows.extend(public['ports'])
    assert known==known_before and hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
    assert len(rows)==len({row['id'] for row in rows})==len(owners)
    assert not {row['id'] for row in rows}&{row['id'] for row in known}
    write('normal-public-port-records.json',rows)
    result={'status':'PASSED','at_utc':datetime.now(timezone.utc).isoformat(),'actual_model_requests':len(owners),
        'bounded_native_pages_with_false_then_true_completion':True,'all_technical_choices_preserved':True,
        'fresh_ids_skip_existing_and_prior_page_ids':True,'source_sha256':source_hash,
        'eval_counts':[r.get('eval_count') for r in responses],'canonical_writes':False,
        **({'prefix_wire_counterprobe':True,
            'prompt_eval_counts':[r.get('prompt_eval_count') for r in responses],
            'exact_native_history_prefix_preserved':True,
            'prompt_eval_counts_are_provider_reported_not_uncached_work':True,
            'actual_cache_reuse_validation':'REQUIRES_INDEPENDENT_ACTIVE_WORKER_OBSERVATIONS'} if args.prefix_cache else {}),
        'original_model_acceptance':False,'provider_model_context_output_timeout_unchanged':True}
    write('result.json',result)
    print(json.dumps(result),flush=True)
    sys.exit(0)
response=get('http://127.0.0.1:11434/api/chat',payload)
write('response.json',response)
assert response.get('done_reason')!='length'
value=json.loads(response['message']['content'])
Draft202012Validator(schema).validate(value)
intents=value.pop('port_intents')
assert value.get('ports',[])==[] and len(intents)==2
assert {row['device_id'] for row in intents}==set(owners)
assert all('id' not in row and row['technology']==technology and not row['parameters'] for row in intents)
value['ports']=_reference_expand_port_intents(known,intents,owners)
public=intake.ReferenceDesignProposal.model_validate(value).model_dump(mode='json')
Draft202012Validator(intake.reference_design_schema(prepared)).validate(public)
ids=[row['id'] for row in public['ports']]
assert len(set(ids))==2 and not set(ids)&{row['id'] for row in known}
for before,after in zip(intents,public['ports']):
    expected=intake.ReferencePort.model_validate({'id':'authored-comparison',**before}).model_dump(mode='json')
    assert {key:item for key,item in after.items() if key!='id'}=={key:item for key,item in expected.items() if key!='id'}
assert known==known_before and hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
write('normal-public-port-records.json',public['ports'])
result={'status':'PASSED','at_utc':datetime.now(timezone.utc).isoformat(),'actual_model_requests':1,
        'native_id_free_schema_and_public_contract_valid':True,'fresh_unique_owner_bound_port_ids':ids,
        'all_native_technical_decisions_preserved':True,'known_ports_unmodified':True,
        'source_sha256':source_hash,'eval_count':response.get('eval_count'),'canonical_writes':False,
        'original_model_acceptance':False,'provider_model_context_output_timeout_unchanged':True}
write('result.json',result)
print(json.dumps(result),flush=True)
