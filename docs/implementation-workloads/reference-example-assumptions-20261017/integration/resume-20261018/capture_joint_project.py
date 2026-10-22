"""Capture actual application evidence via GET; no model writes or inference."""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('case', choices=['vehicle', 'robot'])
parser.add_argument('checkpoint')
parser.add_argument('--job-id')
parser.add_argument('--state', required=True, type=Path,
                    help='Explicit actual-run state; never infer an old project from case name.')
args = parser.parse_args()
assert re.fullmatch('[a-z0-9-]+', args.checkpoint)
case_dir = args.state.resolve().parent
state = json.loads(args.state.read_text(encoding='utf-8'))
project, base = state['project_id'], state['base_url']
assert hashlib.sha256(Path(state['source']).read_bytes()).hexdigest() == state['original_sha256']
dest = case_dir / args.checkpoint
dest.mkdir(exist_ok=False)
manifest = {'at_utc': datetime.now(timezone.utc).isoformat(), 'project_id': project,
            'base_url': base, 'image_id': state['image_id'], 'original_sha256': state['original_sha256'],
            'scope': 'Actual public GET responses only; no model edits, no generated replacement data, no inferred PASS.',
            'canonical_writes': False, 'records': []}

def read(name, endpoint):
    request = Request(base + endpoint, headers={'X-Project-ID': project}, method='GET')
    with urlopen(request, timeout=45) as response:
        raw = response.read()
    data = json.loads(raw)
    (dest / (name + '.json')).write_bytes(raw)
    manifest['records'].append({'name': name, 'endpoint': endpoint, 'bytes': len(raw),
                                'sha256': hashlib.sha256(raw).hexdigest()})
    return data

try:
    build = read('build-info', '/api/build-info')
    assert build['source_sha256'] == state['source_sha256']
    read('ready', '/api/ready')
    workflow = read('workflow', '/api/engineering/workflow')
    assert workflow['project_id'].removeprefix('network-project-') == project
    read('reference-design', '/api/engineering/agent/document-reference-design')
    # No target_project_id: export route must remain a pure read.
    bundle = read('project-bundle', '/api/engineering/projects/export')
    assert bundle['project_id'].removeprefix('network-project-') == project
    jobs = read('simulation-jobs', '/api/simulations')['jobs']
    snapshots = read('simulation-snapshots', '/api/engineering/workflow/snapshots')['simulations']
    if args.job_id:
        assert any(j.get('id', j.get('job_id')) == args.job_id for j in jobs)
        read('simulation-job', '/api/simulations/' + quote(args.job_id, safe=''))
        matches = [s for s in snapshots if s.get('job_id') == args.job_id]
        assert matches, 'Actual simulation has no governing workflow snapshot.'
        for index, snapshot in enumerate(matches):
            read(f'simulation-snapshot-{index}', '/api/engineering/workflow/simulation-snapshots/' + quote(snapshot['id'], safe=''))
        cursor = 0
        for page in range(1000):
            payload = read(f'trace-{page:04}', '/api/simulations/' + quote(args.job_id, safe='') + f'/trace-window?limit=1000&cursor={cursor}')
            if not payload['has_more']:
                break
            assert payload['next_cursor'] > cursor
            cursor = payload['next_cursor']
        else:
            raise AssertionError('Trace pagination is incomplete.')
    manifest['status'] = 'COMPLETE_GET_CAPTURE'
except Exception as error:
    manifest['status'] = 'INCOMPLETE_GET_CAPTURE'
    manifest['error'] = f'{type(error).__name__}: {error}'
    raise
finally:
    (dest / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: manifest.get(k) for k in ['status', 'project_id', 'error']}))
