import difflib,hashlib,json,shutil,sys
from pathlib import Path
base=Path(__file__).resolve().parent;root=base.parents[2]
work=json.loads((base/'workload.json').read_text(encoding='utf-8'))
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
after=[];diff=[]
for name in work['files_changed']:
 source=root/name;target=base/'after'/name;before=base/'before'/name
 target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);after.append(ref(target))
 diff.extend(difflib.unified_diff(before.read_text(encoding='utf-8-sig').splitlines(keepends=True),source.read_text(encoding='utf-8-sig').splitlines(keepends=True),fromfile='before/'+name,tofile='after/'+name))
(base/'owned-changes.diff').write_text(''.join(diff),encoding='utf-8');work['after']=after;work['diff']=[ref(base/'owned-changes.diff')]
work['outcomes']['agent_functional_workflow']['evidence']=[ref(base/'targeted-tests-final.log'),ref(base/'implementation.md'),ref(base/'owned-changes.diff')]
if (base/'release-test-data-repair-targeted.log').is_file():
 work['outcomes']['agent_functional_workflow']['evidence'].append(ref(base/'release-test-data-repair-targeted.log'))
if len(sys.argv)>1:
 path=Path(sys.argv[1]).resolve();receipt=json.loads(path.read_text(encoding='utf-8'));live=json.loads((base/'production-functional.json').read_text(encoding='utf-8'))
 assert receipt['status']=='PASS' and live['status']=='PASSED'
 assert receipt['image_id']==live['image_id'] and live['build-info']['source_sha256']==receipt['release']['source_sha256']
 shutil.copyfile(path,base/'release-pass-receipt.json');release=ref(base/'release-pass-receipt.json');production=ref(base/'production-functional.json')
 transition_path=base/'verification-input-transition.json'
 if transition_path.is_file():
  transition=json.loads(transition_path.read_text(encoding='utf-8'))
  transition.update(full_release_status='PASSED',full_release_evidence=release,production_evidence=production)
  transition_path.write_text(json.dumps(transition,indent=2)+'\n',encoding='utf-8')
  transition_ref=ref(transition_path)
  work['validations']['verification_input_transition']={'status':'PASSED','evidence':[transition_ref]}
  work['validations']['live_qwen_full_source']['evidence']=[transition_ref if Path(item['path']).resolve()==transition_path.resolve() else item for item in work['validations']['live_qwen_full_source']['evidence']]
 work['validations']['release_gate']={'status':'PASSED','evidence':[release]}
 work['outcomes']['verified_production_delivery']={'status':'PASSED','evidence':[release,production]}
 work['delivery'].update(blocker=None,release_state='DEPLOYED',tested_version=receipt['image_id'],running_version=live['image_id'],checks={name:{'status':'PASSED','evidence':[release] if name=='release' else [production]} for name in ('release','deployment','health','functional')})
 work['status']='COMPLETED'
(base/'workload.json').write_text(json.dumps(work,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':work['status'],'production':work['outcomes']['verified_production_delivery']['status']}))
