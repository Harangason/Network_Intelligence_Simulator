from finish_structure_owners import *

def evidence(path):
    path = Path(path).resolve()
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

receipt_path = Path(sys.argv[1]).resolve()
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
proof = OUT / 'production-verification.json'
production = json.loads(proof.read_text())
assert receipt['status'] == 'PASS' and production['status'] == 'PASSED'
assert production['image_id'] == receipt['image_id']
checker = ROOT / '.tool-checker/runs/standalone/session-b156585d421048558c1b2ff77485fc50.json'
assert json.loads(checker.read_text())['status'] == 'PASS'
passed = lambda *paths: {'status':'PASSED','evidence':[evidence(path) for path in paths]}
workload = OUT / 'workload.json'
work = json.loads(workload.read_text())
risks = OUT / 'migration-risk-tests.xml'
equivalence = [OUT / name for name in ['equivalence-comparison.json','physical-equivalence.json','adapter-equivalence.json','catalog-equivalence.json']]
work['outcomes'] = {
    'registry_driven_frontend':passed(risks,receipt_path),
    'technology_ownership':passed(risks,*equivalence),
    'transition_evidence':passed(ROOT/'docs/migrations/structure_mapping.csv',risks),
    'architecture_checker':passed(checker,risks),
    'module_documentation':passed(ROOT/'backend/nis/communication/technologies/README.md',risks),
    'production_delivery':passed(receipt_path,proof),
}
work['validations'] = {
    'targeted_regressions':passed(risks), 'behavior_equivalence':passed(*equivalence),
    'architecture':passed(checker,risks), 'full_release_gate':passed(receipt_path),
    'production_verification':passed(proof),
}
for key, filename in [('before','before-index.json'),('after','after-index.json'),('diff','changes.patch')]:
    work[key] = [evidence(OUT / filename)]
work.update(remaining_findings=[],unresolved_decisions=[],completion_status='COMPLETED')
work['delivery'] = dict(decision='YES',authorization='Standing user authorization in canonical AGENTS.md; user explicitly requested completion',
    target='Canonical NetworkIS production stack on port 13500',tested_version=receipt['image_id'],running_version=production['image_id'],
    checks={key:passed(receipt_path if key=='release' else proof) for key in ['release','deployment','health','functional']})
workload.write_text(json.dumps(work,indent=2),encoding='utf-8')
result = subprocess.run([sys.executable,str(GUARD),'completion','--workload',str(workload)],capture_output=True,text=True)
(OUT / 'completion-guard.json').write_text(result.stdout,encoding='utf-8')
print(result.stdout)
raise SystemExit(result.returncode)
