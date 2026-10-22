"""Observe only the native stack and already loaded local models."""
from pathlib import Path
import datetime
import json
import subprocess
from urllib.request import urlopen
OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[3]
runtime = json.loads((OUT / 'native-runtime-preparation.json').read_text(encoding='utf-8'))
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']
app = json.loads(subprocess.check_output([docker, 'inspect', runtime['containers']['app']], text=True, encoding='utf-8'))[0]
assert app['Image'] == runtime['image_id'] and app['Id'] == runtime['app_container_id']
assert app['Config']['Labels']['networkis.test'] == 'disposable'
stats = subprocess.check_output([docker, 'stats', '--no-stream', '--format', '{{json .}}', runtime['containers']['app'], 'NetworkIS'], text=True, encoding='utf-8')
with urlopen('http://127.0.0.1:11434/api/ps', timeout=5) as response:
    resident = json.load(response)
models = [{key: row.get(key) for key in ['name', 'size', 'size_vram', 'context_length', 'expires_at']} for row in resident.get('models', [])]
record = {'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'scope': 'Read-only observation; no inference/model loading/unloading, source mutation or SQL.', 'app_health': app['State'].get('Health', {}).get('Status'), 'resident_models': models, 'container_stats': [json.loads(line) for line in stats.splitlines() if line]}
with (OUT / 'native-runtime-observation.jsonl').open('a', encoding='utf-8') as stream:
    stream.write(json.dumps(record) + '\n')
print(json.dumps(record))
