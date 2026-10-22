"""Prepare one normal candidate after current affected checks; not a release PASS."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[5]
identity = json.loads((OUT / 'candidate-input-identity.json').read_text())
frozen = json.loads((OUT / 'validation-source-freeze.json').read_text())
assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in frozen.items())
results = {}
for filename, minimum in [('cancellation-regressions.xml', 20), ('document-reference-regressions.xml', 100)]:
    cases = list(ET.parse(OUT / filename).getroot().iter('testcase'))
    assert len(cases) >= minimum
    assert all(not any(case.find(mark) is not None for mark in ('failure', 'error', 'skipped')) for case in cases)
    results[filename] = len(cases)
assert json.loads((OUT / 'typecheck-result.json').read_text())['exit_code'] == 0
tap = (OUT / 'frontend-regressions.tap').read_text()
assert '# pass 15' in tap and '# fail 0' in tap
probes = json.loads((OUT / 'native-four-fact-schemas-after-product/native-private-schema-checks.json').read_text())
assert len(probes['results']) == 14 and all(row['http_status'] == 200 for row in probes['results'])
assert probes['reasoner_file_sha256'] == hashlib.sha256((ROOT / 'backend/nis/agent/orchestration/local_reasoner.py').read_bytes()).hexdigest()
spec = importlib.util.spec_from_file_location('document_repair_release_identity', ROOT / 'scripts/release/release-and-deploy.py')
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
assert delivery.current_identity() == (identity['source_sha256'], identity['commit_id'], identity['verification_sha256'])
output = ROOT / ('backend/test-output/release-gates/joint-document-lifecycle-originals-' + identity['source_sha256'][:12])
assert not output.exists(), 'Inspect existing preparation instead of starting twice'
env = {**os.environ, 'NIS_E2E_LOCAL_AI_BASE_URL': 'http://host.docker.internal:11434/v1'}
env.pop('LOCAL_AI_CONTEXT_TOKENS', None)
env.pop('LOCAL_AI_TIMEOUT_SECONDS', None)
command = [sys.executable, str(ROOT / 'scripts/run-release-gate.py'), '--prepare', '--output', str(output)]
record = {'at_utc': datetime.now(timezone.utc).isoformat(), 'identity': identity, 'affected_backend_cases': results, 'frontend_reader_cases': 15, 'native_grammar_cases': 14, 'scope': 'Affected checks and native grammar fixtures only. Original model/simulation and full exact-image release remain mandatory.', 'command': command, 'development_base': None, 'full_release_pass': False, 'productive_delivery': False}
(OUT / 'candidate-prepare-freeze.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf8')
print(json.dumps(record), flush=True)
subprocess.run(command, cwd=ROOT, env=env, check=True)
