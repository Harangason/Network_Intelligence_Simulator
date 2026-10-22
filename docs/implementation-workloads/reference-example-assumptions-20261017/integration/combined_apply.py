"""Prepare/apply only the verified joint staged delta; never reset foreign work."""
import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
PEER = OUT.parent / 'root'
WORKLOAD = OUT / 'workload.json'
MANIFEST = OUT / 'combined-manifest.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def ref(path):
    return {'path': str(path.resolve()), 'sha256': digest(path)}


parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
workload = json.loads(WORKLOAD.read_text(encoding='utf-8'))
if not args.apply:
    peer = json.loads((PEER / 'staged-manifest.json').read_text(encoding='utf-8'))
    entries = {}
    baseline = workload['revision_before']
    for staged in (OUT / 'staged').rglob('*'):
        if not staged.is_file() or '__pycache__' in staged.parts:
            continue
        relative = staged.relative_to(OUT / 'staged').as_posix()
        entries[relative] = {'staged_path': str(staged), 'before': baseline.get(relative),
                             'staged': digest(staged), 'owner': 'NIS starten'}
    for relative, entry in peer.items():
        staged = PEER / 'staged' / relative
        assert digest(staged) == entry['staged'], ('Peer snapshot changed', relative)
        entries[relative] = {**entry, 'staged_path': str(staged), 'owner': 'Locate evaluation section limit'}
    diff = []
    for relative, entry in entries.items():
        target = ROOT / relative
        assert digest(target) == entry['before'], ('PLAN_STALE', relative, digest(target), entry['before'])
        before = OUT / 'combined-before' / relative
        if target.exists():
            before.parent.mkdir(parents=True, exist_ok=True)
            before.write_bytes(target.read_bytes())
        staged = Path(entry['staged_path'])
        diff.extend(difflib.unified_diff(target.read_text(encoding='utf-8').splitlines(True) if target.exists() else [],
            staged.read_text(encoding='utf-8').splitlines(True), fromfile='before/' + relative, tofile='after/' + relative))
    (OUT / 'combined-staged.diff').write_text(''.join(diff), encoding='utf-8', newline='\n')
    save(MANIFEST, entries)
    workload.update(status='READY_FOR_CANONICAL_APPLY',
        revision_before={key: value['before'] for key, value in entries.items()},
        owned_files=list(entries), peer_ownership_manifest=ref(PEER / 'staged-manifest.json'),
        combined_manifest=ref(MANIFEST), files_changed=[], unresolved_decisions=[],
        implementation_plan='Apply the exact joint staged delta, then run real canonical tests/native source-to-simulation and full release; no model patching.',
        updated_at_utc=datetime.now(timezone.utc).isoformat())
    workload['repair'].update(
        reproduction='Actual product source-role path and actuator proposal observations, original-source counterprobes and recorded source/field handoff losses.',
        targeted_tests=['Reference DTO and source/profile/confirmed-field protections',
                        'Native draft revisions, human-only review and actual canonical proposal persistence',
                        'Frontend compiler, transport and complete typecheck',
                        'Two unchanged original sources with real local Qwen through saved simulation'],
        affected_files=list(entries))
    save(WORKLOAD, workload)
    print(json.dumps({'status': 'PREPARED', 'files': len(entries), 'manifest_sha256': digest(MANIFEST)}))
else:
    gate = json.loads((OUT / 'combined-before-apply-guard.json').read_text(encoding='utf-8-sig'))
    assert gate.get('allowed') is True and not gate.get('issues'), gate
    entries = json.loads(MANIFEST.read_text(encoding='utf-8'))
    assert workload['combined_manifest'] == ref(MANIFEST)
    for relative, entry in entries.items():
        assert digest(ROOT / relative) == entry['before'], ('PLAN_STALE', relative)
        assert digest(Path(entry['staged_path'])) == entry['staged'], ('STAGING_CHANGED', relative)
    for relative, entry in entries.items():
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(entry['staged_path']).read_bytes())
    after_refs = []
    for relative, entry in entries.items():
        target = ROOT / relative
        assert digest(target) == entry['staged']
        copy = OUT / 'combined-after' / relative
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes(target.read_bytes())
        after_refs.append(ref(copy))
    workload.update(status='IMPLEMENTING', files_changed=list(entries),
        before=[ref(OUT / 'combined-before' / relative) for relative, entry in entries.items() if entry['before'] is not None],
        after=after_refs, diff=[ref(OUT / 'combined-staged.diff')], canonical_applied_at_utc=datetime.now(timezone.utc).isoformat())
    save(WORKLOAD, workload)
    print(json.dumps({'status': 'APPLIED_EXACT_STAGED_DELTA', 'files': len(entries), 'model_writes': 0}))
