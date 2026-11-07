"""Metadata-only main-provider and production identity snapshot; never generates tokens."""
from datetime import datetime, timezone
import argparse
import hashlib
import sys
import json
from pathlib import Path
import subprocess
import urllib.request

out = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--model', choices=['llama3.1:8b', 'qwen3.5:9b'], default='llama3.1:8b')
parser.add_argument('--observe-running', action='store_true')
args = parser.parse_args()
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
def get(url, payload=None):
    request = urllib.request.Request(url, data=None if payload is None else json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    with opener.open(request, timeout=15) as response:
        return json.load(response)

ps = get('http://127.0.0.1:11434/api/ps')
tags = get('http://127.0.0.1:11434/api/tags')
model = next(row for row in tags['models'] if row['name'] == args.model)
show = get('http://127.0.0.1:11434/api/show', {'model': args.model})
assert show['details']['format'] == 'gguf'
if args.model == 'llama3.1:8b':
    assert show['details']['family'] == 'llama'
sys.path.insert(0, str(out.parents[2]))
from backend.nis.agent.orchestration.host_tokenizer import _processes
main_process, main_worker = _processes()
main, children = [main_process], [main_worker]
slots = []
for worker in children:
    import re
    port = int(re.search(r'--port\s+(\d+)', worker['CommandLine']).group(1))
    slots.append({'worker': worker, 'slots': get('http://127.0.0.1:' + str(port) + '/slots')})
busy = sum(bool(slot.get('is_processing')) for item in slots for slot in item['slots'])
if not args.observe_running:
    assert busy == 0, 'Busy main worker; no new request permitted'
docker = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
container = json.loads(subprocess.check_output([docker, 'inspect', 'NetworkIS'], encoding='utf-8'))[0]
assert container['Image'] == 'sha256:c7edda158398ce6c13b5563f56df70575aa61345539fbc23a5aeb847164fca33'
env = dict(item.split('=',1) for item in container['Config']['Env'] if '=' in item)
assert env['LOCAL_AI_MODEL'] == env['LOCAL_AI_FAST_MODEL'] == 'llama3.1:8b'
report = {'at': datetime.now(timezone.utc).isoformat(), 'scope': 'Metadata and actual main-provider direct-child slots only; private provider not queried or changed',
          'main_process': main[0], 'main_workers': children, 'slots': slots, 'ps': ps, 'model': model,
          'details': show['details'], 'capabilities': show.get('capabilities'), 'advertised_template': show.get('template'),
          'model_context_metadata': {key:value for key,value in show.get('model_info',{}).items() if 'context_length' in key or key == 'general.parameter_count'},
          'production_image': container['Image'], 'production_build': get('http://127.0.0.1:13500/api/build-info'),
          'production_ready': get('http://127.0.0.1:13500/api/ready'),
          'effective_model_environment': {key:value for key,value in env.items() if key.startswith('LOCAL_AI_') and 'KEY' not in key and 'TOKEN' not in key}}
destination = out / ('provider-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.json')
destination.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'path':str(destination),'loaded_models':[row['name'] for row in ps.get('models',[])], 'main_pid':main[0]['ProcessId'], 'workers':len(children), 'busy_slots':busy, 'model':model['name'], 'context_metadata':report['model_context_metadata'],
                  'slot_progress':[{key:slot.get(key) for key in ['id','id_task','is_processing','n_ctx','next_token','n_prompt_tokens']} for item in slots for slot in item['slots']]}))
