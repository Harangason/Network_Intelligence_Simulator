"""Run the prepared read-only probe in the exact already-delivered image."""
import hashlib
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone

directory = Path(__file__).resolve().parent
root = directory.parents[2]
receipt_path = root / 'backend/test-output/release-gates/delivery-9ba63de4dd43/cd21261e671d/receipt.json'
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
assert receipt['status'] == 'PASS'
docker = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
running = subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip()
assert running == receipt['image_id']
script = (directory / 'production_probe.py').read_bytes()
started = datetime.now(timezone.utc).isoformat()
command = [docker, 'exec', '-i', '-e', 'NIS_PROBE_EXPECTED_SOURCE=' + receipt['release']['source_sha256'],
           'NetworkIS', 'python', '-']
with (directory / 'production-probe.stdout.json').open('wb') as stdout, (directory / 'production-probe.stderr.log').open('wb') as stderr:
    result = subprocess.run(command, input=script, stdout=stdout, stderr=stderr)
report = {'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
          'exit_code': result.returncode, 'image_id': running,
          'source_sha256': receipt['release']['source_sha256'],
          'script_sha256': hashlib.sha256(script).hexdigest(),
          'scope': 'Actual selected Llama component checks inside deployed image; no project tool execution or canonical writes',
          'outputs': []}
for name in ['production-probe.stdout.json', 'production-probe.stderr.log']:
    path = directory / name
    report['outputs'].append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
if result.returncode == 0:
    body = json.loads((directory / 'production-probe.stdout.json').read_bytes())
    assert body['status'] == 'PASSED'
    report['status'] = 'PASSED'
    report['checks'] = body['checks']
    report['seconds'] = body['seconds']
else:
    report['status'] = 'FAILED'
(directory / 'production-probe-process.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report), flush=True)
raise SystemExit(result.returncode)
