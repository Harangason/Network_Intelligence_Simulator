"""Preserve interruption evidence and remove only this abandoned disposable stack."""
import datetime
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[3]
folder = Path(__file__).resolve().parent
gate = root / 'backend/test-output/release-gates/studio-toolbar-performance-full/42a674cad1bc'
receipt = json.loads((gate / 'receipt.json').read_text())
assert receipt['status'] == 'RUNNING' and receipt['gate_pid'] == 45152
docker = json.loads((root / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
processes = json.loads(subprocess.check_output(['pwsh', '-NoProfile', '-Command',
    "@(Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -eq 45152 -or ($_.Name -match '^python' -and $_.CommandLine -match 'run-release-gate\\.py') } | Select-Object ProcessId,Name,CreationDate) | ConvertTo-Json -AsArray"], text=True) or '[]')
assert not processes, processes
def inspect(kind, name):
    return json.loads(subprocess.check_output([docker, kind, 'inspect', name], text=True))[0]
names = receipt['containers']
resources = {}
for kind, key in [('container', 'app'), ('container', 'db'), ('network', 'network'), ('volume', 'runtime')]:
    name = names[key]
    assert name == 'nis-e2e-' + key + '-42a674cad1bc'
    details = inspect(kind, name)
    labels = details.get('Config', {}).get('Labels', {}) if kind == 'container' else details.get('Labels', {})
    assert labels.get('networkis.test') == 'disposable', (kind, name, labels)
    if key == 'app':
        assert details['Image'] == 'sha256:ad0de59d2493605616536846bf0e342daf066330da716230442b41921af5a4da'
    resources[key] = {'name': name, 'id': details.get('Id', details.get('Name')), 'labels': labels}
production = subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip()
record = {'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'status': 'INTERRUPTED_PROCESS_ABSENT', 'receipt': str(gate / 'receipt.json'),
          'last_browser_case_passed': 100, 'complete_browser_suite': False,
          'gate_processes': processes, 'resources': resources, 'production_image_before': production}
evidence = folder / 'interrupted-gate-recovery.json'
evidence.write_text(json.dumps(record, indent=2))
for key in ['app', 'db']:
    with (gate / (names[key] + '-interrupted.log')).open('w', encoding='utf-8') as log:
        subprocess.run([docker, 'logs', names[key]], stdout=log, stderr=subprocess.STDOUT, check=True)
    subprocess.run([docker, 'rm', '-f', names[key]], check=True)
for kind, key in [('network', 'network'), ('volume', 'runtime')]:
    subprocess.run([docker, kind, 'rm', names[key]], check=True)
after = subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip()
assert after == production
record.update(cleanup_completed=True, production_image_after=after)
evidence.write_text(json.dumps(record, indent=2))
print(json.dumps({'status': 'RECOVERED', 'production_unchanged': True, 'evidence': str(evidence)}))
