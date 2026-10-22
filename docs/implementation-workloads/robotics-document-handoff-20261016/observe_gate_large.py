"""Read real large-case progress only from the owned release test stack."""
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
app_name = 'nis-e2e-app-502e1b59f134'
app = json.loads(subprocess.check_output([docker, 'inspect', app_name], text=True, encoding='utf-8'))[0]
assert app['Image'] == runtime['image_id'] and app['Config']['Labels']['networkis.test'] == 'disposable'
environment = dict(row.split('=', 1) for row in app['Config']['Env'] if '=' in row)
database = urlsplit(environment['DATABASE_URL'])
assert database.hostname == 'test-db' and database.path == '/nis_test_e2e'
binding = app['HostConfig']['PortBindings']['13500/tcp'][0]
assert binding['HostIp'] == '127.0.0.1' and binding['HostPort'] != '13500'
base = 'http://127.0.0.1:' + binding['HostPort']
with urlopen(base + '/api/engineering/projects', timeout=10) as response:
    projects = json.load(response)
selected = [row for row in projects['items'] if re.search(r'nis-e2e-large-[0-9a-f]{8}-', row['project_id'])]
assert len(selected) == 1, 'The core large-case project must be unique in this owned stack'
project = selected[0]['project_id']
with urlopen(Request(base + '/api/engineering/workflow?view=summary', headers={'X-Project-ID': project}), timeout=10) as response:
    workflow = json.load(response)
execution = (workflow.get('context') or {}).get('agent_execution') or {}
record = {'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'scope': 'Read-only actual release large-case status; no approvals, writes, mocks or product database access. Intermediate stage status is not an E2E PASS.',
          'image_id': app['Image'], 'project': project, 'active_step': workflow.get('active_step'),
          'statuses': workflow.get('statuses'), 'agent_execution_state': execution.get('state'), 'base_url': base}
with (OUT / 'large-case-live-observations.jsonl').open('a', encoding='utf-8') as stream:
    stream.write(json.dumps(record) + '\n')
print(json.dumps(record))
