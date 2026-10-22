"""Read-only observation of owned disposable release parameter-return cases."""
from pathlib import Path
import datetime
import json
import re
import subprocess
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']
runtime = json.loads((OUT / 'native-attempt-2/native-runtime-preparation.json').read_text(encoding='utf-8'))
app = json.loads(subprocess.check_output([docker, 'inspect', 'nis-e2e-app-502e1b59f134'], text=True, encoding='utf-8'))[0]
assert app['Image'] == runtime['image_id'] and app['Config']['Labels']['networkis.test'] == 'disposable'
environment = dict(row.split('=', 1) for row in app['Config']['Env'] if '=' in row)
database = urlsplit(environment['DATABASE_URL'])
assert database.hostname == 'test-db' and database.path == '/nis_test_e2e'
binding = app['HostConfig']['PortBindings']['13500/tcp'][0]
assert binding['HostIp'] == '127.0.0.1' and binding['HostPort'] != '13500'
base = 'http://127.0.0.1:' + binding['HostPort']
with urlopen(base + '/api/engineering/projects', timeout=10) as response:
    projects = json.load(response)
records = []
for row in projects['items']:
    project = row['project_id']
    if not (re.fullmatch(r'nis-e2e-large-return-(model|routing|topology)-[0-9a-f-]{36}', project)
            or re.fullmatch(r'astra-e2e-[0-9a-f]{12}', project)):
        continue
    with urlopen(Request(base + '/api/engineering/workflow?view=summary', headers={'X-Project-ID': project}), timeout=10) as response:
        workflow = json.load(response)
    execution = (workflow.get('context') or {}).get('agent_execution') or {}
    records.append({'project': project, 'active_step': workflow.get('active_step'), 'statuses': workflow.get('statuses'), 'agent_execution_state': execution.get('state'), 'agent_step': execution.get('step'), 'agent_message': str(execution.get('message', ''))[:500]})
record = {'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'scope': 'Read-only actual disposable release case status; no approvals, mutations, SQL tests or product database access. Intermediate progress does not establish PASS.', 'image_id': app['Image'], 'cases': records}
with (OUT / 'parameter-return-observations.jsonl').open('a', encoding='utf-8') as stream:
    stream.write(json.dumps(record) + '\n')
print(json.dumps(record))
