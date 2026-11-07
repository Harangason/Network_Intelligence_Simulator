"""Timestamped normal GETs; never start or mutate the user's model."""
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
import urllib.request

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
project = 'network-project-20261106093746010-f2585546'
report = {'at': datetime.now(timezone.utc).isoformat(), 'project': project, 'scope': 'Normal read-only production status, not test execution or a global queue inventory', 'responses': {}}
for path in ['/api/ready', '/api/build-info', '/api/engineering/workflow?view=summary', '/api/engineering/agent/conversation', '/api/simulations']:
    request = urllib.request.Request('http://127.0.0.1:13500' + path, headers={'X-Project-ID': project})
    with opener.open(request, timeout=15) as response:
        raw = response.read()
    body = json.loads(raw)
    if 'conversation' in path:
        value = body.get('data') or {}
        body = {'run_id': value.get('run_id'), 'lease_until': value.get('lease_until'), 'active_workload': value.get('active_workload'), 'engineering_draft_keys': list((value.get('engineering_draft') or {}).keys()), 'active_proposal': value.get('active_proposal')}
    elif 'workflow?' in path:
        body = {'statuses': body.get('statuses'), 'execution': body.get('context', {}).get('agent_execution')}
    elif path == '/api/simulations':
        body = {'jobs': [{key: job.get(key) for key in ('id', 'status')} for job in body.get('jobs', [])]}
    report['responses'][path] = {'sha256': hashlib.sha256(raw).hexdigest(), 'status': 200, 'summary': body}
path = Path(__file__).parent / ('user-project-status-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.json')
path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'path': str(path), 'responses': report['responses']}, ensure_ascii=True))
