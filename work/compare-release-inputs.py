"""Compare canonical and isolated NIS gate input files without modifying either tree."""
import hashlib
import json
from pathlib import Path

canonical = Path(r'I:\PycharmProjects\My_first_Network_Simulator')
candidate = Path(r'F:\CodexOrdner\worktrees\wizard-repair\My_first_Network_Simulator')
roots = ('backend/tests', 'frontend/e2e', 'tests/fixtures', 'scripts/tests')
files = ('frontend/playwright.config.ts', 'scripts/run-release-gate.py',
         'scripts/run-isolated-tests.py', 'scripts/verify-live-wizard.py',
         'scripts/deploy-verified-release.py', 'scripts/release-and-deploy.py',
         'scripts/release_storage.py', '.github/workflows/wizard-release-gate.yml')


def hashes(root):
    result = {}
    paths = [item for directory in roots for item in (root / directory).rglob('*')]
    paths.extend(root / item for item in files)
    for path in paths:
        if not path.is_file() or '__pycache__' in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        result[relative] = hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    return result


a, b = hashes(canonical), hashes(candidate)
print(json.dumps({
    'canonical_count': len(a), 'candidate_count': len(b),
    'missing_in_candidate': sorted(set(a) - set(b)),
    'candidate_only': sorted(set(b) - set(a)),
    'different': sorted(key for key in a.keys() & b.keys() if a[key] != b[key]),
}, indent=2))
