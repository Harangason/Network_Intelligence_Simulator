"""One exact authored-stage replay with literal context; diagnosis only, no writes."""
import asyncio
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
import httpx
from jsonschema import Draft202012Validator
from backend.nis.agent.orchestration import local_reasoner as r
from backend.nis.agent.orchestration.reference_token_budget import ReferenceTokenBudget
from backend.tests.test_reference_reasoner import effective_reference_context

BASE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--variant', choices=['literal', 'decision-order'], default='literal')
ARGS = parser.parse_args()
OUT = BASE / ('literal-context-probe' if ARGS.variant == 'literal' else 'ordered-decisions-probe')


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


async def main():
    OUT.mkdir(exist_ok=False)
    admission = json.loads(subprocess.check_output([sys.executable, str(BASE.parent/'read_provider.py'),
        '--model', 'qwen3.5:9b'], encoding='utf-8'))
    save('admission.json', admission)
    path = BASE/'native-counter/request-6.json'
    payload = json.loads(path.read_text(encoding='utf-8'))
    assert 'port_groups_by_device' in payload['format']['properties']
    context = effective_reference_context(payload['messages'])
    original_context = json.dumps(context, ensure_ascii=False, sort_keys=True)
    if ARGS.variant == 'literal':
        payload['messages'] = [payload['messages'][0], {'role':'user',
            'content':json.dumps(context,ensure_ascii=False,separators=(',',':'))}]
    else:
        before_schema=json.dumps(payload['format'],sort_keys=True)
        for node in [payload['format'], *payload['format'].get('anyOf',[])]:
            properties=node['properties']
            node['properties']={key:properties[key] for key in
                [*('port_groups_by_device','port_plan_complete'),
                 *[key for key in properties if key not in {'port_groups_by_device','port_plan_complete','unresolved'}],
                 'unresolved']}
        assert json.dumps(payload['format'],sort_keys=True)==before_schema
    assert json.dumps(effective_reference_context(payload['messages']),ensure_ascii=False,sort_keys=True) == original_context
    save('context-identity.json', {'original_request':str(path),
        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'complete_context_sha256':hashlib.sha256(original_context.encode()).hexdigest(),
        'full_context_equal':True,'removed_sources':0,'removed_findings':0,'variant':ARGS.variant})
    async with httpx.AsyncClient(timeout=1200,trust_env=False) as client:
        budget = ReferenceTokenBudget(client,'http://127.0.0.1:11434/api/chat','qwen3.5:9b',131072)
        payload['options']['num_ctx'] = await budget.admit(payload['messages'])
        save('request.json',payload)
        with (OUT/'events.ndjson').open('w',encoding='utf-8') as log:
            def progress(event):
                log.write(json.dumps({'at':datetime.now(timezone.utc).isoformat(),**event})+'\n');log.flush()
            body=await r._reference_stream_response(client,'http://127.0.0.1:11434/api/chat',payload,progress)
        save('response.json',body)
        await budget.verify_response(payload['messages'],body)
        value=json.loads(body['message']['content']);Draft202012Validator(payload['format']).validate(value)
        complete=value['port_plan_complete'] is True
        if complete:
            ports=r._reference_expand_port_groups(context['current_candidate']['ports'],value['port_groups_by_device'],context['device_ids_for_this_stage'],True)
            assert len(ports)==4 and all(row['technology']=='can_fd' for row in ports)
        save('result.json',{'status':'PASS' if complete else 'FAIL','port_plan_complete':complete,
            'unresolved':value.get('unresolved',[]),'model':'qwen3.5:9b',
            'original_acceptance':False,'canonical_writes':False,'input_tokens':body.get('prompt_eval_count'),
            'output_tokens':body.get('eval_count')})
        print(json.dumps({'status':'PASS' if complete else 'FAIL','port_plan_complete':complete}),flush=True)
        return 0 if complete else 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
