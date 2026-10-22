"""Prepare one normal exact-source candidate after affected reference tests pass.

Preparation is not a complete release gate or production delivery.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[5]
identity = json.loads((OUT / 'candidate-input-identity.json').read_text(encoding='utf-8'))
owned = json.loads((OUT / 'candidate-owned-manifest.json').read_text(encoding='utf-8'))
frozen = json.loads((OUT / 'validation-source-freeze.json').read_text(encoding='utf8'))
assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in frozen.items())
for name, row in owned.items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == row['current'], name
cases = list(ET.parse(OUT / 'tagged-targeted-reference-regressions.xml').getroot().iter('testcase'))
assert len(cases) == 94
assert all(case.find('failure') is None and case.find('error') is None
           and case.find('skipped') is None for case in cases)
scope = json.loads((OUT / 'source-change-scope-proof.json').read_text(encoding='utf8'))
assert scope['unchanged_document_intake_methods_and_response_validation']
assert json.loads((OUT / 'final-schema-equality-proof.json').read_text(encoding='utf8'))['exact_schemas_rechecked']
probe_file = Path(scope['compiler_origin']['path'])
assert hashlib.sha256(probe_file.read_bytes()).hexdigest() == scope['compiler_origin']['sha256']
probes = json.loads(probe_file.read_text(encoding='utf8'))
assert len(probes['results']) == 14 and all(row['http_status'] == 200 for row in probes['results'])
# Recheck the complete product and verification identity, beyond the owned-file subset.
import importlib.util

def load_identity_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

build = load_identity_module('inventory_candidate_build_identity', ROOT / 'scripts/write-build-info.py')
gate = load_identity_module('inventory_candidate_verification_identity', ROOT / 'scripts/run-release-gate.py')
current_manifest = build.build_manifest()
assert current_manifest['source_sha256'] == identity['source_sha256']
assert current_manifest['commit_id'] == identity['commit_id']
assert gate.verification_manifest() == identity['verification_sha256']
assert shutil.disk_usage(ROOT).free >= 20 * 1024**3
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']
production = subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip()
assert production == 'sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'
count = len(set(subprocess.check_output(
    [docker, 'image', 'ls', 'networkis', '--no-trunc', '--format', '{{.ID}}'], text=True).split()))
assert count < 100
output = ROOT / ('backend/test-output/release-gates/joint-tagged-inventory-originals-' + identity['source_sha256'][:12])
assert not output.exists(), 'Inspect existing candidate preparation; never duplicate it.'
env = {**os.environ, 'NIS_E2E_LOCAL_AI_BASE_URL': 'http://host.docker.internal:11434/v1'}
env.pop('LOCAL_AI_CONTEXT_TOKENS', None)
env.pop('LOCAL_AI_TIMEOUT_SECONDS', None)
command = [sys.executable, str(ROOT / 'scripts/run-release-gate.py'), '--prepare', '--output', str(output)]
freeze = {'at_utc': datetime.now(timezone.utc).isoformat(), 'identity': identity,
    'validation_scope': '94 affected isolated reference cases passed on final frozen files; nine one-token native compiler probes and five completed grammar-only fixtures, including EXISTING and nonfirst SENSOR/ACTUATOR variants. This is not a full backend/frontend or release gate run. Original workflows and full release gate still pending.',
    'image_count_before': count, 'source_free_bytes': shutil.disk_usage(ROOT).free,
    'production_image_before': production, 'command': command, 'development_base': None,
    'context_timeout_test_override': False, 'full_release_pass': False, 'productive_delivery': False}
(OUT / 'candidate-prepare-freeze.json').write_text(json.dumps(freeze, indent=2) + '\n', encoding='utf-8')
print(json.dumps(freeze), flush=True)
subprocess.run(command, cwd=ROOT, env=env, check=True)
