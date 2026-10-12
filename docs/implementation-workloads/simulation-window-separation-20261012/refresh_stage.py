import json,hashlib,subprocess,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[2]
docker=json.loads((ROOT/'config/networkis.resources.json').read_text())['paths']['docker_cli']
s=json.loads((HERE/'stage.json').read_text())
def run(*args): return subprocess.check_output([docker,*args],text=True)
hashes={n:hashlib.sha256((ROOT/'frontend'/n).read_bytes()).hexdigest() for n in s['source_hashes']}
if hashes==s['source_hashes']:
    print('Stage already matches source'); raise SystemExit(0)
patch=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()[:12]
manifest=json.loads((HERE/'frontend-build-info.json').read_text()); manifest.update(frontend_patch_id=patch,frontend_patch_source_hashes=hashes)
(HERE/'frontend-build-info.json').write_text(json.dumps(manifest,indent=2))
bundle=HERE/'frontend-source-refresh.tar'
with tarfile.open(bundle,'w') as tar:
    for n in hashes: tar.add(ROOT/'frontend'/n,arcname=n)
    tar.add(HERE/'frontend-build-info.json',arcname='public/build-info.json')
remote='/tmp/frontend-source-refresh-'+patch+'.tar'; target='/app/.frontend-ui-stage-'+patch
run('cp',str(bundle),'NetworkIS:'+remote)
code="from pathlib import Path; import tarfile; old=Path("+repr(s['stage'])+"); target=Path("+repr(target)+"); assert old.parent==target.parent==Path('/app') and old.name.startswith('.frontend-ui-stage-') and not target.exists(); old.rename(target); tarfile.open("+repr(remote)+").extractall(target,filter='data')"
run('exec','NetworkIS','python','-c',code)
# If the previous stage was deployed, baseline the next overlay against that
# exact live source instead of against the original image-layer files.
production=HERE/'production-verification.json'
if production.exists() and json.loads(production.read_text())['patch_id']==s['patch_id']:
    s['before_source_hashes']=s['source_hashes']
s.update(patch_id=patch,stage=target,backup='/app/.frontend-ui-rollback-'+patch,source_hashes=hashes)
(HERE/'stage.json').write_text(json.dumps(s,indent=2));print('Stage refreshed:',patch)
