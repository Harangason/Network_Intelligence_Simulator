import hashlib, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from backend.nis.engineering.network.network_scene import model_signature
old = json.loads((HERE / 'before-encoding-repair-reconciliation-preview.json').read_text(encoding='utf-8'))
new = json.loads((HERE / 'reconciliation-preview.json').read_text(encoding='utf-8'))
differences = []
derived = []
def compare(before, after, path):
    if before == after:
        return
    if isinstance(before, dict) and isinstance(after, dict):
        assert before.keys() == after.keys(), path
        for key in before:
            compare(before[key], after[key], path + '.' + key)
    elif isinstance(before, list) and isinstance(after, list):
        assert len(before) == len(after), path
        for index, (left, right) in enumerate(zip(before, after)):
            compare(left, right, path + '.' + str(index))
    else:
        assert isinstance(before, str) and isinstance(after, str), path
        if path in ('changes.85.data.topology.scene.modelSignature', 'changes.85.data.topology.scene.revision'):
            assert re.fullmatch('[0-9a-f]{64}', before) and re.fullmatch('[0-9a-f]{64}', after)
            derived.append(path)
            return
        assert after.encode('utf-8').decode('cp1252') == before, ('Non-encoding change', path)
        differences.append({'path': path, 'before': before, 'after': after})
compare(old['changes'], new['changes'], 'changes')
topology = new['changes'][85]['data']['topology']
scene = topology['scene']
assert model_signature(topology) == scene['modelSignature']
assert hashlib.sha256(json.dumps({key: value for key, value in scene.items() if key != 'revision'}, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == scene['revision']
assert old['replacements'] == new['replacements'] and old['base_model_revision'] == new['base_model_revision']
report = {'status': 'VERIFIED', 'text_changes': len(differences), 'differences': differences,
    'derived_signatures_recomputed_from_correct_text': derived,
    'all_non_text_repair_decisions_unchanged': True,
    'old_proposal': 'bed69265-d691-4e33-9f18-bf80246f4da5', 'old_proposal_status': 'REJECTED',
    'corrected_proposal': json.loads((HERE / 'prepared-reconciliation-proposal.json').read_text(encoding='utf-8'))['data']['proposal_id'],
    'canonical_model_changes_during_preparation': 0}
(HERE / 'verified-plan-text-repair.json').write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding='utf-8')
print(json.dumps({key: report[key] for key in ['status', 'text_changes', 'all_non_text_repair_decisions_unchanged']}))
