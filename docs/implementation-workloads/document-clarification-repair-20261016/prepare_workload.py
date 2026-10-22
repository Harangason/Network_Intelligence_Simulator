"""Refresh planned-file evidence after the completed neighboring delivery."""
from pathlib import Path
import hashlib
import json
import shutil

WORK = Path(__file__).parent
ROOT = WORK.parents[2]
file = WORK / 'workload.json'
work = json.loads(file.read_text(encoding='utf-8-sig'))
receipt = json.loads((ROOT / 'backend/test-output/release-gates/delivery-c74dcdfd5870/a1c086d28f4b/receipt.json').read_text(encoding='utf-8'))
production = json.loads((WORK.parent / 'large-document-intake-20261016/production-verification.json').read_text(encoding='utf-8'))
assert receipt['status'] == 'PASS' and production['status'] == 'PASSED'
assert production['image_id'] == receipt['image_id']
planned = sorted(path.relative_to(WORK / 'staged').as_posix() for path in (WORK / 'staged').rglob('*') if path.is_file() and path.suffix in {'.py', '.ts', '.tsx', '.mjs'})
work['revision_before'] = {}
work['before'] = []
for relative in planned:
    source = ROOT / relative
    sha = hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None
    work['revision_before'][relative] = sha
    if source.is_file():
        backup = WORK / 'before' / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, backup)
        work['before'].append({'path': str(backup.resolve()), 'sha256': sha})
work['repair']['affected_files'] = planned
work['repair']['acceptance_criteria'] = [
    'Actions and structural headings never add hardware; every normative list item remains source-bound across windows.',
    'Controller aliases, communication payload descriptions and ordinary connection prose never become false transport names; real unknown ports remain unresolved.',
    'Native reviewed INSTANCE facts and explicit per-member answers enter the existing wizard inventory and normal confirmed graph, preserving original source, minimum provenance and remaining gaps.',
    'No invented quantities, technical defaults, direct model edits or bypassed source/review/preflight gates.',
    'Full original-file native workflow and actual functional simulation must be evidenced before claiming completion.',
]
work['repair']['targeted_tests'] = ['backend/tests/test_qwen_document_intake.py', 'frontend/src/features/agent/lib/engineering-specification.test.mjs', 'frontend/e2e/document-intake.spec.ts', 'frontend TypeScript']
work['unresolved_decisions'] = []
work['source_handoff'] = {'preceding_receipt': str((ROOT / 'backend/test-output/release-gates/delivery-c74dcdfd5870/a1c086d28f4b/receipt.json').resolve()),
                          'preceding_image': receipt['image_id'], 'peer_completed': True, 'production_verified': True}
work['user_clarification'] = {'minimum_per_named_sensor_actuator_type': 1, 'is_complete_inventory': False,
    'functional_examples_to_review': ['PDC battery temperature', 'PDC battery voltage', 'PDC battery current'],
    'source': 'User reply call_b0416df30648407d8913498ec7d678cf; preserve as user amendment through NIS, no manual model writes'}
work['status'] = 'IMPLEMENTING'
work['completion_status'] = 'IMPLEMENTING'
file.write_text(json.dumps(work, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'planned_files': planned, 'preceding_delivery_verified': True}))
