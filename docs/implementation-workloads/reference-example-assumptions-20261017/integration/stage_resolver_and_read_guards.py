"""Guarded small follow-up; preserve both failed test-read observations."""
import json
import hashlib
import subprocess
import difflib
from pathlib import Path

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent / 'qualification-followup' / 'resolver-and-read-guards'
OUT.mkdir(exist_ok=True)
edits = {
 'backend/nis/agent/tools/project_draft.py': [("    checked = validate_reference_design(record['proposal'], prepare_reference_design(record['request']))\n    if checked['request_sha256'] != record['request_sha256'] or checked['catalog_sha256'] != record['catalog_sha256']:\n        raise ConcurrentUpdateError('Die Quellen- oder Katalogrevision des Referenzentwurfs ist veraltet.')", "    checked = validate_reference_design(record['proposal'], prepare_reference_design(record['request']))\n    if checked['proposal']['unresolved']:\n        raise ConcurrentUpdateError('Der bestätigte Referenzentwurf erfüllt die aktuellen Entwurfsanforderungen nicht mehr. Erneut prüfen: '\n            + '; '.join(item['message'] for item in checked['proposal']['unresolved'][:8]))\n    if checked['request_sha256'] != record['request_sha256'] or checked['catalog_sha256'] != record['catalog_sha256']:\n        raise ConcurrentUpdateError('Die Quellen- oder Katalogrevision des Referenzentwurfs ist veraltet.')")],
 'backend/tests/test_reference_model_persistence.py': [("    for message in objects['Message']:\n        assert message.get('consumer_refs'), message", "    hardware_ids = {row['name']: str(row['id']) for row in objects['HardwareNode']}\n    device_ids = {row['id']: hardware_ids[row['name']] for row in record['proposal']['devices']}\n    expected_communication = {row['id']: row for row in record['proposal']['communication']}\n    for message in objects['Message']:\n        config = message['configuration']\n        expected = expected_communication[config['reference_design']['communication_id']]\n        contract = config['communication_contract']\n        assert contract['producer_ref'] == device_ids[expected['producer_device_id']]\n        assert contract['consumer_refs'] == [device_ids[key] for key in expected['consumer_device_ids']]\n        assert config['transport_unit']['consumer_refs'] == contract['consumer_refs']")],
}
new_test = '''\n\ndef test_accepted_plan_cannot_bypass_new_validation_findings(reference, monkeypatch):
    authority, request, record, _calls = reference
    accepted = run(authority, drafts.accept_reference_design,
                   {key: record[key] for key in ('design_id', 'revision', 'request_sha256')}).data
    original = intake.validate_reference_design
    def newly_required(proposal, prepared):
        checked = original(proposal, prepared)
        checked['proposal']['unresolved'].append({'code': 'NEW_REQUIRED_CONFIGURATION',
            'target_ref': 'PC', 'message': 'New mandatory configuration remains unresolved'})
        return checked
    monkeypatch.setattr(intake, 'validate_reference_design', newly_required)
    result = run(authority, lambda _: drafts.reference_design_for_prompt(request['prompt'] + '\\n' + marker(accepted)))
    assert not result.success
    assert any('aktuellen Entwurfsanforderungen' in row['message'] for row in result.findings)
'''
relative = 'backend/tests/test_reference_design_integration.py'
edits[relative] = [(None, new_test)]
h = lambda b: hashlib.sha256(b).hexdigest()
manifest = {}
diff = []
for relative, replacements in edits.items():
    target = ROOT / relative
    before = target.read_text(encoding='utf-8')
    after = before
    for old, new in replacements:
        if old is None:
            assert 'def test_accepted_plan_cannot_bypass_new_validation_findings' not in after
            after += new
        else:
            assert after.count(old) == 1, relative
            after = after.replace(old, new)
    for sub, text in [('before', before), ('after', after)]:
        path = OUT / sub / relative; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    manifest[relative] = {'before': h(target.read_bytes()), 'after': h((OUT / 'after' / relative).read_bytes())}
    diff += difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='before/'+relative, tofile='after/'+relative)
(OUT / 'applied.diff').write_text(''.join(diff), encoding='utf-8')
w = json.loads((OUT.parent / 'workload.json').read_text(encoding='utf-8'))
w.update(revision_before={key: item['before'] for key, item in manifest.items()}, owned_files=list(manifest), files_changed=[], status='PLANNING')
w['repair'].update(owner='PROJECT_PRODUCT', first_failing_layer='Accepted-plan server revalidation', root_cause='Server checked only unchanged source/catalog digest and ignored new semantic unresolved findings; persistence regression also needs canonical Message read contract.', reproduction='A revalidated accepted design can now return unresolved findings while old hashes remain equal.', affected_files=list(manifest), targeted_tests=['New required configuration invalidates accepted plan', 'Exact saved communication recipients and physical parameters'])
(OUT / 'workload.json').write_text(json.dumps(w, ensure_ascii=False, indent=2), encoding='utf-8')
r = subprocess.run([str(ROOT/'backend/.venv/Scripts/python.exe'), 'F:/CodexOrdner/skills/lokaler-implementierungs-agent/scripts/implementation_guard.py', 'before-apply', '--workload', str(OUT/'workload.json')], capture_output=True, text=True, encoding='utf-8')
(OUT/'guard.json').write_text(r.stdout,encoding='utf-8')
assert r.returncode == 0, r.stdout
for relative, item in manifest.items():
    assert h((ROOT/relative).read_bytes()) == item['before'], ('PLAN_STALE', relative)
for relative in manifest:
    (ROOT/relative).write_bytes((OUT/'after'/relative).read_bytes())
(OUT/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps({'applied_files': list(manifest), 'model_writes': 0}))
