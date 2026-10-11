"""Record interrupted own gate and remove only its labelled disposable stack."""
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
path = root / 'backend/test-output/release-gates/delivery-cea704cc4878/db6b43fecc86/receipt.json'
receipt = json.loads(path.read_text(encoding='utf-8'))
assert receipt['status'] == 'RUNNING' and receipt['gate_pid'] == 10456
receipt.update(status='FAIL', abort_reason='Task agent stopped its own process tree before changing inputs: four RFC landing-page/HTML aliases require deduplication. This is not a full PASS or a production deployment.')
path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
docker = r'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
for kind in ('app', 'db', 'network', 'runtime'):
    name = receipt['containers'][kind]
    assert name == 'nis-e2e-' + kind + '-db6b43fecc86'
    category = 'container' if kind in ('app', 'db') else 'network' if kind == 'network' else 'volume'
    result = subprocess.run([docker, category, 'inspect', name], capture_output=True, text=True)
    if result.returncode:
        continue
    info = json.loads(result.stdout)[0]
    labels = info.get('Config', {}).get('Labels', {}) if category == 'container' else info.get('Labels', {})
    assert labels.get('networkis.test') == 'disposable'
    command = ['rm', '-f', name] if category == 'container' else [category, 'rm', name]
    subprocess.run([docker, *command], check=True, capture_output=True)
print(json.dumps({'interrupted_gate': str(path), 'historical_images_removed': 0}))
