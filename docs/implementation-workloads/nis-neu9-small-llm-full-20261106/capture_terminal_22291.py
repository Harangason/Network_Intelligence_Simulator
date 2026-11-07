"""Read-only capture of the naturally failed attempt; never starts inference."""
from pathlib import Path
import hashlib
import json
import subprocess
import urllib.request
from datetime import datetime, timezone

goal = Path(__file__).resolve().parent
attempt = goal / 'attempt-10'
state = json.loads((attempt / 'state.json').read_text(encoding='utf-8'))
assert state['status'] == 'NATIVE_PLAN_REFERENCE_FAILED'
out = attempt / 'terminal-22291-verified'
out.mkdir(exist_ok=True)
assert not (out / 'manifest.json').exists()
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
evidence, bodies = [], {}
for name, path in [('bundle', '/api/engineering/projects/export'),
                   ('draft', '/api/engineering/agent/project-draft'),
                   ('jobs', '/api/simulations'),
                   ('reference', '/api/engineering/agent/document-reference-design')]:
    with opener.open(urllib.request.Request(state['base_url'] + path,
                     headers={'X-Project-ID': state['project_id']}), timeout=30) as response:
        raw, status = response.read(), response.status
    target = out / (name + '.json')
    target.write_bytes(raw)
    bodies[name] = json.loads(raw)
    evidence.append({'path': str(target), 'sha256': hashlib.sha256(raw).hexdigest(), 'status': status})
counts = {key: len(value) for key, value in bodies['bundle']['source_data'].items()}
assert not any(counts.values()) and bodies['jobs']['jobs'] == []
docker = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
logs = subprocess.run([docker, 'logs', state['containers']['app']], capture_output=True, check=True)
(out / 'container.log').write_bytes(logs.stdout + logs.stderr)
subprocess.run([docker, 'cp', state['containers']['app'] + ':/app/var/runtime/logs/backend.log', str(out / 'backend.log')], check=True)
for name in ('state.json', 'plan-reference/response.json', 'plan-reference/events.ndjson'):
    raw = (attempt / name).read_bytes()
    target = out / Path(name).name
    target.write_bytes(raw)
    evidence.append({'path': str(target), 'sha256': hashlib.sha256(raw).hexdigest()})
manifest = dict(at=datetime.now(timezone.utc).isoformat(), session=22291, exit_code=1,
    normal_terminal_result=json.loads((out / 'response.json').read_text(encoding='utf-8')),
    state_status=state['status'], python_processes_absent_verified=[48216, 51464],
    provider_idle_evidence='provider-20261107T081116Z.json', canonical_counts=counts,
    jobs=[], evidence=evidence,
    backend_log_sha256=hashlib.sha256((out / 'backend.log').read_bytes()).hexdigest(),
    actual_last_complete_context_retained=False, production_changed=False)
(out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'manifest': str(out / 'manifest.json'), 'canonical_counts': counts, 'jobs': []}))
