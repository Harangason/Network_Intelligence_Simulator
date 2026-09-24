"""Archive evidence and remove only the two disposable stacks created by this audit."""
from pathlib import Path
import json, subprocess

OUT=Path(__file__).resolve().parent
DOCKER='C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
records=[]
for token,relative in [('514e6492cc50','stack'),('655ad99ad418','repaired-stack')]:
    receipt=json.loads((OUT/relative/token/'receipt.json').read_text())
    names=receipt['containers']
    for kind in ['app','db','network','runtime']:
        assert names[kind]=='nis-e2e-'+kind+'-'+token
    for kind in ['app','db']:
        observed=json.loads(subprocess.check_output([DOCKER,'inspect',names[kind]],text=True))[0]
        assert observed['Config']['Labels']['networkis.test']=='disposable'
    for kind,command in [('network','network'),('runtime','volume')]:
        observed=json.loads(subprocess.check_output([DOCKER,command,'inspect',names[kind]],text=True))[0]
        assert observed['Labels']['networkis.test']=='disposable'
    target=OUT/('runtime-evidence-'+token);target.mkdir(exist_ok=True)
    for folder in ['saved','service-logs']:
        subprocess.run([DOCKER,'cp',names['app']+':/app/backend/runtime/'+folder,str(target/folder)],check=True,capture_output=True)
    subprocess.run([DOCKER,'rm','-f',names['app'],names['db']],check=True,capture_output=True)
    subprocess.run([DOCKER,'network','rm',names['network']],check=True,capture_output=True)
    subprocess.run([DOCKER,'volume','rm',names['runtime']],check=True,capture_output=True)
    records.append({'token':token,'archived':str(target),'removed':names})
(OUT/'cleanup.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
print('Archived runtime evidence; removed only the two audit-owned disposable stacks.')
