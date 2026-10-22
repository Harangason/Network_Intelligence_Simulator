"""Read-only completion after the initial export comparison included its timestamp."""
import json
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen
P = Path(__file__).resolve().parent
D = r'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
APP = 'nis-e2e-app-b2bb3887246e'
def inspect(name):
    return json.loads(subprocess.check_output([D,'inspect',name]))[0]
audit=json.loads((P/'provider-correction.json').read_text())
assert inspect(APP)['Image']==audit['image']
assert not inspect(audit['old_container'])['State']['Running']
assert inspect(audit['database'])['State']['Running']
assert inspect('NetworkIS')['Image']=='sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b'
for project in ['20261018141834215-8feb758d','20261018143136468-0e49a16b']:
    with urlopen(Request('http://127.0.0.1:62470/api/engineering/projects/export',headers={'X-Project-ID':project}),timeout=30) as r:
        raw=r.read()
    (P/(project+'-after.json')).write_bytes(raw)
    before=json.loads((P/(project+'-before.json')).read_bytes())
    after=json.loads(raw)
    before.pop('generated_at',None); after.pop('generated_at',None)
    assert before==after
probe=subprocess.check_output([D,'exec',APP,'python','-c',"import json,urllib.request; p=json.load(urllib.request.urlopen('http://host.docker.internal:11434/api/tags')); m=next(x for x in p['models'] if x['name']=='qwen3.8:27b'); assert not m.get('remote_host'); print(json.dumps({'model':m['name'],'digest':m['digest'],'remote_host':m.get('remote_host')}))"],text=True)
audit.update(status='LOCAL_PROVIDER_CORRECTED_EXACT_IMAGE_AND_PROJECTS_PRESERVED',provider_probe=json.loads(probe),project_compare_excluded_only='generated_at export timestamp')
(P/'provider-correction.json').write_text(json.dumps(audit,indent=2)+'\n')
print(json.dumps(audit))
