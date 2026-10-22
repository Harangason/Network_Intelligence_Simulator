"""Record the release owner's verified copy; never edit application source."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
digest = lambda data: hashlib.sha256(data).hexdigest()
manifest = json.loads((OUT / 'staged-manifest.json').read_text(encoding='utf-8'))
report = {'status': 'APPLIED_PENDING_INTEGRATED_VERIFICATION', 'at_utc': datetime.now(timezone.utc).isoformat(),
          'owner': 'NIS starten', 'files': {}}
before_refs, after_refs = [], []
def evidence(path):
    return {'path': str(path.resolve()), 'sha256': digest(path.read_bytes())}
for relative, item in manifest.items():
    after = (ROOT / relative).read_bytes()
    assert digest(after) == item['staged'], relative + ': copy differs from reviewed staging'
    path = OUT / 'after' / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(after)
    after_refs.append(evidence(path))
    if item['before'] is not None:
        before = OUT / 'before' / relative
        assert digest(before.read_bytes()) == item['before']
        before_refs.append(evidence(before))
    report['files'][relative] = {'before': item['before'], 'after': digest(after)}
before_refs.append(evidence(OUT / 'staged-manifest.json'))
(OUT / 'canonical-apply-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
workload_file = OUT / 'workload.json'
work = json.loads(workload_file.read_text(encoding='utf-8'))
work.update(status='APPLIED_PENDING_VERIFICATION', completion_status='IMPLEMENTATION_NOT_YET_RELEASED',
    files_changed=list(manifest), before=before_refs, after=after_refs, diff=[evidence(OUT / 'owned-staged.diff')],
    revision_after={key: value['after'] for key, value in report['files'].items()},
    remaining_findings=['Integrated canonical tests and release gate pending',
        'Native reference planning and actual saved model/simulation for both complete original files pending',
        'Production currently still has the prior fd2 image; new feature delivery pending'])
workload_file.write_text(json.dumps(work, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status':report['status'], 'exact_reviewed_files':len(manifest), 'model_writes':False}))
