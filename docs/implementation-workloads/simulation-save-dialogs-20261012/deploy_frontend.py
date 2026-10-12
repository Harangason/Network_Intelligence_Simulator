import hashlib, json, subprocess, time
from pathlib import Path
from urllib.request import urlopen
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DOCKER = json.loads((ROOT / 'config/networkis.resources.json').read_text())['paths']['docker_cli']
stage = json.loads((HERE / 'stage.json').read_text())
def run(*args):
    return subprocess.check_output([DOCKER, *args], text=True)
identity = json.loads(run('inspect', 'NetworkIS'))[0]
assert identity['Id'] == stage['container_id'] and identity['Image'] == stage['base_image']
for name, expected in stage['source_hashes'].items():
    assert hashlib.sha256((ROOT / 'frontend' / name).read_bytes()).hexdigest() == expected, 'Local revision drift'
assert json.loads((HERE / 'typecheck.json').read_text())['status'] == 'PASSED'
code = """
from pathlib import Path
import json, hashlib, tarfile, shutil
stage = Path(STAGE)
backup = Path(BACKUP)
live = Path('/app/frontend')
assert stage.parent == backup.parent == live.parent == Path('/app')
assert stage.name.startswith('.frontend-ui-stage-') and backup.name.startswith('.frontend-ui-rollback-')
assert not backup.exists(), 'Rollback copy already exists'
expected = EXPECTED
before = BEFORE
for name, digest in expected.items():
    assert hashlib.sha256((stage/name).read_bytes()).hexdigest() == digest
    assert (hashlib.sha256((live/name).read_bytes()).hexdigest() if (live/name).exists() else None) == before[name], 'Production source drift'
build = stage/'.next-networkis'
assert (build/'BUILD_ID').is_file() and (build/'required-server-files.json').is_file()
files = {str(p.relative_to(build)): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in sorted(build.rglob('*')) if p.is_file() and 'cache' not in p.relative_to(build).parts}
artifact_hash = hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()
record = {'artifact_sha256':artifact_hash,'artifact_files':len(files),'next_build_id':(build/'BUILD_ID').read_text().strip(),'patch_id':PATCH}
(stage/'public/frontend-patch.json').write_text(json.dumps(record,indent=2))
archive = Path('/tmp/frontend-artifact-'+PATCH+'.tar')
with tarfile.open(archive,'w') as bundle:
    bundle.add(build,arcname='.next-networkis',filter=lambda item:None if '/cache/' in item.name or item.name.endswith('/cache') else item)
    bundle.add(stage/'public',arcname='public')
    for name in expected: bundle.add(stage/name,arcname=name)
record['artifact_archive_sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
record['artifact_archive']=str(archive)
backup.mkdir()
shutil.copytree(live/'.next-networkis',backup/'.next-networkis',symlinks=True)
for name in [*expected,'public/build-info.json','public/frontend-patch.json']:
    target=backup/name
    target.parent.mkdir(parents=True,exist_ok=True)
    if (live/name).is_file(): shutil.copyfile(live/name,target)
record['rollback_next_build_id']=(backup/'.next-networkis/BUILD_ID').read_text().strip()
# Docker overlayfs cannot rename lower-layer directories. Back up the original
# compiled tree, then replace only that verified tree and the scoped files.
assert (live/'.next-networkis').resolve().parent == live.resolve()
assert (backup/'.next-networkis/BUILD_ID').is_file()
try:
    shutil.rmtree(live/'.next-networkis')
    build.rename(live/'.next-networkis')
    for name in [*expected,'public/build-info.json','public/frontend-patch.json']:
        (live/name).parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(stage/name,live/name)
except BaseException:
    if (live/'.next-networkis').exists(): shutil.rmtree(live/'.next-networkis')
    shutil.copytree(backup/'.next-networkis',live/'.next-networkis',symlinks=True)
    for name in [*expected,'public/build-info.json','public/frontend-patch.json']:
        if (backup/name).is_file(): shutil.copyfile(backup/name,live/name)
        else: (live/name).unlink(missing_ok=True)
    raise
print(json.dumps(record))
""".replace('STAGE',repr(stage['stage'])).replace('BACKUP',repr(stage['backup'])).replace('EXPECTED',repr(stage['source_hashes'])).replace('BEFORE',repr(stage['before_source_hashes'])).replace('PATCH',repr(stage['patch_id']))
record = json.loads(run('exec','NetworkIS','python','-c',code))
print('Frontend bundle installed, restarting the existing container',flush=True)
run('restart','NetworkIS')
health = {}
try:
    for base in ['http://127.0.0.1:13500','http://192.168.178.10:13500']:
        for attempt in range(60):
            try:
                with urlopen(base+'/api/ready',timeout=5) as response: ready=json.load(response)
                with urlopen(base+'/frontend-patch.json',timeout=5) as response: patch=json.load(response)
                with urlopen(base+'/api/build-info',timeout=5) as response: backend=json.load(response)
                assert ready['status']=='ready' and patch['artifact_sha256']==record['artifact_sha256']
                assert backend['build_id']==stage['base_build_id']
                health[base]={'ready':ready,'frontend_patch':patch,'backend_build':backend}
                break
            except Exception:
                if attempt==59: raise
                time.sleep(1)
except BaseException:
    rollback = "from pathlib import Path; import shutil; live=Path('/app/frontend'); backup=Path("+repr(stage['backup'])+"); failed=Path("+repr(stage['stage']+'-failed-build')+"); assert not failed.exists(); (live/'.next-networkis').rename(failed); shutil.copytree(backup/'.next-networkis',live/'.next-networkis',symlinks=True); files="+repr([*stage['source_hashes'],'public/build-info.json','public/frontend-patch.json'])+"; [(shutil.copyfile(backup/n,live/n) if (backup/n).is_file() else (live/n).unlink(missing_ok=True)) for n in files]"
    run('exec','NetworkIS','python','-c',rollback)
    run('restart','NetworkIS')
    raise
identity_after=json.loads(run('inspect','NetworkIS'))[0]
assert identity_after['Image']==stage['base_image'] and identity_after['Id']==stage['container_id']
archive_root=Path('F:/CodexOrdner/visualizations/2026/10/09/01a11f88-d6c9-7b63-bec3-26450a86e52c')
archive_path=archive_root/('frontend-ui-'+stage['patch_id']+'.tar')
assert not archive_path.exists()
run('cp','NetworkIS:'+record['artifact_archive'],str(archive_path))
assert hashlib.sha256(archive_path.read_bytes()).hexdigest()==record['artifact_archive_sha256']
record.update(status='PASSED',deployed_at=datetime.now(timezone.utc).isoformat(),base_image=stage['base_image'],container_id=stage['container_id'],image_created=False,full_gate_run=False,artifact_archive_local=str(archive_path),rollback_path=stage['backup'],health=health)
(HERE/'production-verification.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps({k:record[k] for k in ['status','patch_id','artifact_sha256','base_image','image_created','full_gate_run']},indent=2))
