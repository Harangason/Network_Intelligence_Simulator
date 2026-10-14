import json,subprocess,sys,urllib.request
from pathlib import Path
base=Path(__file__).resolve().parent;root=base.parents[2]
receipt_path=Path(sys.argv[1]).resolve();receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
assert receipt['status']=='PASS'
docker=json.loads((root/'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
image=subprocess.check_output([docker,'inspect','NetworkIS','--format','{{.Image}}'],text=True).strip()
assert image==receipt['image_id']
result={'image_id':image,'receipt':str(receipt_path),'mutation':'NONE'}
for endpoint in ('ready','build-info'):
 with urllib.request.urlopen('http://127.0.0.1:13500/api/'+endpoint,timeout=10) as response:result[endpoint]=json.load(response)
assert result['ready']['status']=='ready'
assert result['build-info']['source_sha256']==receipt['release']['source_sha256']
probe=subprocess.run([docker,'exec','-i','NetworkIS','python','-'],input=(base/'production_probe.py').read_text(encoding='utf-8'),text=True,encoding='utf-8',capture_output=True)
if probe.returncode:raise RuntimeError(probe.stdout+probe.stderr)
result['functional']=json.loads(probe.stdout);assert result['functional']['status']=='PASSED'
result['status']='PASSED';(base/'production-functional.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'status':'PASSED','image_id':image,'industries':len(result['functional']['cases'])}))
