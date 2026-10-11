"""Attach a real PASS receipt and actual production GET checks, without changing campaign state."""
import json
import argparse
from pathlib import Path
from record_evidence import reference, record
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('--receipt', type=Path, required=True)
parser.add_argument('--delivery-log', type=Path, required=True)
args=parser.parse_args()
receipt_path=args.receipt.resolve()
delivery_log=args.delivery_log.resolve()
receipt=json.loads(receipt_path.read_text(encoding='utf-8-sig'))
assert receipt['status']=='PASS'
required={'storage-tests','typecheck','frontend-tests','backend-tests','browser-e2e','small-http','large-http'}
assert required <= {check['name'] for check in receipt['checks'] if check['exit_code']==0}
# The canonical gate reuses an immutable production image after test-only changes.
# Retain the original successful build evidence, never invent a build in this run.
build_receipt_path=receipt_path
if not any(check['name']=='production-build' and check['exit_code']==0 for check in receipt['checks']):
    build_receipt_path=ROOT/'backend/test-output/release-gates/delivery-b37a5c6cc165/e7cc98f3e6fb/receipt.json'
build_receipt=json.loads(build_receipt_path.read_text(encoding='utf-8-sig'))
assert build_receipt['image_id']==receipt['image_id']
assert build_receipt['release']==receipt['release']
assert any(check['name']=='production-build' and check['exit_code']==0 for check in build_receipt['checks'])
functional=HERE/'production-functional.json'
result=json.loads(functional.read_text(encoding='utf-8'))
assert result['status']=='READ_ONLY_FUNCTIONAL_PASS'
assert result['running_image_id']==receipt['image_id']
review_path=HERE/'implementation-review.json'
review=json.loads(review_path.read_text(encoding='utf-8'))
review['verification']['nis_full_backend']='21792 passed, 56 subtests passed, 2 skipped, final current-base release'
review['verification']['nis_browser']='109 passed; actual small and exact 50/250/250 nine-stage wizard cases including restart/recovery; model/routing/topology parameter-return cases are additional targeted review-only tests'
http_scopes={}
for size in ('small','large'):
    report=json.loads((receipt_path.parent/(size+'-http.json')).read_text(encoding='utf-8'))
    scope=report['assessment']['scope_coverage']
    assert scope['complete'] is True and scope['scope_mode']=='ALL'
    http_scopes[size]={'project':report['project'],'statuses':report['statuses'],'scope_mode':scope['scope_mode'],
        'covered_messages':scope['covered_messages'],'covered_signals':scope['covered_signals'],
        'explicitly_excluded_messages':len(scope.get('excluded_message_ids',[])),
        'explicitly_excluded_signals':len(scope.get('excluded_signal_ids',[])),
        'evidence':reference(receipt_path.parent/(size+'-http.json'))}
review['verification']['nis_http']=http_scopes
review['verification']['release']='Complete canonical NIS release PASS and exact tested image deployed; actual image, readiness, current-project safety export and norm directory verified through GET only'
review['source_label_repair']={'prior_receipt':str(ROOT/'backend/test-output/release-gates/delivery-b37a5c6cc165/e7cc98f3e6fb/receipt.json'),'prior_result':'108 browser cases passed, 1 failed on obsolete source column selector; HTTP gate not reached, no deployment','repair':'Existing search/sort assertions retained; selector updated to intentional Technologie / Normbereich label','targeted_result':'All 4 existing source-directory browser cases passed against unchanged candidate image','evidence':str(HERE/'source-label-browser.log')}
review['release_delivery']={'receipt':str(receipt_path),'image_id':receipt['image_id'],'commit_id':receipt['release']['commit_id'],'source_sha256':receipt['release']['source_sha256'],'functional_check':str(functional),'eip_delivery':'NO, explicit user decision retained'}
review['release_delivery']['original_build_receipt']=str(build_receipt_path)
review['production_browser']={'project':'20261009072206008-4bb505f1',
    'scope':'Current build confirmed in browser; safety panel NOT_EVALUATED with no requirements, original historical OUTDATED evidence, ISO 26262-1/-5 and UN R155/R156 original source links; no product writes',
    'screenshots':[reference(HERE/'production-safety-ui.jpg'),reference(HERE/'production-norm-sources.jpg')]}
review['release_blocker']['resolved']='Exact newly failed candidate archived, scoped user approval obtained, removed, current-base full gate PASS and exact-image deployment completed'
review['image_cleanup_current']={'audit':str(HERE/'authorized-failed-candidate-removal.json'),'authorization':'Direct user reply to call_d01f754b62d0409a9d7725edfa4247b5','scope':'Only networkis:candidate-1d8155ff129c; full archive retained'}
review_path.write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
record('nis')
path=HERE/'nis-workload.json'
work=json.loads(path.read_text(encoding='utf-8'))
review_ref=reference(review_path)
patch_ref=reference(HERE/'nis-owned.diff')
for name in work['required_outcomes']:
    work['outcomes'][name]={'status':'PASSED','scope':'Requested implementation and verified NIS delivery; no normative conformity or independent human approval claimed','evidence':[review_ref,patch_ref] if name!='verified_delivery' else [reference(receipt_path),reference(functional)]}
for name, validation in work['validations'].items():
    if name=='release_gate':
        work['validations'][name]={'status':'PASSED','evidence':[reference(receipt_path)]}
    else:
        validation['evidence']=[ref for ref in validation['evidence'] if Path(ref['path']).name!='implementation-review.json']+[review_ref]
work['delivery'].update(tested_version=receipt['image_id'],running_version=result['running_image_id'],checks={
    'release':{'status':'PASSED','evidence':[reference(receipt_path)]},
    'deployment':{'status':'PASSED','evidence':[reference(delivery_log),reference(functional)]},
    'health':{'status':'PASSED','evidence':[reference(functional)]},
    'functional':{'status':'PASSED','evidence':[reference(functional)]}})
work['completion_status']='DELIVERED_VERIFIED'
path.write_text(json.dumps(work,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
# Updating shared review hashes retains the explicit EIP NO decision and blocked full delivery outcomes.
path=HERE/'eip-workload.json'
work=json.loads(path.read_text(encoding='utf-8'))
for section in ('outcomes','validations'):
    for item in work[section].values():
        if item.get('evidence'):
            item['evidence']=[review_ref if Path(ref['path']).name=='implementation-review.json' else ref for ref in item['evidence']]
path.write_text(json.dumps(work,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'RECORDED','image_id':receipt['image_id'],'receipt':str(receipt_path)}))
