from pathlib import Path
import json,hashlib,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
docker=json.loads((ROOT/'config/networkis.resources.json').read_text())['paths']['docker_cli']
stage=json.loads((HERE/'stage.json').read_text());prod=json.loads((HERE/'production-verification.json').read_text())
code="""
from pathlib import Path
import hashlib,json,shutil
build=Path('/app/frontend/.next-networkis')
files={str(p.relative_to(build)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(build.rglob('*')) if p.is_file() and 'cache' not in p.relative_to(build).parts}
digest=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()
assert digest==EXPECTED,'Live compiled artifact drift'
target=Path(STAGE)
assert target.resolve().parent==Path('/app') and target.name==NAME and not target.is_symlink()
assert not (target/'.next-networkis').exists(),'Only remove the stage after deployment moved its build'
assert Path(BACKUP,'.next-networkis/BUILD_ID').is_file(),'Preserve rollback'
shutil.rmtree(target)
print(json.dumps({'status':'PASSED','live_artifact_sha256':digest,'files':len(files),'temporary_stage_removed':True,'rollback_preserved':BACKUP}))
""".replace('EXPECTED',repr(prod['artifact_sha256'])).replace('STAGE',repr(stage['stage'])).replace('NAME',repr(Path(stage['stage']).name)).replace('BACKUP',repr(stage['backup']))
record=json.loads(subprocess.check_output([docker,'exec','NetworkIS','python','-c',code],text=True))
identity=json.loads(subprocess.check_output([docker,'inspect','NetworkIS'],text=True))[0]
assert identity['Image']==prod['base_image'] and identity['Id']==prod['container_id'] and identity['State']['Running']
record.update(base_image=identity['Image'],container_id=identity['Id'])
(HERE/'live-artifact-proof.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record,indent=2))
