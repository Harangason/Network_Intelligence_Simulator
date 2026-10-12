import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
work=json.loads((HERE/'workload.json').read_text(encoding='utf-8'))
name='frontend/src/features/simulation/ui/model-simulation-runner.tsx'
target=HERE/'before'/name;target.parent.mkdir(parents=True,exist_ok=True)
assert not target.exists();target.write_bytes((ROOT/name).read_bytes())
work['files_changed'].append(name)
work['before'].append({'path':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
work['revision_before']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in work['files_changed']}
work['required_outcomes']+=['signal_name_typography_and_bounds_restored','fault_editor_closed_by_default']
work['implementation_plan']+=['Restore original 11px signal-name typography on selection buttons and bound compact labels to their column; native fault-editor details closed by default']
(HERE/'workload.json').write_text(json.dumps(work,indent=2)+'\n',encoding='utf-8')
receipt=ROOT/'backend/test-output/release-gates/delivery-560672231aac/55a10e12998d/receipt.json'
data=json.loads(receipt.read_text(encoding='utf-8'))
assert data['status']=='RUNNING' and data['gate_pid']==66992 and 'image_id' not in data
(HERE/'interrupted-receipt-before.json').write_bytes(receipt.read_bytes())
data.update(status='FAIL',error='Orchestrator stopped before image build to include newly authorized signal typography and collapsed fault-editor changes; partial checks do not constitute PASS.',orchestrator_interrupted=True)
receipt.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
print('FOLLOWUP_BEFORE_EVIDENCE_AND_INTERRUPTION_RECORDED')
