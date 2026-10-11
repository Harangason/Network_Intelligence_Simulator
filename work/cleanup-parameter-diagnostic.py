"""Remove only the named disposable stack in a PREPARED diagnostic receipt."""
import argparse,json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DOCKER=r'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
parser=argparse.ArgumentParser()
parser.add_argument('receipt',type=Path)
args=parser.parse_args()
path=args.receipt.resolve()
assert path.is_relative_to(ROOT/'backend/test-output/parameter-browser-repairs')
receipt=json.loads(path.read_text(encoding='utf-8'))
assert receipt['status']=='PREPARED'
token=path.parent.name
names=receipt['containers']
for kind in ('app','db','network','runtime'):
    assert names[kind]=='nis-e2e-'+kind+'-'+token
    type_name='container' if kind in ('app','db') else 'network' if kind=='network' else 'volume'
    inspected=subprocess.run([DOCKER,type_name,'inspect',names[kind]],capture_output=True,text=True)
    if inspected.returncode: continue
    info=json.loads(inspected.stdout)[0]
    labels=info.get('Config',{}).get('Labels',{}) if type_name=='container' else info.get('Labels',{})
    assert labels.get('networkis.test')=='disposable'
    command=[DOCKER,'rm','-f',names[kind]] if type_name=='container' else [DOCKER,type_name,'rm',names[kind]]
    subprocess.run(command,check=True,capture_output=True)
print(json.dumps({'cleaned_receipt':str(path),'historical_images_removed':0}))
