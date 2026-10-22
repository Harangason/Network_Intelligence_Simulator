"""Verify the coordinated second copy, keeping first-apply evidence immutable."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
STAGE = OUT / 'qualification-stage'
digest = lambda data: hashlib.sha256(data).hexdigest()
manifest = json.loads((STAGE / 'manifest.json').read_text(encoding='utf-8'))
def evidence(path):
    return {'path': str(path), 'sha256': digest(path.read_bytes())}
after_refs, before_refs = [], []
for relative, entry in manifest.items():
    raw = (ROOT / relative).read_bytes()
    assert digest(raw) == entry['staged'], 'Canonical differs from reviewed qualification staging: ' + relative
    target = STAGE / 'after' / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    after_refs.append(evidence(target))
    if entry['before'] is not None:
        before = STAGE / 'before' / relative
        assert digest(before.read_bytes()) == entry['before']
        before_refs.append(evidence(before))
before_refs.append(evidence(STAGE / 'manifest.json'))
record = {'status': 'APPLIED_PENDING_INTEGRATED_VERIFICATION', 'at_utc': datetime.now(timezone.utc).isoformat(),
          'files': manifest, 'canonical_copy_owner': 'NIS starten', 'root_model_writes': False}
(STAGE / 'canonical-apply-verification.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
work_file = STAGE / 'workload.json'
work = json.loads(work_file.read_text(encoding='utf-8'))
work.update(status='APPLIED_PENDING_INTEGRATED_VERIFICATION', files_changed=list(manifest),
    before=before_refs, after=after_refs, diff=[evidence(STAGE / 'staged.diff')],
    remaining_findings=['Canonical combined regressions and release candidate pending',
        'Both complete original file models and saved simulations pending', 'Exact image productive delivery pending'])
work_file.write_text(json.dumps(work, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
root_file = OUT / 'workload.json'
root_work = json.loads(root_file.read_text(encoding='utf-8'))
old_after = {relative: ref for relative in root_work['files_changed'] for ref in root_work['after']
             if ref['path'].replace('\\', '/').endswith('/' + relative)}
for relative, entry in manifest.items():
    if relative not in root_work['files_changed']:
        root_work['files_changed'].append(relative)
        root_work['revision_before'][relative] = entry['before']
    root_work['revision_after'][relative] = entry['staged']
    old_after[relative] = next(ref for ref in after_refs if ref['path'].replace('\\', '/').endswith('/' + relative))
root_work.update(status='APPLIED_PENDING_VERIFICATION', after=list(old_after.values()),
    completion_status='IMPLEMENTED_NOT_YET_NATIVE_VERIFIED_OR_DEPLOYED',
    remaining_findings=work['remaining_findings'])
root_work['before'].extend(before_refs)
root_work['diff'].append(evidence(STAGE / 'staged.diff'))
root_file.write_text(json.dumps(root_work, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status':record['status'], 'exact_reviewed_files':len(manifest), 'root_owned_files_total':len(root_work['files_changed'])}))
