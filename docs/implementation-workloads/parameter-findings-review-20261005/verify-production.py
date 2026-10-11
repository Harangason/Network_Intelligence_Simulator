"""Read-only deployed image and current-project verification."""
import hashlib
import json
from collections import Counter
from pathlib import Path
import subprocess
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PROJECT = '20261005103106027-d3a78a2c'
RECEIPT = Path((OUT / 'final-receipt.txt').read_text(encoding='utf-8').strip())
DOCKER = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'

def get(path):
    with urlopen(Request('http://127.0.0.1:13500' + path, headers={'X-Project-ID': PROJECT}), timeout=180) as response:
        return json.load(response)

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()

receipt = json.loads(RECEIPT.read_text(encoding='utf-8'))
assert receipt['status'] == 'PASS', 'Release receipt must be PASS'
running = subprocess.check_output([DOCKER, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip()
ready = get('/api/ready')
build = get('/api/build-info')
parameters = get('/api/engineering/workflow/parameters')
review = get('/api/engineering/workflow/parameters/review')
assert running == receipt['image_id'], 'Running image differs from tested image'
assert ready['status'] == 'ready'
assert build['source_sha256'] == receipt['release']['source_sha256']
assert review['source'] == 'CURRENT_CANONICAL_MODEL'
assert review['project_id'] == parameters['project_id']
assert review['edit_token'] == parameters['edit_token'], 'Project parameter snapshot changed while reading'
before = json.loads((OUT / 'parameters-before.json').read_text(encoding='utf-8-sig'))
batch = json.loads((OUT / 'parameters-after-batch-deployed.json').read_text(encoding='utf-8-sig'))
findings = review['findings']
summary = {
    'status': 'PASSED', 'receipt': str(RECEIPT), 'running_image': running,
    'source_sha256': build['source_sha256'], 'ready': ready,
    'project_id': review['project_id'], 'review_source': review['source'],
    'finding_count': len(findings), 'by_technology': dict(Counter(f.get('technology') for f in findings)),
    'by_code': dict(Counter(f.get('code') for f in findings)),
    'fields_by_technology': {tech: sorted({key for f in findings if f.get('technology') == tech for key in f.get('parameter_fields', [])}) for tech in {f.get('technology') for f in findings}},
    'parameters_before_sha256': digest(before['parameters']),
    'parameters_after_sha256': digest(parameters['parameters']),
    'parameters_unchanged': before['parameters'] == parameters['parameters'],
    'parameters_unchanged_since_batch_delivery': batch['parameters'] == parameters['parameters'],
    'parameter_storage': parameters.get('parameter_storage'),
}
(OUT / 'production-review.json').write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(OUT / 'parameters-after.json').write_text(json.dumps(parameters, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(OUT / 'production-verification.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
