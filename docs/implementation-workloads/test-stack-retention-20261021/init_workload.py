"""Record the bounded host-tool repair before changing its implementation."""
import hashlib
import json
from pathlib import Path
import shutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
FILES = ['scripts/release/run-release-gate.py', 'scripts/release/release-and-deploy.py',
         'scripts/tests/test_release_and_deploy.py', 'scripts/tests/test_release_lifecycle.py',
         'docs/WIZARD_RELEASE_GATE.md', 'AGENTS.md']


def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


revisions = {}
before = []
for relative in FILES:
    source = ROOT / relative
    revisions[relative] = ref(source)['sha256'] if source.exists() else None
    if source.exists():
        dest = OUT / 'before' / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        before.append(ref(dest))

data = {
    'goal_id': 'test-stack-retention-20261021', 'goal_type': 'RELEASE_TOOLING_REPAIR',
    'repository': str(ROOT), 'project_scope': 'Host release tooling and explicitly retired test Docker objects',
    'requested_change': 'Safely archive/remove obsolete test stacks and unused candidates; prevent repeated builds and retained stacks.',
    'constraints': ['Preserve production, all PASS/unknown images, recorded rollback, active latest prepared stack and unrelated projects.',
                    'No application-source changes, production deployment or candidate builds for this host-only repair.',
                    'Preserve original receipts; PREPARED retirement is not a FAIL or delivered-feature claim.'],
    'required_outcomes': ['safe_cleanup', 'reuse_and_bounded_stacks', 'production_and_rollback_preserved'],
    'validation_requirements': ['release_tool_regressions', 'cleanup_archive_and_identity_checks', 'production_health'],
    'kind': 'repair', 'modify_code': True, 'allow_repair': True,
    'repair': {
        'owner': 'PROJECT_PRODUCT', 'first_failing_layer': 'Host release/preparation orchestration',
        'root_cause': '--prepare builds before selecting an existing image and always retains its unique stack; PREPARED is excluded from image reuse; no cross-process gate lock or retained-stack bound.',
        'reproduction': 'Audited 30 nis-e2e containers and 27 PREPARED-only image identities; repeated prepare leaves every stack.',
        'evidence': [ref(OUT / 'inventory-before.json')], 'affected_files': FILES,
        'acceptance_criteria': ['Reuse non-development PREPARED images for the exact source and commit.',
                                'Serialize gates; reuse an identical healthy prepared stack, otherwise block a second retained stack before building.',
                                'Keep receipts and archived data; delete only fresh-checked exact retired objects.'],
        'targeted_tests': ['scripts/tests/test_release*.py'], 'weaken_assertions_to_pass': False,
    },
    'revision_before': revisions, 'unresolved_decisions': [], 'before': before,
    'files_inspected': FILES, 'files_changed': [], 'remaining_findings': [],
    'delivery': {'decision': 'NOT_APPLICABLE', 'reason': 'Only host-executed preparation/release orchestration and its verification/docs change. No application image inputs or production behavior change; no image build/redeployment is needed.'},
    'status': 'IMPLEMENTING',
}
(OUT / 'workload.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'workload': str(OUT / 'workload.json'), 'files': len(FILES)}))
