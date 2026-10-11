import hashlib,json,subprocess
from pathlib import Path
from uuid import uuid4

out = Path(__file__).parent.resolve()
receipt = json.loads((out/'performance-stack/e6ef799ce239/receipt.json').read_text(encoding='utf-8'))
assert receipt['image_id'] == 'sha256:d33e70db50af1769e96c7b97a273f8b1d8fd1800e05ebeec95b4b405e58f737a'
docker = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
name = 'nis-topology-baseline-'+uuid4().hex[:12]
created = subprocess.run([docker,'create','--name',name,'--label','networkis.test=disposable',receipt['image_id'],'true'],capture_output=True,text=True)
if created.returncode:
    raise RuntimeError(created.stderr)
records=[]
try:
    for relative,destination in [('backend/nis/agent/tools/validation.py','pre-topology-validation.py'),
            ('backend/nis/communication/technologies/lin/timing.py','pre-topology-lin-timing.py')]:
        target = out/destination
        assert not target.exists()
        subprocess.run([docker,'cp',name+':/app/'+relative,str(target)],check=True,capture_output=True)
        records.append({'source':relative,'path':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
finally:
    assert subprocess.check_output([docker,'inspect',name,'--format','{{ index .Config.Labels "networkis.test" }}'],text=True).strip()=='disposable'
    subprocess.run([docker,'rm',name],check=True,capture_output=True)
(out/'topology-baseline-image.json').write_text(json.dumps({'image_id':receipt['image_id'],
    'source_sha256':receipt['release']['source_sha256'],'files':records,'container_removed':name},indent=2),encoding='utf-8')
print(json.dumps({'files':len(records),'image_id':receipt['image_id']}))
