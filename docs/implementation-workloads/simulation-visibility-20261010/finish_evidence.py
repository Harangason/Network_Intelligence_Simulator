import difflib, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
def ref(p):
    return {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}

work = json.loads((HERE / 'workload.json').read_text(encoding='utf-8'))
after, patch = [], []
for name in work['files_changed']:
    source, original = ROOT / name, HERE / 'before' / name
    dest = HERE / 'after' / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(source.read_bytes())
    after.append(ref(dest))
    patch.extend(difflib.unified_diff(original.read_text(encoding='utf-8').splitlines(True) if original.exists() else [],
        source.read_text(encoding='utf-8').splitlines(True), fromfile='before/' + name, tofile='after/' + name))
(HERE / 'changes.patch').write_text(''.join(patch), encoding='utf-8')
review = {
    'frontend_tests': {'status': 'PASSED', 'count': 10},
    'typecheck': {'status': 'PASSED', 'exit_code': 0},
    'browser': {'status': 'PASSED', 'count': 1, 'fixture_only': True,
        'scope': 'Actual frontend signal defaults, static filtering, search, last pages, event time delta across pages, keyboard selection, computed transparent fill, preserved activation SVG, widths 1383/954/390.'},
    'visual': 'Reviewed sequence-highlight.png: continuous activation bars/lifelines remain visible through hover; arrows and text legible; no route-wide label mask.',
    'react_review': 'Bounded page rendering; memoized Set membership for full selection; ALL avoids scanning dynamic point values; native labelled page select/buttons; keyboard selection retained; source API data unmodified.',
    'generated_config': 'Stopped owned isolated preview and restored only its automatic next-env/tsconfig additions; git diff is empty for both config files.',
    'limitations': ['Fixture browser check does not prove canonical generation or persisted simulation E2E.', 'No image deletion; historical retention exception remains pending.', 'Full release gate and production delivery still required.'],
}
(HERE / 'verification-summary.json').write_text(json.dumps(review, indent=2), encoding='utf-8')
tests = [ref(HERE / 'frontend-tests.log'), ref(HERE / 'verification-summary.json')]
browser = [ref(HERE / 'browser-reviewed.json')]
work.update(after=after, diff=[ref(HERE / 'changes.patch')], completion_status='WAITING_FOR_DECISION')
work['outcomes'] = {
    'all_signals_accessible': {'status': 'PASSED', 'evidence': tests + browser},
    'all_sequence_events_accessible': {'status': 'PASSED', 'evidence': tests + browser},
    'non_obscuring_highlight': {'status': 'PASSED', 'evidence': browser + [ref(HERE / 'verification-summary.json')]},
    'release_and_deploy': {'status': 'PENDING', 'evidence': []},
}
work['validations'] = {
    'targeted_frontend': {'status': 'PASSED', 'evidence': tests},
    'typecheck': {'status': 'PASSED', 'evidence': [ref(HERE / 'typecheck.log'), ref(HERE / 'verification-summary.json')]},
    'isolated_browser': {'status': 'PASSED', 'evidence': browser},
    'release_gate': {'status': 'PENDING', 'evidence': []},
    'production_verification': {'status': 'PENDING', 'evidence': []},
}
work['unresolved_decisions'] = [{'kind': 'EXACT_IMAGE_RETENTION_EXCEPTION',
    'authoritative_workload': str(HERE.parent / 'stranded-capacity-channels-20261010/workload.json'),
    'image': 'networkis:candidate-42a674cad1bc',
    'status': 'USER_ANSWER_PENDING', 'instruction': 'No deletion until explicit exception approval. Archive and current production image must be preserved.'}]
work['delivery']['status'] = 'NOT_DEPLOYED_STORAGE_EXCEPTION_PENDING'
(HERE / 'workload.json').write_text(json.dumps(work, indent=2), encoding='utf-8')
