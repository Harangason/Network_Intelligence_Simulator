"""Read-only progress for the active isolated large browser case."""
import json
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen

try:
    with urlopen('http://127.0.0.1:61612/api/engineering/projects', timeout=10) as response:
        projects = json.load(response)['items']
    candidates = [item for item in projects if str(item.get('project_id', item.get('id', ''))).startswith(('nis-e2e-large', 'astra-e2e-'))]
    selected = max(candidates, key=lambda item: parsedate_to_datetime(item['created_at']))
    project = selected.get('project_id', selected.get('id'))
    request = Request('http://127.0.0.1:61612/api/engineering/workflow?view=summary', headers={'X-Project-ID': project})
    with urlopen(request, timeout=10) as response:
        workflow = json.load(response)
    execution = workflow.get('context', {}).get('agent_execution', {})
    print(json.dumps({'isolated_project': project, 'statuses': workflow.get('statuses'), 'state': execution.get('state'), 'step': execution.get('step')}, ensure_ascii=False))
except OSError as error:
    print(json.dumps({'isolated_status_read': type(error).__name__}))
