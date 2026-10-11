"""Read-only verification of the delivered exact release and selected project."""
import json, subprocess
from pathlib import Path
from urllib.request import Request, urlopen
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
RECEIPT=ROOT/'backend/test-output/release-gates/delivery-3112c6e77690/e169e94e6a7a/receipt.json'
PROJECT='network-project-20261005103106027-d3a78a2c'
DOCKER='C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
def get(base,path,headers=None):
    with urlopen(Request(base+path,headers=headers or {}),timeout=30) as response:
        return json.load(response)
def main():
    receipt=json.loads(RECEIPT.read_text())
    assert receipt['status']=='PASS' and receipt.get('development_only') is not True
    running=subprocess.check_output([DOCKER,'inspect','NetworkIS','--format','{{.Image}}'],text=True).strip()
    assert running==receipt['image_id']
    result={'status':'PASSED','checked_at':datetime.now(timezone.utc).isoformat(),'receipt':str(RECEIPT),'tested_image_id':receipt['image_id'],'running_image_id':running,'checks':{}}
    for name,base in [('local','http://127.0.0.1:13500'),('lan','http://192.168.178.10:13500')]:
        ready=get(base,'/api/ready');build=get(base,'/api/build-info')
        assert ready['status']=='ready' and build['source_sha256']==receipt['release']['source_sha256']
        result['checks'][name]={'ready':ready,'build':build}
    state=get('http://127.0.0.1:13500','/api/engineering/workflow/parameters',{'X-Project-ID':PROJECT})
    assert state['project_id']==PROJECT
    (OUT/'production-parameters-after.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    baseline=json.loads((OUT/'production-parameters-before.json').read_text())
    result['project_parameters_preserved']=state['parameters']==baseline['parameters']
    assert result['project_parameters_preserved'], 'Project data changed; inspect whether this was a concurrent user edit.'
    catalog=get('http://127.0.0.1:13500','/api/technologies')
    profiles={p['id']:p for d in catalog['domains'] for p in d['technologies']}
    missing=[];fields=0
    for tech,profile in profiles.items():
        for f in profile['parameter_schema']:
            fields+=1;v=f.get('simulation_default');proof=f.get('simulation_default_provenance') or {}
            if v is None or v=='':missing.append([tech,f['key']])
            assert proof.get('technology')==tech and proof.get('hardware_evidence') is False
            assert proof.get('status')=='ASSUMED' and proof.get('source')=='NIS_SIMULATION_ASSUMPTION' and proof.get('value')==v
    assert len(profiles)==125 and fields==14133 and not missing
    result['catalog']={'unique_profiles':len(profiles),'fields':fields,'missing':missing}
    (OUT/'production-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'image_id':running,'catalog':result['catalog'],'project_parameters_preserved':result['project_parameters_preserved']}))
if __name__=='__main__':main()
