"""Freeze verified bundled repairs and invoke the one canonical preparation."""
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from unittest.mock import patch

ROOT = Path.cwd()
P = Path(__file__).resolve().parent

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def write(name, value):
    (P / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--launcher-repair-dir', type=Path)
args = parser.parse_args()
if args.launcher_repair_dir:
    baseline = P
    P = args.launcher_repair_dir.resolve(strict=True)
    assert P == baseline / 'launcher-repair'
    assert not (P / 'candidate-prepare-freeze.json').exists(), 'Reconcile existing preparation; never duplicate.'
    expected = read(P / 'current-identity.json')
    frozen = {**read(baseline / 'final-validation-identity.json')['affected_files'], **expected['affected_files']}
    assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in frozen.items())
    for name, count in (('final-green.xml', 53), ('powershell-final.xml', 3)):
        suite = ET.parse(P / name).getroot()
        assert len(list(suite.iter('testcase'))) == count
        assert not any(list(suite.iter(tag)) for tag in ('failure', 'error', 'skipped'))
    terminal = read(baseline / 'terminal-14388/cancellation.json')
    assert terminal['client_exit_code'] == 1 and terminal['server_draft_status'] == 'REFERENCE_CANCELED'
    retirement = baseline.parent / 'retire-04ad698f1b23-stack/retirement.json'
    assert read(retirement)['status'] == 'EXACT_OBSOLETE_STACK_RETIRED'
    assert read(retirement)['no_image_removed']
    spec = importlib.util.spec_from_file_location('nis_launcher_delivery', ROOT / 'scripts/release/release-and-deploy.py')
    delivery = importlib.util.module_from_spec(spec); spec.loader.exec_module(delivery)
    source, commit, verification = delivery.current_identity()
    identity = {'source_sha256': source, 'commit_id': commit, 'verification_sha256': verification}
    assert all(identity[key] == expected[key] for key in identity)
    # Use the canonical manifest with only the old launcher restored in memory.
    # This proves the remaining application source still equals the tested69 image.
    info = delivery.load_module('nis_launcher_scope_build', ROOT / 'scripts/write-build-info.py')
    original_read = Path.read_bytes
    launcher = ROOT / 'scripts/dev/launch-networkis.py'
    before = (P / 'before-launch-networkis.py').read_bytes()
    with patch.object(Path, 'read_bytes', lambda path: before if path == launcher else original_read(path)):
        prior = info.build_manifest()
    assert prior['source_sha256'] == read(baseline / 'prepared-current-identity.json')['source_sha256']
    write('source-scope-proof.json', {'only_application_source_changed': 'scripts/dev/launch-networkis.py',
        'canonical_before': prior, 'canonical_after': identity, 'frozen_affected_files': frozen,
        'native_reasoner_preview_models_provider_budgets_validators_unchanged': True})
    output = ROOT / ('backend/test-output/release-gates/joint-launcher-cache-originals-' + source[:12])
    assert not output.exists(), 'Reconcile/reuse the existing normal candidate.'
    command = [sys.executable, str(ROOT / 'scripts/run-release-gate.py'), '--prepare', '--output', str(output)]
    freeze = {**identity, 'at_utc': datetime.now(timezone.utc).isoformat(), 'command': command,
        'output': str(output), 'frozen_affected_files': frozen, 'source_scope': ref(P / 'source-scope-proof.json'),
        'startup53': ref(P / 'final-green.xml'), 'powershell3': ref(P / 'powershell-final.xml'),
        'previous_regressions': ref(baseline / 'regression-aggregate.json'),
        'native_cache': ref(baseline / 'native-cache/reviewed-result.json'),
        'browser_raw35': ref(baseline / 'browser-raw35/result.json'), 'retirement': ref(retirement),
        'full_release_pass': False, 'productive_delivery': False}
    write('candidate-prepare-freeze.json', freeze)
    env = {**os.environ, 'NIS_E2E_LOCAL_AI_BASE_URL': 'http://host.docker.internal:11434/v1'}
    for key in ('LOCAL_AI_CONTEXT_TOKENS', 'LOCAL_AI_TIMEOUT_SECONDS'):
        env.pop(key, None)
    print(json.dumps(freeze), flush=True)
    with (P / 'candidate-prepare.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    write('candidate-prepare-result.json', {**freeze, 'exit_code': result.returncode,
        'finished_at_utc': datetime.now(timezone.utc).isoformat()})
    assert result.returncode == 0, 'Inspect actual failure; preserve canonical gates.'
    print(json.dumps({'status': 'PREPARED_ONLY', 'output': str(output)}), flush=True)
    raise SystemExit(0)

assert not (P / 'candidate-prepare-freeze.json').exists(), 'Reconcile the existing preparation; never duplicate.'
expected = read(P / 'final-validation-identity.json')
for name, sha in expected['affected_files'].items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, 'Validation inputs changed: ' + name
runs = []
for name in ('green.xml', 'exact-wire-regressions.xml', 'reference-regressions-complete.xml'):
    path = P / name
    suite = ET.parse(path).getroot()
    cases = list(suite.iter('testcase'))
    assert cases and not list(suite.iter('failure')) and not list(suite.iter('error')) and not list(suite.iter('skipped')), name
    runs.append({'xml': ref(path), 'passed_cases': len(cases)})
assert read(P / 'native-cache/reviewed-result.json')['status'] == 'PASSED'
retirement = P.parent / 'retire-99b17a68b19b-stack/retirement.json'
assert read(retirement)['status'] == 'EXACT_OBSOLETE_STACK_RETIRED' and read(retirement)['no_image_removed']
for name, count in (('preview-regressions-final.txt', 132), ('frontend-adjacent.txt', 40)):
    raw = (P / name).read_text(encoding='utf-8-sig')
    assert f'# pass {count}' in raw and '# fail 0' in raw
assert read(P / 'typecheck-final-result.json')['exit_code'] == 0
work = read(P / 'workload.json')
for row in work['after']:
    snapshot = Path(row['path'])
    current = ROOT / snapshot.relative_to(P / 'after')
    # Exact-wire whitespace test additions followed the first full test import;
    # their own completed isolated retest is required above.
    snapshot.write_bytes(current.read_bytes())
    row['sha256'] = ref(snapshot)['sha256']
write('workload.json', work)
write('regression-aggregate.json', {'runs': runs, 'frontend_parser': 132, 'frontend_adjacent': 40,
    'typecheck_exit_code': 0, 'initial_three_RED': ref(P / 'red.xml'), 'initial_preview_two_RED': ref(P / 'preview-red.txt'),
    'collection_error_preserved': ref(P / 'reference-regressions.xml'),
    'scope': 'Current scoped tests; no original, full release or campaign PASS.'})
spec = importlib.util.spec_from_file_location('nis_final_context_delivery', ROOT / 'scripts/release/release-and-deploy.py')
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
source, commit, verification = delivery.current_identity()
identity = {'source_sha256': source, 'commit_id': commit, 'verification_sha256': verification}
assert all(identity[key] == expected[key] for key in identity), 'Complete source/verification identity changed during validation.'
write('current-input-identity.json', identity)
output = ROOT / ('backend/test-output/release-gates/joint-cache-progress-originals-' + source[:12])
assert not output.exists(), 'Inspect/reuse the existing canonical image/output, never duplicate preparation.'
command = [sys.executable, str(ROOT / 'scripts/run-release-gate.py'), '--prepare', '--output', str(output)]
freeze = {**identity, 'at_utc': datetime.now(timezone.utc).isoformat(), 'command': command, 'output': str(output),
    'regressions': ref(P / 'regression-aggregate.json'), 'native_cache': ref(P / 'native-cache/reviewed-result.json'),
    'source_scope': ref(P / 'source-scope-proof.json'), 'retirement': ref(retirement),
    'full_release_pass': False, 'productive_delivery': False}
write('candidate-prepare-freeze.json', freeze)
env = {**os.environ, 'NIS_E2E_LOCAL_AI_BASE_URL': 'http://host.docker.internal:11434/v1'}
for key in ('LOCAL_AI_CONTEXT_TOKENS', 'LOCAL_AI_TIMEOUT_SECONDS'):
    env.pop(key, None)
print(json.dumps(freeze), flush=True)
with (P / 'candidate-prepare.log').open('w', encoding='utf-8') as log:
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
write('candidate-prepare-result.json', {**freeze, 'exit_code': result.returncode,
    'finished_at_utc': datetime.now(timezone.utc).isoformat()})
assert result.returncode == 0, 'Inspect actual failure; preserve canonical gate and storage checks.'
print(json.dumps({'status': 'PREPARED_ONLY', 'output': str(output)}), flush=True)
