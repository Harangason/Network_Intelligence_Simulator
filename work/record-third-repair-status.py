from pathlib import Path
import hashlib,json

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'docs/implementation-workloads/technology-full-parameter-audit-20261001'
receipt=ROOT/'backend/test-output/release-gates/delivery-598d59124c0b/a47ee30356bb/receipt.json'
assert json.loads(receipt.read_text())['status']=='FAIL'
ref={'path':str(receipt),'sha256':hashlib.sha256(receipt.read_bytes()).hexdigest()}
p=FOLDER/'progress.json';progress=json.loads(p.read_text(encoding='utf-8'))
progress['complete_release_gate']='THIRD_GATE_FAILED_REPAIRED_AWAITING_FULL_RERUN'
progress['production_delivered']=False
progress.setdefault('release_history',[]).append({'status':'FAIL','evidence':ref,
    'scope':'21503 backend and 554 frontend tests passed; 73 browser tests passed, seven failed. No production deployment.'})
p.write_text(json.dumps(progress,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=FOLDER/'workload.json';w=json.loads(p.read_text(encoding='utf-8'))
w['validation']['complete_release_gate']={'status':'AWAITING_FULL_RERUN','evidence':[ref]}
w['audit_notes'].append('Third full gate found catalog timeout silently returning a development subset, invalid native parameter reviews yielding HTTP500, I2C editor missing its unconfirmed baseline mode, missing actionable native wizard evidence, and unqualified/contradictory Ethernet software fixtures. Repairs preserve strict geometry and evidence gates; focused browser rerun and full exact-image delivery remain required.')
p.write_text(json.dumps(w,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(progress['complete_release_gate'])
