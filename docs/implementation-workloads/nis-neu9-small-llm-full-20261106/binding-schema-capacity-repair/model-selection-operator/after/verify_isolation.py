"""Independent actual image, network, database DNS and empty project checks."""
import hashlib
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from urllib.parse import urlsplit
import urllib.request

goal = Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--state',type=Path,default=goal/'state.json')
args=parser.parse_args()
assert args.state.resolve().is_relative_to(goal)
out=args.state.resolve().parent
state = json.loads(args.state.read_text(encoding='utf-8'))
docker = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
def inspect(name):
    return json.loads(subprocess.check_output([docker,'inspect',name],encoding='utf-8'))[0]
app, db = (inspect(state['containers'][key]) for key in ['app','db'])
assert app['Image'] == state['image_id'] and app['State']['Running'] and db['State']['Running']
network = state['containers']['network']
assert set(app['NetworkSettings']['Networks']) == set(db['NetworkSettings']['Networks']) == {network}
env = dict(value.split('=',1) for value in app['Config']['Env'] if '=' in value)
dsn = urlsplit(env['DATABASE_URL'])
assert (dsn.hostname,dsn.port,dsn.username,dsn.path) == ('test-db',5432,'nis_test','/nis_test_e2e')
expected_model = state.get('expected_model', 'llama3.1:8b')
assert expected_model in {'llama3.1:8b', 'qwen3.5:9b'}
if expected_model == 'qwen3.5:9b':
    authorization = state['model_authorization']
    path = Path(authorization['path'])
    assert path.resolve() == (goal/'human-small-model-decision-20261107.json').resolve()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == authorization['sha256']
    decision = json.loads(path.read_text(encoding='utf8'))
    assert decision['verified_directly'] is True and expected_model in decision['human_message']
assert env['LOCAL_AI_MODEL'] == env['LOCAL_AI_FAST_MODEL'] == expected_model
assert env['LOCAL_AI_BASE_URL'] == 'http://host.docker.internal:11434/v1'
resolved = subprocess.check_output([docker,'exec',app['Id'],'python','-c',"import socket; print(socket.gethostbyname('test-db'))"],encoding='utf-8').strip()
assert resolved == db['NetworkSettings']['Networks'][network]['IPAddress']
assert any(row['HostIp'] == '127.0.0.1' and state['base_url'] == 'http://127.0.0.1:'+row['HostPort'] for row in app['NetworkSettings']['Ports']['13500/tcp'])
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
counts = {}
for name,path in [('build','/api/build-info'),('export','/api/engineering/projects/export'),('jobs','/api/simulations')]:
    with opener.open(urllib.request.Request(state['base_url']+path,headers={'X-Project-ID':state['project_id']}),timeout=15) as response:
        raw = response.read()
    body = json.loads(raw)
    if name == 'build':
        assert body['source_sha256'] == state['source_sha256']
    elif name == 'export':
        counts = {key:len(value) for key,value in body['source_data'].items()}
        assert not any(counts.values())
    else:
        assert body['jobs'] == []
    (out / ('start-'+name+'.json')).write_bytes(raw)
report = {'at':datetime.now(timezone.utc).isoformat(),'status':'VERIFIED_ISOLATED_SOURCE_ONLY',
          'app_id':app['Id'],'db_id':db['Id'],'network':network,'database_host':dsn.hostname,'resolved_db_ip':resolved,
          'image_id':app['Image'],'base_url':state['base_url'],'project_id':state['project_id'],'canonical_counts':counts,
          'configured_model':env['LOCAL_AI_MODEL'],'provider_url':env['LOCAL_AI_BASE_URL']}
(out / 'start-isolation-proof.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
