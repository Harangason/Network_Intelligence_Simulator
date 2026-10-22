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
identity = json.loads((OUT / 'waitress-candidate-input-identity.json').read_text())
frozen = json.loads((OUT / 'waitress-validation-source-freeze.json').read_text())
assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in frozen.items())
results = {}
for filename, minimum in [('cancellation-regressions.xml', 20), ('document-reference-regressions.xml', 100)]:
    cases = list(ET.parse(OUT / filename).getroot().iter('testcase'))
    assert len(cases) >= minimum
    assert all(not any(case.find(mark) is not None for mark in ('failure', 'error', 'skipped')) for case in cases)
    results[filename] = len(cases)
server_cases = list(ET.parse(OUT / 'waitress-after-regressions.xml').getroot().iter('testcase'))
assert len(server_cases) == 64 and all(not any(case.find(mark) is not None for mark in ('failure', 'error', 'skipped')) for case in server_cases)
server_scope = json.loads((OUT / 'server-only-source-change-proof.json').read_text())
assert server_scope['all_other_application_sources_identical_to_19ec']
ui = OUT.parent / 'document-network-error-repair'
transition = json.loads((ui / 'source-transition.json').read_text())
assert transition['all_other_application_sources_identical_to_ed7']
assert transition['current']['source_sha256'] == identity['source_sha256']
assert json.loads((ui / 'typecheck-result.json').read_text())['exit_code'] == 0
tap = (ui / 'frontend-final-18.tap').read_text()
assert '# pass 18' in tap and '# fail 0' in tap
browser = json.loads((ui / 'browser-final.json').read_text())['stats']
assert browser['expected'] == 4 and browser['unexpected'] == browser['skipped'] == browser['flaky'] == 0
probes = json.loads((OUT / 'native-four-fact-schemas-after-product/native-private-schema-checks.json').read_text())
assert len(probes['results']) == 14 and all(row['http_status'] == 200 for row in probes['results'])
assert probes['reasoner_file_sha256'] == hashlib.sha256((ROOT / 'backend/nis/agent/orchestration/local_reasoner.py').read_bytes()).hexdigest()
spec = importlib.util.spec_from_file_location('document_repair_release_identity', ROOT / 'scripts/release/release-and-deploy.py')
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
assert delivery.current_identity() == (identity['source_sha256'], identity['commit_id'], identity['verification_sha256'])
output = ROOT / ('backend/test-output/release-gates/joint-waitress-lifecycle-originals-' + identity['source_sha256'][:12])
assert not output.exists(), 'Inspect existing preparation instead of starting twice'
env = {**os.environ, 'NIS_E2E_LOCAL_AI_BASE_URL': 'http://host.docker.internal:11434/v1'}
env.pop('LOCAL_AI_CONTEXT_TOKENS', None)
env.pop('LOCAL_AI_TIMEOUT_SECONDS', None)
command = [sys.executable, str(ROOT / 'scripts/run-release-gate.py'), '--prepare', '--output', str(output)]
record = {'at_utc': datetime.now(timezone.utc).isoformat(), 'identity': identity, 'historical_affected_backend_cases': results, 'historical_server_cases': 64, 'server_case_source': transition['previous']['source_sha256'], 'earlier_452_case_source': '19ec12affb70db3c36a4fdd8d6eb9fd0ea4af0870db2e5e8db48161def47a893', 'frontend_reader_cases': 18, 'local_frontend_browser_contract_cases': 4, 'native_grammar_cases': 14, 'scope': 'Revision-bound affected checks, local frontend transport contracts and native grammar fixtures only. No fresh current-image complete backend, original model/simulation or full release PASS. Original acceptance and full exact-image release remain mandatory.', 'command': command, 'development_base': None, 'full_release_pass': False, 'productive_delivery': False}
(OUT / 'waitress-candidate-prepare-freeze.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf8')
print(json.dumps(record), flush=True)
subprocess.run(command, cwd=ROOT, env=env, check=True)
