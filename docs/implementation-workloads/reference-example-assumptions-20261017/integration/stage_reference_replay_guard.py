"""Persist an exact post-apply replay boundary using existing proposal ownership."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent / 'reference-replay-guard'
OUT.mkdir(exist_ok=True)
replacements = {
 'backend/nis/agent/tools/proposal_service.py': (
  '    contract.update(status="APPLIED", canonical_ids=canonical, revision=str(uuid4()))',
  '    contract.update(status="APPLIED", canonical_ids=canonical, revision=str(uuid4()))\n'
  "    if row['proposal_type'] == 'WIZARD_ENGINEERING_MODEL' and any(\n"
  "            item.get('source') == 'REFERENCE_ASSUMPTION' and item.get('reference_design')\n"
  "            for item in row.get('evidence') or []):\n"
  '        # The exact saved model, not the pre-apply source fingerprint, owns replay.\n'
  "        contract['applied_model_revision'] = model_revision()"),
 'backend/nis/agent/tools/wizard_generation.py': (
  "    proposals = proposal_store.list_proposals(limit=100)\n    reusable = _reusable_proposal('WIZARD_ENGINEERING_MODEL', proposal_identity, proposals)",
  "    proposals = proposal_store.list_proposals(limit=100)\n"
  "    if reference:\n"
  "        for prior in proposals:\n"
  "            contract = prior.get('engineering_contract') or {}\n"
  "            if prior['proposal_type'] != 'WIZARD_ENGINEERING_MODEL' or contract.get('status') != 'APPLIED':\n"
  "                continue\n"
  "            saved_reference = next((item.get('reference_design') for item in prior.get('evidence') or []\n"
  "                if item.get('source') == 'REFERENCE_ASSUMPTION'), None)\n"
  "            if not saved_reference or any(saved_reference.get(key) != reference[key]\n"
  "                    for key in ('design_id', 'revision', 'request_sha256', 'source_sha256', 'proposal')):\n"
  "                continue\n"
  "            same_generator = any(item.get('generator_version') == MODEL_GENERATOR_VERSION\n"
  "                                 for item in prior.get('evidence') or [])\n"
  "            if same_generator and contract.get('applied_model_revision') == model.model_revision():\n"
  "                return proposal_service.envelope(prior)\n"
  "            from backend.nis.infrastructure.persistence.db import ConcurrentUpdateError\n"
  "            raise ConcurrentUpdateError('Der bereits übernommene Referenzentwurf gehört zu einem geänderten Modell- oder Generatorstand. '\n"
  "                'Änderungen müssen als neuer geprüfter Modellvorschlag übernommen werden; keine doppelte Modellanlage.')\n"
  "    reusable = _reusable_proposal('WIZARD_ENGINEERING_MODEL', proposal_identity, proposals)"),
 'backend/tests/test_reference_model_persistence.py': (
  "    assert not [row for row in repeated.get('changes', []) if row.get('action', 'CREATE') == 'CREATE']",
  "    assert repeated['status'] == 'APPLIED'\n"
  "    assert repeated['proposal_id'] == applied['proposal_id']\n"
  "    assert repeated['canonical_ids'] == applied['canonical_ids']\n"
  "    assert call('read-again', saved_model) == objects\n"
  "    # A legitimate reviewed model change invalidates the old exact replay proof.\n"
  "    edited = call('edit', lambda _: proposal_service.create('TEST_MODEL_EDIT', [{'object_type': 'Function',\n"
  "        'action': 'UPDATE', 'object_id': str(functions[0]['id']), 'local_ref': 'reviewed-function-edit',\n"
  "        'data': {'description': 'Explicit reviewed isolated test modification'}}], 'Test canonical revision guard'))\n"
  "    edited = call('edit-validate', lambda _: proposal_service.validate(edited['proposal_id']))\n"
  "    assert edited['status'] == 'VALIDATED', edited['validation_result']\n"
  "    edited = call('edit-review', lambda _: proposal_service.review(edited['proposal_id'], revision=edited['revision'],\n"
  "        decision='approve', actor='test-human', trace_id=uuid4().hex))\n"
  "    assert call('edit-apply', lambda _: proposal_service.apply(edited['proposal_id'], actor='test-human', trace_id=uuid4().hex))['status'] == 'APPLIED'\n"
  "    rejected = execute(authority, 'stale-repeat', Permission.GENERATE_PROPOSAL, {'prompt': prompt}, wizard_generation.generate)\n"
  "    assert not rejected.success\n"
  "    assert any('geänderten Modell- oder Generatorstand' in row['message'] for row in rejected.findings)"),
}
h = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest, diff = {}, []
for relative, (old, new) in replacements.items():
    target = ROOT/relative
    before = target.read_text(encoding='utf-8')
    assert before.count(old) == 1, relative
    after = before.replace(old, new)
    for name, value in [('before', before), ('after', after)]:
        path = OUT/name/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value,encoding='utf-8')
    manifest[relative] = {'before': h(target), 'after': h(OUT/'after'/relative)}
    diff += difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='before/'+relative,tofile='after/'+relative)
w = json.loads((OUT.parent/'workload.json').read_text(encoding='utf-8'))
w.update(revision_before={key:item['before'] for key,item in manifest.items()},owned_files=list(manifest),files_changed=[],status='PLANNING')
evidence=OUT.parent/'qualification-followup/persistence4.log'
w['repair'].update(owner='PROJECT_PRODUCT',root_cause='Pre-apply proposal fingerprint changes after canonical writes; generator reenters CREATE-only reference materialization without a verified post-apply replay boundary.',first_failing_layer='Applied reference proposal replay',reproduction='Actual isolated full save succeeds; identical generator repeat fails because existing payload is not a newly proposed object.',affected_files=list(manifest),targeted_tests=['Exact applied reference replay leaves all saved objects unchanged','Reviewed canonical drift invalidates replay'],evidence=[{'path':str(evidence.resolve()),'sha256':h(evidence)}])
(OUT/'workload.json').write_text(json.dumps(w,ensure_ascii=False,indent=2),encoding='utf-8')
r=subprocess.run([str(ROOT/'backend/.venv/Scripts/python.exe'),'F:/CodexOrdner/skills/lokaler-implementierungs-agent/scripts/implementation_guard.py','before-apply','--workload',str(OUT/'workload.json')],capture_output=True,text=True,encoding='utf-8')
(OUT/'guard.json').write_text(r.stdout,encoding='utf-8');assert r.returncode==0,r.stdout
for relative,item in manifest.items():assert h(ROOT/relative)==item['before'],('PLAN_STALE',relative)
for relative in manifest:(ROOT/relative).write_bytes((OUT/'after'/relative).read_bytes())
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');(OUT/'applied.diff').write_text(''.join(diff),encoding='utf-8')
print(json.dumps({'applied':list(manifest),'model_writes':0}))
