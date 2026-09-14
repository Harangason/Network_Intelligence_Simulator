"""Inspect and assess the current project's repair plan without applying a strategy."""
import json
from pathlib import Path
from urllib.request import Request, urlopen

project = 'network-project-20260910042736034-d11591d0'
base = 'http://127.0.0.1:15050/api/engineering/'
def request(path, body=None):
    with urlopen(Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                        headers={'X-Project-ID': project, 'Content-Type': 'application/json'}), timeout=600) as response:
        return json.load(response)

before = request('communication-resources')
plan = request('workflow/communication-repair/preview', {})
print(json.dumps({'stage': 'preview', 'groups': len(plan['groups']), 'options': sum(len(g['options']) for g in plan['groups'])}), flush=True)
reviewed = request('workflow/communication-repair/review', {'workload_id': plan['workload_id']})
while reviewed['agent_review']['status'] == 'REVIEWING':
    print(json.dumps({'stage': 'review', 'completed': len(reviewed['agent_review']['decisions'])}), flush=True)
    reviewed = request('workflow/communication-repair/review', {'workload_id': plan['workload_id']})
after = request('communication-resources')
assert before == after, 'Canonical communication resources changed during preview'
result = {'passed': reviewed['agent_review']['status'] in {'REVIEWED', 'NO_CANDIDATES'},
          'project_id': project, 'groups': len(plan['groups']), 'canonical_resources_unchanged': True,
          'workload_id': plan['workload_id'], 'review': reviewed['agent_review']}
Path('backend/runtime/specialist-project.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key: value for key, value in result.items() if key != 'review'}), flush=True)
assert result['passed'], reviewed['agent_review']
