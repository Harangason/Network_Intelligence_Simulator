"""Read-only deployment evidence; run only after complete release delivery."""
import datetime
import json
from pathlib import Path
import subprocess
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
RECEIPT = ROOT / 'backend/test-output/release-gates/delivery-488ac00bf2cd/b106f2e968ff/receipt.json'
PROJECT = 'network-project-20261008035128534-d555f433'
DOCKER = r'C:\Users\marti\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'


def read(path, *, project=False, base='http://127.0.0.1:13500'):
    request = Request(base + path, headers={'X-Project-ID': PROJECT} if project else {})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


receipt = json.loads(RECEIPT.read_text(encoding='utf-8'))
assert receipt['status'] == 'PASS', 'Full release is not PASS'
image = subprocess.check_output([DOCKER, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip()
ready = read('/api/ready')
build = read('/api/build-info')
lan_ready = read('/api/ready', base='http://192.168.178.10:13500')
assert image == receipt['image_id'], 'Running image differs from tested image'
assert build['source_sha256'] == receipt['release']['source_sha256'], 'Running source differs'
assert ready['status'] == lan_ready['status'] == 'ready', 'Local/LAN readiness failed'
workflow = read('/api/engineering/workflow?view=summary', project=True)
snapshots = read('/api/engineering/workflow/snapshots', project=True)
jobs = read('/api/simulations', project=True)
execution = workflow.get('context', {}).get('agent_execution', {})
evidence = {
    'status': 'PASSED',
    'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'receipt': str(RECEIPT),
    'image_id': image,
    'source_sha256': build['source_sha256'],
    'build_id': build.get('build_id'),
    'ready': ready,
    'lan_ready': lan_ready,
    'project_id': workflow.get('project_id'),
    'statuses': workflow.get('statuses'),
    'snapshot_ids': [item['id'] for item in snapshots.get('simulations', [])],
    'job_ids': [item['id'] for item in jobs.get('jobs', [])],
    'execution_state': execution.get('state'),
    'execution_step': execution.get('step'),
    'run_id': execution.get('run_id'),
    'scope': 'Exact production image, source, localhost/LAN readiness and existing project workflow/snapshot/job reads. No production writes.',
    'limitation': 'Completed-run finish/reload/fresh-session behavior is proved by the real isolated nine-stage browser case on this exact image. No production simulation is created for verification.',
}
(HERE / 'production-verification.json').write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps(evidence, ensure_ascii=False))
