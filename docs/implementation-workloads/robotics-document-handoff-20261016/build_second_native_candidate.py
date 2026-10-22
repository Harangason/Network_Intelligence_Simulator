"""Build a real production candidate, then prepare its owned native Wizard."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
work = json.loads((OUT / 'workload.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == digest for p, digest in work['revision_after'].items())
root = ET.parse(OUT / 'targeted-backend.xml').getroot()
suites = [root] if root.tag == 'testsuite' else list(root.iter('testsuite'))
assert sum(int(suite.get('tests', 0)) for suite in suites) >= 240
assert not any(int(suite.get('failures', 0)) or int(suite.get('errors', 0)) for suite in suites)
assert '# pass 114' in (OUT / 'semantic-frontend-tests.log').read_text(encoding='utf-8')
assert not (OUT / 'semantic-typecheck.log').read_text(encoding='utf-8').strip()
manifest = json.loads((OUT / 'source-final-before-gate.json').read_text(encoding='utf-8'))
directory = ROOT / 'backend/test-output/release-gates/robotics-semantic-native-candidate-20261016'
assert not directory.exists(), 'Never overwrite an earlier candidate attempt'
with (OUT / 'semantic-candidate-build.log').open('w', encoding='utf-8') as log:
    subprocess.run([sys.executable, 'scripts/run-release-gate.py', '--prepare', '--output', str(directory)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
paths = list(directory.glob('*/receipt.json'))
assert len(paths) == 1
receipt = json.loads(paths[0].read_text(encoding='utf-8'))
assert receipt['status'] == 'PREPARED' and receipt.get('development_only', False) is False
assert receipt['initial_source_sha256'] == manifest['source_sha256']
assert any(check['name'] == 'production-build' and check['exit_code'] == 0 for check in receipt['checks'])
with (OUT / 'native-attempt-2/native-runtime-prepare.log').open('w', encoding='utf-8') as log:
    subprocess.run([sys.executable, str(OUT / 'native-attempt-2/prepare_native_acceptance.py'), '--candidate-receipt', str(paths[0])], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
runtime = json.loads((OUT / 'native-attempt-2/native-runtime-preparation.json').read_text(encoding='utf-8'))
assert runtime['source_sha256'] == manifest['source_sha256'] and runtime['release_pass'] is False
work['verification_phase'] = 'SECOND_NATIVE_CANDIDATE_READY'
work['semantic_candidate'] = {'receipt': str(paths[0]), 'image_id': receipt['image_id'], 'source_sha256': receipt['initial_source_sha256'], 'release_pass': False}
(OUT / 'workload.json').write_text(json.dumps(work, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key: runtime[key] for key in ['status', 'base_url', 'image_id', 'source_sha256']}), flush=True)
