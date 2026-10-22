"""Relocate two recoverable archives without changing their legacy paths/data."""
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
OUT = Path(__file__).resolve().parent
ALLOWED_SOURCE = (ROOT / 'work/archived-candidates').resolve()
ALLOWED_TARGET = Path('F:/CodexOrdner/visualizations/2026/10/09/01a11f88-d6c9-7b63-bec3-26450a86e52c').resolve()
source = ALLOWED_SOURCE / 'reference-example-assumptions-20261017'
staged = ALLOWED_SOURCE / 'reference-example-assumptions-20261017.relocation-source-20261018'
target = ALLOWED_TARGET / 'nis-recoverable-archives-20261018/reference-example-assumptions-20261017'
assert source.resolve().is_relative_to(ALLOWED_SOURCE)
assert staged.resolve().is_relative_to(ALLOWED_SOURCE)
assert target.resolve().is_relative_to(ALLOWED_TARGET)
assert not source.is_symlink() and not (hasattr(source, 'is_junction') and source.is_junction())
assert not staged.exists() and not target.exists()
expected = {}
for tag in ['43d202d1dbde', '66a892b0b219']:
    audit_path = ROOT / ('docs/implementation-workloads/reference-example-assumptions-20261017/archive-review-' + tag + '/archive-audit.json')
    audit = json.loads(audit_path.read_text())
    path = Path(audit['archive']['path'])
    assert path.parent.resolve() == source.resolve()
    expected[path.name] = {'sha256': audit['archive']['sha256'], 'image_id': audit['image'], 'verified_blobs': audit['verified_blobs']}
assert {p.name for p in source.iterdir()} == set(expected), 'Only the two known archives may be relocated.'
assert shutil.disk_usage(ALLOWED_TARGET).free > 20 * 1024**3 + sum(p.stat().st_size for p in source.iterdir())

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

target.mkdir(parents=True)
for name, evidence in expected.items():
    original, copy = source / name, target / name
    assert sha(original) == evidence['sha256']
    shutil.copy2(original, copy)
    assert sha(copy) == evidence['sha256'] and copy.stat().st_size == original.stat().st_size
    verified = set()
    with tarfile.open(copy) as tar:
        def verify(desc):
            digest = desc['digest']
            assert digest.startswith('sha256:')
            if digest in verified:
                return
            member = tar.getmember('blobs/sha256/' + digest.split(':')[1])
            assert member.isfile() and member.size == desc['size']
            with tar.extractfile(member) as stream:
                assert 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest() == digest
            verified.add(digest)
            if desc.get('mediaType', '').endswith(('index.v1+json', 'manifest.v1+json', 'manifest.v2+json', 'manifest.list.v2+json')):
                data = json.load(tar.extractfile(member))
                for child in data.get('manifests', []):
                    verify(child)
                if 'config' in data:
                    verify(data['config'])
                for child in data.get('layers', []):
                    verify(child)
        index = json.load(tar.extractfile('index.json'))
        verify(next(desc for desc in index['manifests'] if desc['digest'] == evidence['image_id']))
    assert verified == set(evidence['verified_blobs'])
    evidence.update(bytes=copy.stat().st_size, fresh_verified_blobs=len(verified), actual_path=str(copy))
record = {'at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'COPIES_AND_ALL_BLOBS_VERIFIED_ORIGINALS_STILL_PRESENT',
          'legacy_directory': str(source), 'actual_directory': str(target), 'archives': expected,
          'scope': 'Reversible archive relocation only; no Docker image/container/database operation and no application source change.'}
audit_path = OUT / 'archive-relocation.json'
audit_path.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
# Validate resolved endpoints before the one bounded, reversible directory move.
assert source.resolve() == ALLOWED_SOURCE / source.name
assert staged.resolve() == ALLOWED_SOURCE / staged.name
os.rename(source, staged)
try:
    powershell = str(Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe')
    subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-File', str(OUT / 'create_archive_junction.ps1'), '-Source', str(source), '-Target', str(target)], check=True)
except Exception:
    if not source.exists():
        os.rename(staged, source)
    raise
assert source.resolve() == target.resolve()
for name, evidence in expected.items():
    assert sha(source / name) == evidence['sha256'], 'Legacy recovery path must read exactly the verified relocated bytes.'
record['status'] = 'LEGACY_PATHS_VERIFIED_JUNCTION_CREATED_LOCAL_DUPLICATES_PRESENT'
audit_path.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
for name, evidence in expected.items():
    duplicate = staged / name
    assert duplicate.resolve().is_relative_to(staged.resolve()) and staged.resolve().is_relative_to(ALLOWED_SOURCE)
    assert sha(duplicate) == evidence['sha256'] and (source / name).stat().st_size == evidence['bytes']
    duplicate.unlink()  # Remove only the byte-identical duplicate after recovery paths have been verified.
staged.rmdir()  # Empty bounded directory; never recursive deletion.
record.update(status='COMPLETE_LEGACY_RECOVERY_PATHS_AND_IMMUTABLE_ARCHIVES_PRESERVED',
              source_free_bytes=shutil.disk_usage(ROOT).free, target_free_bytes=shutil.disk_usage(target).free)
audit_path.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': record['status'], 'archives': len(expected), 'source_free_bytes': record['source_free_bytes']}), flush=True)
