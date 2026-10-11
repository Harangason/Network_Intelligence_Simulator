import hashlib, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
work = json.loads((HERE / 'workload.json').read_text(encoding='utf-8'))
for key, name in [('canonical_reconciliation_preview', 'reconciliation-preview.json'),
                  ('canonical_prepared_proposal', 'prepared-reconciliation-proposal.json')]:
    work['validation'][key] = [ref(HERE / ('before-encoding-repair-' + name)), ref(HERE / name)]
work['validation']['plan_encoding_preservation'] = [ref(HERE / 'verified-plan-text-repair.json'), ref(HERE / 'rejected-encoding-plan.json')]
work['prepared_proposal_id'] = json.loads((HERE / 'prepared-reconciliation-proposal.json').read_text(encoding='utf-8'))['data']['proposal_id']
work['context'].update(image_deleted=True, production_model_mutations=0, production_fix_pending=True)
work['remaining_findings'] = ['Full release retry in progress after structure inventory repair.',
    'Canonical reconciliation validated with UTF-8 preservation; apply after exact complete PASS deployment.']
work['unresolved_decisions'] = []
work['delivery']['status'] = 'FULL_RELEASE_RETRY_IN_PROGRESS'
(HERE / 'workload.json').write_text(json.dumps(work, indent=2), encoding='utf-8')
