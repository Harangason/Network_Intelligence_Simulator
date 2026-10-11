"""Seal this UI request against real unit, browser, release and live evidence."""
import hashlib, json, sys
from pathlib import Path

out=Path(__file__).parent
receipt_path=Path(sys.argv[1]).resolve()
receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
checks={'storage-tests','typecheck','frontend-tests','backend-tests','browser-e2e','small-http','large-http'}
assert receipt['status']=='PASS'
assert checks <= {c['name'] for c in receipt['checks'] if c['exit_code']==0}
build=json.loads((out/'after-live/build.json').read_text(encoding='utf-8'))
ready=json.loads((out/'after-live/ready.json').read_text(encoding='utf-8'))
assert ready=={'database':'available','status':'ready','storage':'available'}
before=json.loads((out/'before-live/parameters.json').read_text(encoding='utf-8'))['parameters']
after=json.loads((out/'after-live/parameters.json').read_text(encoding='utf-8'))['parameters']
visible=json.loads((out/'live-controls.json').read_text(encoding='utf-8'))
running=(out/'running-image.txt').read_text(encoding='utf-8').strip()
assert running==receipt['image_id']
assert build['source_sha256']==receipt['release']['source_sha256']
expected={'lin':{'lin_bitrate_bps':(19200,'19,2 kbit/s')},'can_fd':{'arbitration_bitrate':(500000,'500 kbit/s'),'data_bitrate':(2000000,'2 Mbit/s')},'ethernet':{'bitrate':(1000000000,'1 Gbit/s')}}
for technology,fields in expected.items():
    for key,(bits,display) in fields.items():
        assert before['simulation_parameter_assumptions'][technology]['values'][key]==bits
        assert after['simulation_parameter_assumptions'][technology]['values'][key]==bits
        assert visible[technology][key]==display
proof={'status':'PASSED','image_id':running,'source_sha256':build['source_sha256'],
       'live_canonical_rates_unchanged':True,'visible_rates':visible,'readiness':ready,
       'persistence_scope':'15 isolated real parameter browser cases, including SI edits/save/reload; production read-only display verification'}
(out/'functional-proof.json').write_text(json.dumps(proof,indent=2,ensure_ascii=False),encoding='utf-8')
def ref(p):
    p=Path(p).resolve()
    return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
w=json.loads((out/'workload.json').read_text(encoding='utf-8'))
for group in ('before','after','diff'):
    w[group]=[ref(e['path']) for e in w[group]]
gate=ref(receipt_path);functional=ref(out/'functional-proof.json');browser=ref(out/'browser-tests.log');deployment=ref(out/'deployment.log')
w['outcomes']={
    'readable_editable_rates':{'status':'PASSED','evidence':[browser,functional,ref(out/'live-ethernet.png')]},
    'lossless_canonical_persistence':{'status':'PASSED','evidence':[browser,functional,gate]},
    'production_delivery':{'status':'PASSED','evidence':[deployment,functional,gate]}}
w['validations']={
    'targeted_regression':{'status':'PASSED','evidence':[browser,ref(out/'frontend-tests.log'),ref(out/'typecheck.log')]},
    'full_release_gate':{'status':'PASSED','evidence':[gate]},
    'production_verification':{'status':'PASSED','evidence':[functional,ref(out/'after-live/build.json')]}}
w['delivery'].update(tested_version=running,running_version=running,checks={
    'release':{'status':'PASSED','evidence':[gate]},'deployment':{'status':'PASSED','evidence':[deployment]},
    'health':{'status':'PASSED','evidence':[functional]},'functional':{'status':'PASSED','evidence':[functional]}})
w['remaining_findings']=[]
w['completion_status']='COMPLETED'
(out/'workload.json').write_text(json.dumps(w,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(proof,ensure_ascii=False))
