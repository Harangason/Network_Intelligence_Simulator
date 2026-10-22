"""Stage a hash-bound product follow-up without editing canonical sources."""
from pathlib import Path
import hashlib
import json
import difflib

OUT = Path(__file__).resolve().parent / 'qualification-followup'
ROOT = OUT.parents[4]
OUT.mkdir(exist_ok=True)
FILES = {
    'backend/nis/agent/tools/wizard_generation.py': [(
        "        aliases = DEFAULT_TECHNOLOGY_REGISTRY.profile(technology, fields=('parameter_aliases',)).get('parameter_aliases') or {}\n        values = {aliases.get(key, key): value for key, value in port['parameters'].items() if roles.get(aliases.get(key, key)) == 'CONFIGURATION'}",
        "        normalized = DEFAULT_TECHNOLOGY_REGISTRY.normalize_parameters(technology, port['parameters'])\n        values = {key: value for key, value in normalized.items() if roles.get(key) == 'CONFIGURATION'}"), (
        "             'processing_evidence': 'NONE', 'timing_evidence': 'NONE'}",
        "             'processing_evidence': 'NONE', 'timing_evidence': 'NONE',\n             'hardware_evidence': False, 'qualification': 'UNVERIFIED'}"), (
        "    document_evidence['reference_design'] = {**stamp, 'coverage': deepcopy(reference['coverage']),",
        "    document_evidence['reference_design'] = {**stamp,\n        'qualification_findings': deepcopy(reference.get('qualification_findings', [])),\n        'coverage': deepcopy(reference['coverage']),")],
    'frontend/src/features/agent/lib/engineering-agent.ts': [(
        "  status: 'REVIEW_REQUIRED' | 'ACCEPTED'; canonical_writes: false;",
        "  status: 'REVIEW_REQUIRED' | 'ACCEPTED'; canonical_writes: false;\n  qualification?: 'UNVERIFIED'; hardware_evidence?: false;\n  qualification_findings?: { target_ref: string; technology: string; parameter: string; value_role: string;\n    qualification: 'UNVERIFIED'; hardware_evidence: false; finding: Record<string, unknown> }[];")],
    'frontend/src/features/agent/ui/agent-chat-core.tsx': [(
        "            <h4>Teilnehmer und Umfang</h4>",
        "            <p>Hardware- und Zeitnachweise bleiben ungeprüft. Die Freigabe dieses Beispielentwurfs ersetzt weder Preflight noch die technische Qualifikation.</p>\n            {(currentReference.qualification_findings?.length ?? 0) > 0 && <details><summary>Offene technische Nachweise ({currentReference.qualification_findings?.length})</summary>\n              <ul>{currentReference.qualification_findings?.map((row, index) => <li key={index}>{row.target_ref} · {row.technology} · {row.parameter} · {row.value_role}: {String(row.finding.message ?? row.finding.code ?? 'Nachweis offen')}</li>)}</ul>\n            </details>}\n            <h4>Teilnehmer und Umfang</h4>")],
}
manifest = {}
diff = []
for relative, replacements in FILES.items():
    path = ROOT / relative
    before = path.read_bytes()
    value = before.decode('utf-8')
    for old, new in replacements:
        assert value.count(old) == 1, (relative, old[:100], value.count(old))
        value = value.replace(old, new)
    target = OUT / 'staged' / relative
    original = OUT / 'before' / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(before)
    target.write_text(value, encoding='utf-8', newline='\n')
    manifest[relative] = {'before': hashlib.sha256(before).hexdigest(), 'staged': hashlib.sha256(target.read_bytes()).hexdigest(), 'staged_path': str(target)}
    diff += difflib.unified_diff(before.decode('utf-8').splitlines(True), value.splitlines(True), fromfile='before/' + relative, tofile='after/' + relative)
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
(OUT / 'staged.diff').write_text(''.join(diff), encoding='utf-8')
base = json.loads((OUT.parent / 'workload.json').read_text(encoding='utf-8'))
base.update(revision_before={key: item['before'] for key, item in manifest.items()}, owned_files=list(manifest), files_changed=[], before=[], after=[], diff=[], status='PLANNING')
base['repair'].update(root_cause='Reference parameter alias handling bypassed public registry normalization; qualification provenance was not explicit in canonical stamps or visible UI.', first_failing_layer='reference materializer and review presentation', reproduction='Public Ethernet bitrate alias maps to bitrate_bps through normalize_parameters but not through profile.parameter_aliases; proof findings require a separate visible qualification state.', affected_files=list(manifest), targeted_tests=['Canonical reference model persistence', 'Parameter alias and hardware evidence provenance', 'Frontend typecheck'])
(OUT / 'workload.json').write_text(json.dumps(base, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'staged_files': len(manifest), 'canonical_writes': 0}))
