"""Extract an actual failed-test HTTP response from the retained trace."""
from pathlib import Path
import json
import zipfile

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
path = ROOT / 'backend/test-output/release-gates/robotics-document-handoff-20261016/911347665bea/browser/wizard-exact-confirmed-50--c2f3c-gh-real-wizard-review-large/trace.zip'
with zipfile.ZipFile(path) as archive:
    last = None
    with archive.open('0-trace.network') as stream:
        for line in stream:
            event = json.loads(line)
            snapshot = event.get('snapshot', {})
            if '/api/engineering/workflow?view=summary' in snapshot.get('request', {}).get('url', ''):
                last = snapshot
    assert last
    content = last['response']['content']
    key = content.get('_file') or ('resources/' + content['_sha1'])
    body = json.loads(archive.read(key))
(OUT / 'large-timeout-last-workflow.json').write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding='utf-8')
data = body.get('data', body)
print(json.dumps({'keys': list(data), 'statuses': data.get('statuses'), 'agent_execution': data.get('context', {}).get('agent_execution'),
                  'request': last['request']['url'], 'response_status': last['response']['status']}, ensure_ascii=True, indent=2))
