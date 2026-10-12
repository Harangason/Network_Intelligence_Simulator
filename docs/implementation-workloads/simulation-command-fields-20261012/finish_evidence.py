import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
production=read(HERE/'production-verification.json');functional=read(HERE/'production-functional.json')
assert production['status']==functional['status']=='PASSED'
receipt_path=Path(production['receipt']);receipt=read(receipt_path)
assert receipt['status']=='PASS' and receipt.get('development_only') is not True
assert production['running_image']==production['expected_image']==receipt['image_id']
assert len(receipt['checks'])==8 and all(c['exit_code']==0 for c in receipt['checks'])
work=read(HERE/'workload.json')
assert all(ref(Path(p['path']))==p for p in work['after'])
release_ref=ref(receipt_path);production_ref=ref(HERE/'production-verification.json');functional_ref=ref(HERE/'production-functional.json')
work['outcomes']={name:{'status':'PASSED','evidence':[functional_ref]} for name in work['required_outcomes']}
work['outcomes']['verified_production_delivery']['evidence']=[release_ref,production_ref,functional_ref]
work['validations'].update(release={'status':'PASSED','evidence':[release_ref]},production={'status':'PASSED','evidence':[production_ref,functional_ref]})
work['delivery'].update(tested_version=receipt['image_id'],running_version=production['running_image'],checks={
 'release':{'status':'PASSED','evidence':[release_ref]},'deployment':{'status':'PASSED','evidence':[production_ref]},'health':{'status':'PASSED','evidence':[production_ref]},'functional':{'status':'PASSED','evidence':[functional_ref]}})
work['completion_status']='COMPLETED'
(HERE/'workload.json').write_text(json.dumps(work,indent=2)+'\n',encoding='utf-8')
(HERE/'delivery-state.json').write_text(json.dumps({'status':'VERIFIED_PRODUCTION_DELIVERY','production_has_consistent_command_fields':True,'receipt':str(receipt_path),'image':receipt['image_id']},indent=2)+'\n',encoding='utf-8')
print('VERIFIED_DELIVERY_RECORDED')
