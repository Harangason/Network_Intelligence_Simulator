"""Finalize only after exact PASS deployment and real production verification."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def ref(path):return {'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
production=read(HERE/'production-verification.json')
functional=read(HERE/'production-functional.json')
assert production['status']==functional['status']=='PASSED'
receipt_path=Path(production['receipt']);receipt=read(receipt_path)
assert receipt['status']=='PASS' and receipt.get('development_only') is not True
assert production['expected_image']==production['running_image']==receipt['image_id']
assert all(c['exit_code']==0 for c in receipt['checks'])
browser=read(HERE/'browser-report.json')
assert browser['stats']['unexpected']==0 and browser['stats']['expected']==9
assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in read(HERE/'after-hashes.json').items())
work=read(HERE/'workload.json')
diff=ref(HERE/'implementation.diff');browser_ref=ref(HERE/'browser-report.json')
release_ref=ref(receipt_path);production_ref=ref(HERE/'production-verification.json');functional_ref=ref(HERE/'production-functional.json')
work['after']=[ref(ROOT/name) for name in work['files_changed']]
work['diff']=[diff]
work['outcomes']={name:{'status':'PASSED','evidence':[diff,browser_ref]} for name in work['required_outcomes']}
work['outcomes']['verified_production_delivery']['evidence']=[release_ref,production_ref,functional_ref]
assert functional['observations']['fault_editor']['glossary_entries']==29
work['outcomes']['fault_editor_explanations']['evidence']=[functional_ref,ref(HERE/'fault-explanations-source-review.md'),ref(HERE/'fault-explanations.diff')]
work['validations']={
 'targeted':{'status':'PASSED','evidence':[browser_ref,ref(HERE/'targeted-unit.log'),ref(HERE/'targeted-validation.json')]},
 'typecheck':{'status':'PASSED','evidence':[release_ref]},
 'release':{'status':'PASSED','evidence':[release_ref]},
 'production':{'status':'PASSED','evidence':[production_ref,functional_ref]},
}
work['delivery'].update(tested_version=receipt['image_id'],running_version=production['running_image'],checks={
 'release':{'status':'PASSED','evidence':[release_ref]},
 'deployment':{'status':'PASSED','evidence':[production_ref]},
 'health':{'status':'PASSED','evidence':[production_ref]},
 'functional':{'status':'PASSED','evidence':[functional_ref]},
})
work['completion_status']='COMPLETED'
(HERE/'workload.json').write_text(json.dumps(work,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'VERIFIED_DELIVERY_RECORDED','image':receipt['image_id']}))
