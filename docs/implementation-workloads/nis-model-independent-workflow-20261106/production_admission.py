"""Read normal production status APIs; never start, cancel or modify a request."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import urllib.request

now = datetime.now(timezone.utc)
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
base = 'http://127.0.0.1:13500'
report = {'at': now.isoformat(), 'scope': 'Timestamped normal GETs for registered projects; no global provider queue claim',
          'projects': [], 'active': [], 'errors': []}
active = {'RUNNING', 'QUEUED', 'PENDING', 'STARTING', 'EXECUTING', 'CANCELING',
          'IN_PROGRESS', 'PLANNING', 'VALIDATING', 'REPAIRING'}


def get(path, project=None):
    req = urllib.request.Request(base + path, headers={'X-Project-ID': project} if project else {})
    with opener.open(req, timeout=10) as response:
        raw = response.read()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


inventory, _ = get('/api/engineering/projects')
assert inventory['next_offset'] is None, 'Inventory pagination must be handled before admission'
for project in inventory['items']:
    pid = project['project_id']
    entry = {'project_id': pid, 'response_hashes': {}}
    try:
        body, digest = get('/api/engineering/agent/conversation', pid)
        entry['response_hashes']['conversation'] = digest
        state = body.get('data') or {}
        entry.update({key: state.get(key) for key in ('run_id', 'lease_until', 'active_workload')})
        if state.get('run_id') and state.get('lease_until'):
            lease = datetime.fromisoformat(state['lease_until'].replace('Z', '+00:00'))
            if lease.tzinfo is None:
                lease = lease.replace(tzinfo=timezone.utc)
            if lease > now:
                report['active'].append({'project_id': pid, 'kind': 'current_conversation_lease', 'run_id': state['run_id']})
        workload = state.get('active_workload')
        if isinstance(workload, dict) and str(workload.get('status', '')).upper() in active:
            report['active'].append({'project_id': pid, 'kind': 'active_conversation_workload', 'status': workload['status']})
        for key, value in (state.get('engineering_draft') or {}).items():
            if 'generation' in key and isinstance(value, dict):
                entry[key] = {k: v for k, v in value.items() if k in ('status', 'phase', 'started_at', 'updated_at', 'token')}
                if str(value.get('status', '')).upper() in active:
                    report['active'].append({'project_id': pid, 'kind': key, 'status': value['status']})
        body, digest = get('/api/simulations', pid)
        entry['response_hashes']['simulations'] = digest
        entry['simulation_statuses'] = [{'id': j.get('id'), 'status': j.get('status')} for j in body.get('jobs') or []]
        for job in entry['simulation_statuses']:
            if str(job['status']).upper() in active:
                report['active'].append({'project_id': pid, 'kind': 'simulation', **job})
        entry['workloads'] = []
        for offset in range(0, 5001, 500):
            body, digest = get(f'/api/engineering/workloads?limit=500&offset={offset}', pid)
            entry['response_hashes']['workloads_' + str(offset)] = digest
            items = body.get('items') or []
            for item in items:
                summary = {'id': item.get('id') or item.get('workload_id'), 'status': item.get('status')}
                entry['workloads'].append(summary)
                if str(summary['status']).upper() in active:
                    report['active'].append({'project_id': pid, 'kind': 'workload', **summary})
            if len(items) < 500:
                break
        else:
            raise ValueError('Workload pagination limit reached; no idle conclusion')
    except Exception as error:
        report['errors'].append({'project_id': pid, 'error': str(error)})
    report['projects'].append(entry)

report['status'] = 'NO_ACTIVE_OBSERVED' if not report['errors'] and not report['active'] else 'REQUIRES_REVIEW'
out = Path('docs/implementation-workloads/nis-model-independent-workflow-20261106') / ('production-admission-' + now.strftime('%Y%m%dT%H%M%SZ') + '.json')
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'status': report['status'], 'projects_checked': len(report['projects']),
                  'active': report['active'], 'errors': report['errors'], 'path': str(out)}, ensure_ascii=True))
if report['errors'] or report['active']:
    raise SystemExit(1)
