import hashlib,json,subprocess,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1]
out=root/'.tool-checker/reports'
docker='C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
app='nis-e2e-app-5d4cd2636806';db='nis-e2e-db-5d4cd2636806'
network='nis-e2e-network-5d4cd2636806';volume='nis-e2e-runtime-5d4cd2636806'
def run(*args):return subprocess.check_output([docker,*args],text=True,encoding='utf-8',errors='replace').strip()
checks=[]
for kind,name in [('container',app),('container',db),('network',network),('volume',volume)]:
    value=json.loads(run(*(['inspect',name] if kind=='container' else [kind,'inspect',name])))[0]
    labels=value['Config']['Labels'] if kind=='container' else value['Labels']
    if labels.get('networkis.test')!='disposable':raise RuntimeError('Not disposable: '+name)
    checks.append({'kind':kind,'name':name,'labels':labels})
for directory in sorted((root/'.tool-checker/evidence/industry40-live-ai').iterdir()):
    info=json.loads((directory/'run-id.json').read_text(encoding='utf-8'))
    if info['base']!='http://127.0.0.1:57797':raise RuntimeError('Wrong target')
    with urllib.request.urlopen(urllib.request.Request(info['base']+'/api/engineering/workflow',headers={'X-Project-ID':info['project']}),timeout=30) as response:state=json.load(response)
    (directory/'workflow-full.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
for name in [app,db]:
    result=subprocess.run([docker,'logs',name],capture_output=True,text=True,encoding='utf-8',errors='replace')
    (out/(name+'.log')).write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
results=[run('rm','-f',app,db),run('network','rm',network),run('volume','rm',volume)]
record={'verified_resources':checks,'removed':results,'product_resources_modified':False,'images_removed':False,'test_evidence_retained':True,'remaining_containers':run('ps','--format','{{.Names}}\t{{.Status}}\t{{.Ports}}')}
(out/'cleanup.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'removed':results,'evidence_retained':True}))
