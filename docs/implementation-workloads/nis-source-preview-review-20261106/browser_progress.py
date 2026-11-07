"""Read the disposable release stack's current large-case workflow, without mutations."""
import json
from pathlib import Path
import urllib.request

base = 'http://127.0.0.1:57439'
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(path, project=None):
    request = urllib.request.Request(base + path, headers={'X-Project-ID': project} if project else {})
    with opener.open(request, timeout=10) as response:
        return json.load(response)


projects = get('/api/engineering/projects')
assert projects['next_offset'] is None
http_project = None
http_log = Path('backend/test-output/release-gates/delivery-6127991a9e47/4310b821dab9/large-http.log')
if http_log.exists():
    for line in http_log.read_text(encoding='utf-8', errors='replace').splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if item.get('phase') == 'start':
            http_project = item['project']
result = []
for project in projects['items']:
    pid = project['project_id']
    if 'nis-e2e-large-' not in pid and 'nis-e2e-large-return-' not in pid and not (http_project and pid.endswith(http_project)):
        continue
    workflow = get('/api/engineering/workflow?view=summary', pid)
    execution = workflow.get('context', {}).get('agent_execution') or {}
    result.append({'project': pid, 'statuses': workflow.get('statuses'), 'versions': workflow.get('versions'),
                   'execution': {key: execution.get(key) for key in ['state', 'step', 'updated_at', 'last_error', 'message', 'blocking_findings']},
                   'latest_analyses': workflow.get('latest_analyses')})
result.sort(key=lambda item: item['execution'].get('updated_at') or '', reverse=True)
print(json.dumps({'large_case_project_count': len(result), 'most_recently_updated': result[:1]}, ensure_ascii=True))
