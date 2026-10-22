"""Relocate one byte-identical recovery archive, keeping its legacy path."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[5]
ALLOWED_SOURCE = (ROOT / 'work/archived-candidates').resolve()
ALLOWED_TARGET = Path('F:/CodexOrdner/visualizations/2026/10/09/01a11f88-d6c9-7b63-bec3-26450a86e52c').resolve()
name = 'document-clarification-repair-20261016'
source = ALLOWED_SOURCE / name
staged = ALLOWED_SOURCE / (name + '.verified-relocation-20261018')
target = ALLOWED_TARGET / 'nis-recoverable-archives-20261018' / name
assert source.resolve().is_relative_to(ALLOWED_SOURCE) and staged.resolve().is_relative_to(ALLOWED_SOURCE)
assert target.resolve().is_relative_to(ALLOWED_TARGET)
assert not source.is_junction() and not source.is_symlink() and not staged.exists() and not target.exists()
audit_path = ROOT / 'docs/implementation-workloads/document-clarification-repair-20261016/archive-audit.json'
audit = json.loads(audit_path.read_text())
assert audit['status'] == 'ARCHIVED_VERIFIED'
assert all(audit[key] for key in ('immutable_index_verified', 'immutable_config_verified', 'all_layers_verified'))
assert len(audit['verified_blobs']) == 23
original = Path(audit['archive']['path'])
assert original.parent.resolve() == source.resolve()
assert {p.name for p in source.iterdir()} == {original.name}
assert original.stat().st_size == audit['archive_bytes'] == 2075242496
assert shutil.disk_usage(target.parent).free > audit['archive_bytes'] + 20 * 1024**3

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

before_free = shutil.disk_usage(ROOT).free
assert sha(original) == audit['archive']['sha256']
target.mkdir()
copy = target / original.name
shutil.copy2(original, copy)
assert sha(copy) == audit['archive']['sha256'] and copy.stat().st_size == audit['archive_bytes']
record = {'at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'AUDITED_ARCHIVE_FULL_HASH_AND_COPY_VERIFIED',
          'legacy_directory': str(source), 'actual_directory': str(target),
          'archive_sha256': audit['archive']['sha256'], 'bytes': audit['archive_bytes'],
          'immutable_image': audit['image'], 'verified_blobs': len(audit['verified_blobs']),
          'component_verification': 'Existing full OCI index/config/layer audit remains bound by freshly matching whole-archive SHA256, before and after copy.',
          'original_audit': {'path': str(audit_path), 'sha256': sha(audit_path)},
          'source_free_before': before_free, 'docker_operations': False,
          'production_changed': False, 'application_source_changed': False}
report = OUT / 'archive-relocation-e4af.json'
report.write_text(json.dumps(record, indent=2)+'\n')
# Verify both absolute move endpoints are inside the exact authorized workspace.
assert source.resolve() == ALLOWED_SOURCE / name and staged.resolve() == ALLOWED_SOURCE / staged.name
os.rename(source, staged)
try:
    helper = OUT.parent / 'normative-boundary-repair/create_archive_junction.ps1'
    subprocess.run([r'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe', '-NoProfile', '-NonInteractive',
                    '-File', str(helper), '-Source', str(source), '-Target', str(target)], check=True)
except Exception:
    if not source.exists(): os.rename(staged, source)
    raise
assert source.resolve() == target.resolve()
assert sha(source / original.name) == audit['archive']['sha256']
duplicate = staged / original.name
assert duplicate.resolve().is_relative_to(staged.resolve()) and staged.resolve().is_relative_to(ALLOWED_SOURCE)
assert sha(duplicate) == audit['archive']['sha256'] and copy.is_file()
duplicate.unlink()  # Only the verified duplicate; the audited recovery copy remains.
staged.rmdir()  # Empty bounded directory, never recursive removal.
record.update(status='COMPLETE_IDENTICAL_RECOVERY_ARCHIVE_AND_LEGACY_PATH_PRESERVED',
              source_free_after=shutil.disk_usage(ROOT).free)
report.write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record), flush=True)
