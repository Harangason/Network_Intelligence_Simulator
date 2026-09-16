import json, os, subprocess, time, urllib.request
from pathlib import Path
d='C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
p=Path('backend/test-output/industry60-recheck-stack/919f1a3730d4/receipt.json')
r=json.loads(p.read_text()); name=r['containers']['app']
def inspect(n): return json.loads(subprocess.check_output([d,'inspect',n],text=True))[0]
old=inspect(name)
assert name=='nis-e2e-app-919f1a3730d4' and old['Config']['Labels']['networkis.test']=='disposable'
env=dict(x.split('=',1) for x in old['Config']['Env'])
env.update(LOCAL_AI_BASE_URL='http://host.docker.internal:11434/v1',LOCAL_AI_MODEL='qwen3.8:27b',LOCAL_AI_FAST_MODEL='llama3.1:8b')
assert '@test-db:' in env['DATABASE_URL']
subprocess.run([d,'rm','-f',name],check=True,stdout=subprocess.DEVNULL)
args=[d,'run','-d','--name',name,'--network',r['containers']['network'],'--label','networkis.test=disposable']
for key in ['DATABASE_URL','NETWORKIS_ALLOW_NON_CANONICAL_ROOT','NUMERIC_ACCELERATOR','SIMULATOR_RUNTIME_ROOT','SIMULATION_EXECUTOR','AI_PROVIDER','CLOUD_ESCALATION','LOCAL_AI_BASE_URL','LOCAL_AI_MODEL','LOCAL_AI_FAST_MODEL']:
    args+=['-e',key]
args+=['-p','127.0.0.1:'+r['base_url'].rsplit(':',1)[1]+':13500','--mount','type=volume,source='+r['containers']['runtime']+',target=/app/backend/runtime',r['image_id']]
subprocess.run(args,env={**os.environ,**env},check=True,stdout=subprocess.DEVNULL)
for i in range(60):
    try:
        urllib.request.urlopen(r['base_url']+'/api/ready',timeout=2)
        break
    except Exception: time.sleep(1)
probe=subprocess.check_output([d,'exec',name,'python','-c',"import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/api/tags',timeout=5).read().decode())"],text=True)
models=json.loads(probe)
Path('.tool-checker/industry60-recheck-ai-preflight.json').write_text(json.dumps({'models':models,'test_container':name,'base_url':r['base_url'],'image_id':r['image_id']},indent=2),encoding='utf-8')
print(json.dumps({'models':[m['name'] for m in models['models']],'test_container':name}))

