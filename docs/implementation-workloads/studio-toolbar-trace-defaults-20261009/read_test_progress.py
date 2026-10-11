"""Read already captured Playwright workflow responses; no server requests."""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('backend/test-output/release-gates/studio-toolbar-full-retry/32cb85dc18ff/browser/.playwright-artifacts-0/traces')
segments = list(root.glob('*.network'))
if not segments:
    print('No captured trace segments remain; consult the release receipt and browser log.')
    raise SystemExit(0)
latest = max(segments, key=lambda path: path.stat().st_mtime)
workflow = None
for line in latest.open(encoding='utf-8'):
    try:
        snapshot = json.loads(line).get('snapshot', {})
    except ValueError:
        continue
    if urlsplit(snapshot.get('request', {}).get('url', '')).path != '/api/engineering/workflow':
        continue
    resource = snapshot.get('response', {}).get('content', {}).get('_file')
    if resource and (root / resource).is_file():
        workflow = json.loads((root / resource).read_text(encoding='utf-8'))
if workflow:
    execution = workflow.get('context', {}).get('agent_execution', {})
    print(json.dumps({'project': workflow.get('project_id'), 'statuses': workflow.get('statuses'),
                      'execution': {key: execution.get(key) for key in ['state', 'step', 'message', 'updated_at']}},
                     ensure_ascii=False))
else:
    print('No workflow response in the latest trace segment')
