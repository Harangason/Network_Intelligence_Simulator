"""Bind actual targeted results to the final inputs; never claims native/release PASS."""
import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('I:/PycharmProjects/My_first_Network_Simulator')
OUT = Path(__file__).resolve().parent
PEER = ROOT / 'docs/implementation-workloads/portfolio-parser-20261018'
summary = json.loads((PEER / 'validation-summary.json').read_text())
identity = json.loads((OUT / 'joint-release-input-identity.json').read_text())
for relative, row in json.loads((OUT / 'joint-owned-manifest.json').read_text()).items():
    assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == row['current'], ('PLAN_STALE', relative)
for check in summary['checks'].values():
    for evidence in check.get('evidence', []):
        assert hashlib.sha256(Path(evidence['path']).read_bytes()).hexdigest() == evidence['sha256'], evidence['path']


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


cases = {}
history = []
for path in (OUT / 'joint-backend-completion.xml', OUT / 'structure-mapping-repair/regressions.xml', PEER / 'repair-2-regressions.xml'):
    run = []
    for case in ET.parse(path).getroot().iter('testcase'):
        key = case.get('classname', '').removeprefix('backend.') + '::' + case.get('name', '')
        status = 'FAILED' if case.find('failure') is not None or case.find('error') is not None else 'SKIPPED' if case.find('skipped') is not None else 'PASSED'
        cases[key] = status
        run.append(status)
    history.append({'evidence': ref(path), 'tests': len(run), 'failures': run.count('FAILED'), 'skipped': run.count('SKIPPED')})
assert all(status == 'PASSED' for status in cases.values()), {key: status for key, status in cases.items() if status != 'PASSED'}
frontend = (OUT / 'joint-frontend-completion.log').read_text(encoding='utf-8-sig')
assert '# tests 191' in frontend and '# pass 191' in frontend and '# fail 0' in frontend
assert summary['checks']['frontend']['tests'] == 69 and summary['checks']['typecheck']['exit_code'] == 0
sources = [
    (Path('C:/Users/marti/PycharmProjects/Benchmark_Modelle/Fahrzeug komplett.txt'), '86865975c689643d9b07ea73e21d68fa6f4a3a8770402ffb537dba2d7ecdf4d7'),
    (Path('C:/Users/marti/PycharmProjects/Benchmark_Modelle/INDUSTRIEPORTFOLIO_100_KATEGORIENPAKET/D_INDUSTRIAL_ROBOTICS_054_063.md'), '8fc201a55e8b0afeb7b708ac70abd0c72a7b25eb17d90fceca71d80a291f3cef')]
for path, expected in sources:
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, ('Original changed', str(path))
result = {'at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'TARGETED_CHECKS_VERIFIED_WAITING_IMAGE_CAPACITY_APPROVAL',
    'identity': identity, 'unique_final_passing_backend_cases': len(cases), 'backend_run_history': history,
    'original_structure_failure_resolved': True, 'structure_resolution': ref(OUT / 'structure-mapping-repair/transition-proof.json'),
    'frontend_tests': 260, 'frontend_evidence': [ref(OUT / 'joint-frontend-completion.log'), *summary['checks']['frontend']['evidence']],
    'typecheck': summary['checks']['typecheck'], 'scope_parity': summary['checks']['backend_frontend_scope_parity'],
    'portfolio_source_coverage': summary['checks']['corpus_100_deterministic'],
    'unchanged_originals': [ref(path) for path, _ in sources],
    'native_final_original_models_and_simulations': 'PENDING_NEW_JOINT_CANDIDATE',
    'full_release_gate': 'PENDING', 'production_delivery': 'PENDING',
    'blocking_decision': 'Exact archived mixed-status image networkis:candidate-43d202d1dbde removal question pending. No removal has occurred.'}
(OUT / 'joint-validation.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': result['status'], 'backend_unique_cases': len(cases), 'frontend_tests': 260, 'typecheck_exit': 0, 'source_sha256': identity['source_sha256'], 'native_simulations': 'PENDING', 'release': 'PENDING'}), flush=True)
