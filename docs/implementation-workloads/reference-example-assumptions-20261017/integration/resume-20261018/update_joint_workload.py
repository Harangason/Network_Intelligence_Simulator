"""Update the parent checkpoint truthfully; no completion or deployment claim."""
import hashlib
import json
from pathlib import Path

ROOT = Path('I:/PycharmProjects/My_first_Network_Simulator')
OUT = Path(__file__).resolve().parent
path = OUT.parent / 'workload.json'
work = json.loads(path.read_text())
manifest = json.loads((OUT / 'joint-owned-manifest.json').read_text())


def ref(value):
    target = Path(value)
    return {'path': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}


proof = ref(OUT / 'joint-validation.json')
work.update(status='WAITING_FOR_DECISION', owned_files=sorted(manifest), files_changed=sorted(manifest),
    revision_before={name: row['before_sha256'] for name, row in manifest.items()},
    before=[ref(OUT / 'joint-before' / name) for name in manifest],
    after=[ref(OUT / 'joint-after' / name) for name in manifest], diff=[ref(OUT / 'joint-owned.diff')],
    unresolved_decisions=['Exact archived mixed-status image networkis:candidate-43d202d1dbde removal question is pending; do not assume authorization.'],
    current_validation=proof, resume=str(OUT / 'RESUME.md'),
    completion_status='Both chats local code and targeted regressions verified; new shared candidate, two native original simulations, full gate and production remain pending.')
if 'portfolio_source_coverage' not in work['required_outcomes']:
    work['required_outcomes'].append('portfolio_source_coverage')
work.setdefault('outcomes', {})['portfolio_source_coverage'] = {'status': 'PASSED', 'scope': 'Deterministic original source coverage only, no native portfolio simulation claim', 'evidence': [proof]}
for name in ('targeted_frontend', 'isolated_backend', 'typecheck'):
    work.setdefault('validations', {})[name] = {'status': 'PASSED', 'scope': 'Targeted checks bound to final local input identities; full gate remains pending', 'evidence': [proof]}
for name in ('real_native_two_documents', 'full_release_gate', 'production_identity_health_function'):
    work.setdefault('validations', {})[name] = {'status': 'PENDING', 'evidence': []}
work['delivery'].update(decision='YES', authorization='Standing AGENTS.md plus direct user instruction on 2026-10-18: publish after both chats finish', status='PENDING')
work['joint_delivery'] = json.loads((OUT / 'joint-delivery.json').read_text())
work['joint_delivery']['current_source_sha256'] = json.loads((OUT / 'joint-release-input-identity.json').read_text())['source_sha256']
work['joint_delivery']['new_candidate_status'] = 'PENDING_EXACT_STORAGE_AUTHORIZATION'
path.write_text(json.dumps(work, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': work['status'], 'owned_files': len(manifest), 'current_validation': proof, 'production': 'UNCHANGED', 'full_pass': False}), flush=True)
