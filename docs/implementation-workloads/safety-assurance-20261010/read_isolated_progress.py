"""Read-only progress from the current gate's labelled disposable app."""
import argparse
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--receipt', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[3]
receipt = json.loads(args.receipt.read_text(encoding='utf-8-sig'))
name = receipt['containers']['app']
assert name.startswith('nis-e2e-app-') and name != 'NetworkIS'
docker = json.loads((root/'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
app = json.loads(subprocess.check_output([docker, 'inspect', name], text=True))[0]
assert app['Config']['Labels'].get('networkis.test') == 'disposable'
code = '''
import json
from urllib.request import Request, urlopen
def get(path, project=None):
    request = Request('http://127.0.0.1:13500/api/engineering/'+path,
        headers={'X-Project-ID':project} if project else {})
    with urlopen(request, timeout=10) as response:
        return json.load(response)
projects = get('projects?offset=0')
rows = projects.get('items', []) if isinstance(projects, dict) else projects
matches = 0
for row in rows:
    identifier = row.get('project_id') or row.get('id')
    if identifier and ('nis-e2e-large' in str(identifier) or str(identifier).startswith('astra-e2e-')):
        workflow = get('workflow?view=summary', identifier)
        execution = workflow.get('context', {}).get('agent_execution') or {}
        if execution.get('state') == 'COMPLETED':
            continue
        print(json.dumps({'project':identifier, 'statuses':workflow.get('statuses'),
            'execution':{key:execution.get(key) for key in ('state','step','message','completed','total','updated_at')}}))
        matches += 1
        if matches == 1:
            break
if not matches:
    print(json.dumps({'project_count':len(rows), 'scope':'isolated release stack'}))
'''
result = subprocess.run([docker, 'exec', '-i', name, 'python', '-'], input=code,
    text=True, encoding='utf-8', capture_output=True)
print(result.stdout)
if result.returncode:
    print(result.stderr)
    raise SystemExit(result.returncode)
