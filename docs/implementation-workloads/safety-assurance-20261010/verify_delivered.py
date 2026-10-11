"""Read-only production checks after a complete PASS deployment."""
import argparse, json, urllib.request, subprocess
from pathlib import Path
from datetime import datetime, timezone
parser=argparse.ArgumentParser()
parser.add_argument('--receipt',required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parents[3]
receipt=json.loads(Path(args.receipt).read_text(encoding='utf-8-sig'))
assert receipt['status']=='PASS'
docker=json.loads((root/'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
running=subprocess.check_output([docker,'inspect','NetworkIS','--format','{{.Image}}'],text=True).strip()
assert running==receipt['image_id']
base='http://127.0.0.1:13500'
project='20261009072206008-4bb505f1'
def get(path):
    request=urllib.request.Request(base+path,headers={'X-Project-ID':project})
    with urllib.request.urlopen(request,timeout=45) as response:
        assert response.status==200
        return json.load(response)
ready=get('/api/ready')
build=get('/api/build-info')
assert ready['status']=='ready'
assert build['source_sha256']==receipt['release']['source_sha256']
assert build['commit_id']==receipt['release']['commit_id']
safety=get('/api/engineering/intelligence/safety')
assert safety['project_id'].endswith(project)
assert len(safety['profiles'])==3
assert {profile['standard'] for profile in safety['profiles']}=={'ISO 26262','UN R155','UN R156'}
bundle=safety['bundle']
assert bundle['payload']['release_approved'] is False
assert bundle['payload']['assessment']['normative_status']=='NOT_EVALUATED'
download=get('/api/engineering/intelligence/safety?download=1')
assert download==bundle
catalog=get('/api/technology-sources')
rows=[row for row in catalog['sources'] if any(area['id']=='safety-regulations' for area in row.get('categories',[]))]
assert len(rows)==4
result={'checked_at':datetime.now(timezone.utc).isoformat(),'status':'READ_ONLY_FUNCTIONAL_PASS','running_image_id':running,'receipt':str(Path(args.receipt).resolve()),'ready':ready,'build':build,'project_id':safety['project_id'],'safety_requirement_count':len(safety['requirements']),'safety_function_count':len(safety['functions']),'norm_profiles':safety['profiles'],'export_sha256':bundle['sha256'],'export_freshness':bundle['payload']['freshness'],'technical_status':bundle['payload']['assessment']['technical_status'],'normative_status':bundle['payload']['assessment']['normative_status'],'release_approved':False,'source_directory_norms':[{'name':row['name'],'url':row['url']} for row in rows],'scope':'GET requests only, current project; no product test data or independent human approval created'}
output=Path(__file__).with_name('production-functional.json')
output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
