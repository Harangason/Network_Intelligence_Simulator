"""Keep the original code baseline; make a fresh guard for authorized model apply."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
work = json.loads((HERE / 'workload.json').read_text(encoding='utf-8'))
plan = json.loads((HERE / 'reconciliation-preview.json').read_text(encoding='utf-8'))
prepared = json.loads((HERE / 'prepared-reconciliation-proposal.json').read_text(encoding='utf-8'))['data']
assert prepared['status'] == 'VALIDATED'
assert prepared['validation_result']['valid']
assert not work['unresolved_decisions']
work['revision_before'] = {
    relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
    for relative in work['files_changed']
}
for filename in ('reconciliation-preview.json', 'prepared-reconciliation-proposal.json'):
    path = HERE / filename
    work['revision_before'][str(path.relative_to(ROOT)).replace('\\', '/')] = hashlib.sha256(path.read_bytes()).hexdigest()
work['action_scope'] = 'Apply the explicitly approved, validated 86-change canonical channel reconciliation through normal versioned proposal review/apply, only after complete PASS deployment. No application edits or deletions.'
work['model_revision_before'] = plan['base_model_revision']
work['prepared_proposal_id'] = prepared['proposal_id']
(HERE / 'production-apply-guard-workload.json').write_text(json.dumps(work, indent=2), encoding='utf-8')
print(json.dumps({'proposal_id': prepared['proposal_id'], 'model_revision': plan['base_model_revision'], 'guard_scope': work['action_scope']}))
