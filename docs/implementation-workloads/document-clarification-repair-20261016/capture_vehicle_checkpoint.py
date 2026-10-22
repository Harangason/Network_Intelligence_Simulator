"""Capture existing product evidence using GET only; never generate or fix a model."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import quote
from urllib.request import Request, urlopen

PROJECT = '20261016122109077-dc3a1aeb'
BASE = 'http://127.0.0.1:13500'
OUT = Path(__file__).resolve().parent
SOURCE = Path('C:/Users/marti/PycharmProjects/Benchmark_Modelle/Fahrzeug komplett.txt')
SOURCE_SHA256 = '86865975c689643d9b07ea73e21d68fa6f4a3a8770402ffb537dba2d7ecdf4d7'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('checkpoint')
parser.add_argument('--job-id')
args = parser.parse_args()
assert re.fullmatch(r'[a-z0-9-]+', args.checkpoint), 'Use a plain checkpoint name.'
dest = OUT / 'product-checkpoints' / args.checkpoint
dest.mkdir(parents=True, exist_ok=False)
manifest = {'at': datetime.now(timezone.utc).isoformat(), 'project_id': PROJECT,
            'base_url': BASE, 'scope': 'Existing saved evidence, GET only; no test PASS inferred.',
            'records': [], 'counts': {}, 'canonical_writes': False}


def read(name, endpoint):
    request = Request(BASE + endpoint, headers={'X-Project-ID': PROJECT}, method='GET')
    with urlopen(request, timeout=90) as response:
        raw = response.read()
    payload = json.loads(raw)
    (dest / (name + '.json')).write_bytes(raw)
    manifest['records'].append({'name': name, 'endpoint': endpoint,
                                'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    return payload


try:
    original = SOURCE.read_bytes()
    source_hash = hashlib.sha256(original).hexdigest()
    manifest['original_source'] = {'path': str(SOURCE), 'sha256': source_hash,
                                   'bytes': len(original), 'characters': len(original.decode('utf-8'))}
    assert source_hash == SOURCE_SHA256, 'Original source changed; do not substitute silently.'
    read('build-info', '/api/build-info')
    read('ready', '/api/ready')
    workflow = read('workflow', '/api/engineering/workflow')
    assert workflow['project_id'] == 'network-project-' + PROJECT, workflow.get('project_id')
    manifest['statuses'] = workflow.get('statuses')
    for resource in ('hardware-nodes', 'functions', 'interfaces', 'messages', 'signals',
                     'hardware-interfaces', 'relations', 'routing'):
        total = 0
        for page in range(200):
            payload = read(f'{resource}-{page:03}',
                           f'/api/engineering/{resource}?limit=500&offset={page * 500}')
            items = payload['items']
            total += len(items)
            if len(items) < 500:
                break
        else:
            raise RuntimeError(f'{resource}: pagination bound reached; evidence is incomplete.')
        manifest['counts'][resource] = total
    read('network-view', '/api/engineering/workflow/network-view')
    jobs = read('simulation-jobs', '/api/simulations')['jobs']
    snapshots = read('simulation-snapshots', '/api/engineering/workflow/snapshots')['simulations']
    if args.job_id:
        assert any(j.get('id', j.get('job_id')) == args.job_id for j in jobs), 'Job absent from this project.'
        read('simulation-job', '/api/simulations/' + quote(args.job_id, safe=''))
        matches = [s for s in snapshots if s.get('job_id') == args.job_id]
        assert matches, 'No governing saved workflow snapshot found for this job.'
        for index, snapshot in enumerate(matches):
            read(f'simulation-snapshot-{index}', '/api/engineering/workflow/simulation-snapshots/'
                 + quote(snapshot['id'], safe=''))
        cursor = 0
        for page in range(1000):
            payload = read(f'trace-{page:04}', '/api/simulations/' + quote(args.job_id, safe='')
                           + f'/trace-window?limit=1000&cursor={cursor}')
            if not payload['has_more']:
                break
            assert payload['next_cursor'] > cursor, 'Trace cursor did not advance.'
            cursor = payload['next_cursor']
        else:
            raise RuntimeError('Trace pagination bound reached; evidence is incomplete.')
    manifest['capture_status'] = 'COMPLETE_GET_CAPTURE'
except Exception as error:
    manifest['capture_status'] = 'INCOMPLETE_GET_CAPTURE'
    manifest['error'] = f'{type(error).__name__}: {error}'
    raise
finally:
    (dest / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: manifest.get(k) for k in ('capture_status', 'project_id', 'counts', 'error')}, ensure_ascii=False))
