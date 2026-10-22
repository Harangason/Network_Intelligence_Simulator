"""Stage only the qualified-planning repair against the applied first revision."""
from pathlib import Path
from datetime import datetime, timezone
import difflib
import hashlib
import json

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
STAGE = OUT / 'qualification-stage'
targets = ['backend/nis/agent/orchestration/project_intake.py', 'backend/tests/test_reference_design.py',
           'backend/nis/communication/catalog.py', 'backend/tests/test_reference_parameter_roles.py']
marker = '# Reference design is a separate planning result, never a source interpretation.'
manifest = {}
diff = []
for relative in targets:
    original = (ROOT / relative).read_bytes() if (ROOT / relative).is_file() else None
    before = STAGE / 'before' / relative
    before.parent.mkdir(parents=True, exist_ok=True)
    if before.is_file():
        assert before.read_bytes() == original, 'Applied source changed during qualification staging: ' + relative
    elif original is not None:
        before.write_bytes(original)
    if relative.endswith('project_intake.py'):
        text = original.decode('utf-8')
        assert text.count(marker) == 1
        prefix = text[:text.index(marker)].rstrip('\r\n')
        newline = '\r\n' if '\r\n' in text else '\n'
        fragment = (OUT / 'reference-contract.fragment.py').read_text(encoding='utf-8').replace('\n', newline)
        after = prefix + fragment
        compile(after, relative, 'exec')
        candidate = after.encode('utf-8')
    elif relative.endswith('catalog.py'):
        text = original.decode('utf-8')
        needle = "    if spec.get('value_role'):\n        return spec['value_role']\n"
        newline = '\r\n' if '\r\n' in text else '\n'
        needle = needle.replace('\n', newline)
        assert text.count(needle) == 1
        code = ("    if (spec.get('type') == 'boolean' or spec.get('boolean')) and name.endswith(\n"
                "            ('_confirmed', '_verified', '_proven', '_validated')):\n"
                "        return 'EVIDENCE'\n").replace('\n', newline)
        candidate = text.replace(needle, needle + code).encode('utf-8')
    else:
        candidate = (OUT / Path(relative).name).read_bytes()
    target = STAGE / 'staged' / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(candidate)
    # The read-only runtime loader still uses this projection, never canonical source.
    runtime = OUT / 'staged' / relative
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_bytes(candidate)
    digest = lambda value: hashlib.sha256(value).hexdigest()
    manifest[relative] = {'before': digest(original) if original is not None else None, 'staged': digest(candidate)}
    diff.extend(difflib.unified_diff((original or b'').decode('utf-8').splitlines(True), candidate.decode('utf-8').splitlines(True),
        fromfile='a/' + relative, tofile='b/' + relative))
(STAGE / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
(STAGE / 'staged.diff').write_text(''.join(diff), encoding='utf-8')
work = json.loads((OUT / 'workload.json').read_text(encoding='utf-8'))
work.update(status='QUALIFICATION_REPAIR_STAGED', revision_before={key: value['before'] for key, value in manifest.items()},
    files_changed=[], root_owned_files=targets, unresolved_decisions=[],
    requested_change='Separate missing genuine EVIDENCE/REFERENCE from example design completeness, reject invented machine proofs and keep missing/invalid CONFIGURATION blocking.',
    remaining_findings=['Canonical qualification repair not yet applied or integrated', 'Original-file saved models/simulations and exact-image delivery pending'])
work['repair'].update(first_failing_layer='Port reference planning/proof-role boundary',
    root_cause='The planner treats missing real evidence as missing design data and permits arbitrary evidence strings in machine port parameters.',
    affected_files=targets, reproduction='Actual native LIN/I2C missing-evidence findings and explicit forbidden-role candidate tests.')
work['created_at_utc'] = datetime.now(timezone.utc).isoformat()
(STAGE / 'workload.json').write_text(json.dumps(work, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'staged_files': len(manifest), 'canonical_changed': False}))
