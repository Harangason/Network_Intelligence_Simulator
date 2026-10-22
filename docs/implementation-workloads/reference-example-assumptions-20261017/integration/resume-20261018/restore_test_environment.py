"""Restore only the stopped disposable candidate database from its exact backup."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import time
import urllib.request

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
DOCKER = json.loads((ROOT/'config/networkis.resources.json').read_text())['paths']['docker_cli']
APP = 'nis-e2e-app-d851f62a961b'
DB = 'nis-e2e-db-d851f62a961b'
IMAGE = 'sha256:0a191a95598704d2dc1c0f1a7060665b8c896bfdf8d36ec8a43a5daa1a6a5d74'
BACKUP = OUT.parent/'pause-20261017/candidate-database.dump'
assert hashlib.file_digest(BACKUP.open('rb'),'sha256').hexdigest() == '66447085f307c4d22c20fcdeb21ea4fbb27105fe6a2c54471999473594bc788e'
def call(*args, timeout=60):
    return subprocess.run([DOCKER,*args],capture_output=True,text=True,encoding='utf-8',check=True,timeout=timeout).stdout.strip()
app,db,production = json.loads(call('inspect',APP,DB,'NetworkIS'))
assert app['Image'] == IMAGE and not app['State']['Running']
assert not db['State']['Running'] and DB != 'NetworkIS-db'
assert '/var/lib/postgresql/data' in (db['HostConfig'].get('Tmpfs') or {})
environment = dict(v.split('=',1) for v in db['Config']['Env'] if '=' in v)
assert environment['POSTGRES_DB']=='nis_test_e2e' and environment['POSTGRES_USER']=='nis_test'
call('start',DB)
for _ in range(120):
    ready = subprocess.run([DOCKER,'exec',DB,'pg_isready','-U','nis_test','-d','nis_test_e2e'],capture_output=True,timeout=10)
    if ready.returncode==0:break
    time.sleep(.5)
else:raise RuntimeError('Disposable database did not become ready')
call('cp',str(BACKUP),DB+':/tmp/nis-resume-20261018.dump')
toc = call('exec',DB,'pg_restore','--list','/tmp/nis-resume-20261018.dump')
assert 'TABLE DATA' in toc
(OUT/'restored-database-toc.txt').write_text(toc,encoding='utf-8')
call('exec',DB,'pg_restore','--clean','--if-exists','--no-owner','--no-privileges',
     '-U','nis_test','-d','nis_test_e2e','/tmp/nis-resume-20261018.dump',timeout=180)
call('start',APP)
port = json.loads(call('inspect',APP))[0]['NetworkSettings']['Ports']['13500/tcp'][0]['HostPort']
base = 'http://127.0.0.1:'+port
for _ in range(90):
    try:
        with urllib.request.urlopen(base+'/api/ready',timeout=2) as response:
            readiness=json.load(response)
        if readiness.get('status')=='ready':break
    except Exception:pass
    time.sleep(.5)
else:raise RuntimeError('Restored candidate did not become ready')
with urllib.request.urlopen(base+'/api/build-info',timeout=10) as response:build=json.load(response)
assert build['source_sha256']=='2d0d2b566456e5a8614b4cace16380ec0a3cb73525076fcf510ca8b0b538f0bd'
record={'status':'RESTORED_READY','at_utc':datetime.now(timezone.utc).isoformat(),
    'candidate_image':IMAGE,'base_url':base,'project_id':'20261017190202251-60e9cb65',
    'database_restored_from':str(BACKUP),'original_backup_sha256':hashlib.file_digest(BACKUP.open('rb'),'sha256').hexdigest(),
    'restore_scope':'Disposable candidate database only; exact saved backup, no model changes',
    'readiness':readiness,'build':build,'production_image_unchanged':call('inspect','NetworkIS','--format','{{.Image}}')==production['Image']}
(OUT/'restored-state.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':record['status'],'base_url':base,'project_id':record['project_id'],'production_unchanged':record['production_image_unchanged']}),flush=True)
