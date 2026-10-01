"""Record current evidence without turning a partial audit into a release PASS."""
from pathlib import Path
import difflib
import hashlib
import json

root = Path(__file__).resolve().parents[1]
folder = root / 'docs/implementation-workloads/technology-full-parameter-audit-20261001'
path = folder / 'workload.json'
work = json.loads(path.read_text(encoding='utf-8'))
progress = json.loads((folder / 'progress.json').read_text(encoding='utf-8'))

def evidence(file):
    return {'path': str(file.resolve()), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}

before, after, diffs, changed = [], [], [], []
for relative in work['revision_before']:
    source = root / relative
    original = folder / 'before' / relative
    if not source.exists() or not original.exists() or source.read_bytes() == original.read_bytes():
        continue
    target = folder / 'after' / relative
    delta = folder / 'diff' / (relative + '.diff')
    target.parent.mkdir(parents=True, exist_ok=True)
    delta.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    delta.write_text(''.join(difflib.unified_diff(original.read_text(encoding='utf-8').splitlines(keepends=True),
                                                source.read_text(encoding='utf-8').splitlines(keepends=True),
                                                fromfile='before/' + relative, tofile='after/' + relative)), encoding='utf-8')
    changed.append(relative)
    before.append(evidence(original))
    after.append(evidence(target))
    diffs.append(evidence(delta))
tests = []
for review in folder.joinpath('individual').glob('*.json'):
    record = json.loads(review.read_text(encoding='utf-8'))
    tests.append({'technology': record['technology'], 'status': 'SOURCE_AND_LOCAL_RULES_REVIEWED',
                  'evidence': [evidence(review)], 'scope': record.get('scope'),
                  'runtime_capacity_verified': False, 'production_delivered': False})
work.update(completion_status='IMPLEMENTING', files_changed=changed, before=before, after=after, diff=diffs,
            tests=tests, remaining_findings=[
                f"{progress['total_technologies'] - progress['source_and_local_reviews']} individual technology reviews pending",
                'Consumer-wide consistency, full release gate and exact-image production delivery pending'])
work['validation'] = {name: {'status': 'IN_PROGRESS' if name != 'complete_release_gate' else 'NOT_RUN',
                            'evidence': [evidence(folder / 'progress.json')]} for name in work['validation_requirements']}
work['outcomes'] = {name: {'status': 'IN_PROGRESS', 'evidence': [evidence(folder / 'progress.json')]}
                    for name in work['required_outcomes']}
path.write_text(json.dumps(work, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': work['completion_status'], 'reviews': progress['source_and_local_reviews'],
                  'total': progress['total_technologies'], 'changed_files': len(changed), 'production': False}))
