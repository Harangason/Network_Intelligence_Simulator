"""Read current wizard progress only inside the disposable release container."""
import json
import subprocess
from pathlib import Path

folder = Path(__file__).resolve().parent
root = folder.parents[2]
receipt = json.loads(Path(json.loads((folder / 'workload.json').read_text())['active_release_receipt']).read_text())
name = receipt['containers']['app']
assert name.startswith('nis-e2e-app-') and name != 'NetworkIS'
docker = json.loads((root / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
code = '''
import json
from urllib.request import Request, urlopen
def get(path, project=None):
    with urlopen(Request('http://127.0.0.1:13500/api/engineering/' + path,
                         headers={'X-Project-ID': project} if project else {}), timeout=20) as response:
        return json.load(response)
projects = get('projects?offset=0')
rows = projects.get('items', []) if isinstance(projects, dict) else projects
for row in rows:
    identifier = row.get('project_id') or row.get('id')
    if identifier and ('nis-e2e-large' in str(identifier) or str(identifier).startswith('astra-e2e-')):
        workflow = get('workflow?view=summary', identifier)
        execution = workflow.get('context', {}).get('agent_execution') or {}
        detail = {}
        if workflow.get('statuses', {}).get('validation') == 'WARNING':
            from backend.nis.engineering.capacity.service import preflight_warning_signature
            preflight = get('preflight', identifier)
            full = get('workflow/parameters', identifier)
            approval = full.get('parameters', {}).get('preflight_warning_approval') or {}
            detail = {'preflight_id': preflight.get('id'), 'results': {key: preflight.get('results', {}).get(key)
                for key in ('preflight_status', 'ready_for_simulation', 'warnings_allowed', 'warning_count')},
                'approval_matches': approval.get('signature') == preflight_warning_signature(preflight.get('findings', [])),
                'approved_snapshot': approval.get('snapshot_id'), 'preflight_outdated': preflight.get('is_outdated')}
        print(json.dumps({'project': identifier, 'statuses': workflow.get('statuses'),
                          'execution': {key: execution.get(key) for key in ('state', 'step', 'message', 'completed', 'total', 'updated_at')},
                          'finding_codes': sorted({item.get('code', '') for item in execution.get('blocking_findings', [])}),
                          'preflight': detail}))
        break
else:
    print(json.dumps({'project_count': len(rows), 'scope': 'isolated release stack'}))
'''
result = subprocess.run([docker, 'exec', '-i', name, 'python', '-'], input=code,
                        text=True, encoding='utf-8', capture_output=True)
print(result.stdout)
if result.returncode:
    print(result.stderr)
    raise SystemExit(result.returncode)
