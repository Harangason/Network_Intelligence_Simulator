"""Read-only native Qwen verification inside the exact deployed NIS image."""
import hashlib
import importlib.util
import json
import runpy
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
receipt = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
assert runpy.run_path(str(ROOT / 'scripts/release_storage.py'))['complete_pass'](receipt)
freeze = json.loads((HERE / 'source-freeze.json').read_text(encoding='utf-8'))
native = json.loads((HERE / freeze['native_evidence'] / 'manifest.json').read_text(encoding='utf-8'))
assert len(native['cases']) == 7 and all(c['status'] == 'RETEST_PASSED' for c in native['cases'])
assert native['full_application_source_sha256'] == receipt['release']['source_sha256']
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']


def running_image():
    return subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip()


assert running_image() == receipt['image_id']
case = next(c for c in native['cases'] if c['id'] == 'building')
raw = Path(case['original_path']).read_bytes()
assert hashlib.sha256(raw).hexdigest() == case['source_sha256']
payload = {'source': raw.decode('utf-8'), 'source_name': case['file'], 'hash_paths': list(native['application_hashes'])}
code = '''
import asyncio,hashlib,json,sys
from pathlib import Path
from backend.nis.agent.orchestration.local_reasoner import LocalEngineeringReasoner
data=json.load(sys.stdin)
async def run():
    reasoner=LocalEngineeringReasoner()
    calls=[]
    async def capture(response):
        if response.request.url.path=='/api/chat':
            await response.aread()
            actual=response.json()
            calls.append({'model':actual.get('model'),'eval_count':actual.get('eval_count'),
                          'total_duration':actual.get('total_duration'),'endpoint':str(response.request.url)})
    reasoner.client.event_hooks['response']=[capture]
    hashes={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in data['hash_paths']}
    try:
        result=await reasoner.interpret_document(data['source'],data['source_name'])
        print(json.dumps({'result':result,'calls':calls,'module_hashes':hashes},ensure_ascii=False))
    finally:
        await reasoner.client.aclose()
asyncio.run(run())
'''
process = subprocess.run([docker, 'exec', '-i', 'NetworkIS', 'python', '-c', code],
                         input=json.dumps(payload, ensure_ascii=False), capture_output=True,
                         text=True, encoding='utf-8', timeout=1300)
if process.returncode:
    (HERE / 'production-native-error.txt').write_text(process.stderr, encoding='utf-8')
assert process.returncode == 0, process.stderr
observed = json.loads(process.stdout)
assert observed['module_hashes'] == native['application_hashes']
result = observed['result']
assert result['source_sha256'] == case['source_sha256'] and result['source_complete']
assert result['canonical_writes'] is False and result['approval_required'] is True
assert observed['calls'] and all(c['model'] == native['model'] and c['eval_count'] > 0 for c in observed['calls'])
spec = importlib.util.spec_from_file_location('qwen_verification_oracles', HERE / 'probe.py')
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)
assert oracle.semantic_oracle('building', result) == []
assert running_image() == receipt['image_id']
with urlopen('http://127.0.0.1:13500/api/ready', timeout=15) as response:
    ready = json.load(response)
with urlopen('http://127.0.0.1:13500/api/build-info', timeout=15) as response:
    build = json.load(response)
assert ready['status'] == 'ready' and build['source_sha256'] == receipt['release']['source_sha256']
evidence = {'status': 'PASSED', 'expected_image': receipt['image_id'], 'running_image': running_image(),
            'scope': 'Native document proposal inside deployed container; no database or canonical model mutation',
            'ready': ready, 'build': build, **observed}
(HERE / 'production-verification.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'status': 'PASSED', 'image': receipt['image_id'], 'model': native['model'],
                  'calls': len(observed['calls']), 'canonical_writes': False}))
