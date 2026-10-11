import json
import zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

folder = Path(__file__).resolve().parent
trace = folder.parents[2] / 'backend/test-output/release-gates/studio-toolbar-full-slot/4faafc428761/browser/wizard-exact-confirmed-50--c2f3c-gh-real-wizard-review-large/trace.zip'
with zipfile.ZipFile(trace) as archive:
    captured = []
    counts = Counter()
    for name in archive.namelist():
        if not name.endswith('.network'):
            continue
        for line in archive.read(name).splitlines():
            item = json.loads(line).get('snapshot', {})
            request, response = item.get('request', {}), item.get('response', {})
            path = urlsplit(request.get('url', '')).path
            if not path.startswith('/api/'):
                continue
            resource = response.get('content', {}).get('_sha1') or response.get('content', {}).get('_file')
            if resource:
                resource = resource if resource.startswith('resources/') else 'resources/' + resource
            counts[path] += 1
            captured.append({'path': path, 'url': request.get('url'), 'method': request.get('method'),
                             'resource': resource, 'status': response.get('status'),
                             'size': archive.getinfo(resource).file_size if resource in archive.namelist() else 0,
                             'time': item.get('startedDateTime'), 'duration_ms': item.get('time')})
    (folder / 'large-trace-index.json').write_text(json.dumps(captured, indent=2))
    print(json.dumps({'paths': counts, 'last_requests': captured[-15:]}, indent=2))
    for item in reversed(captured):
        if item['path'] == '/api/engineering/workflow' and 'view=summary' not in item['url'] and item['size'] > 50000:
            (folder / 'large-workflow-captured.json').write_bytes(archive.read(item['resource']))
            state = json.loads(archive.read(item['resource']))
            print(json.dumps({'workflow_keys': list(state), 'context_keys': list(state.get('context', {})),
                              'topology_keys': list(state.get('topology', {}))}))
            break
    for path in ['/api/engineering/agent/conversation', '/api/engineering/messages', '/api/engineering/routing', '/api/engineering/hardware-interfaces', '/api/engineering/workflow/topology', '/api/engineering/workflow/parameters', '/api/engineering/hardware-nodes', '/api/engineering/interfaces', '/api/engineering/signals', '/api/engineering/functions']:
        item = next(item for item in reversed(captured) if item['path'] == path and item['method'] == 'GET' and item['size'])
        state = json.loads(archive.read(item['resource']))
        target = folder / ('large-' + path.split('/')[-1] + '-captured.json')
        target.write_text(json.dumps(state), encoding='utf-8')
        print(json.dumps({'path': path, 'keys': list(state), 'size': item['size']}))
        if 'items' in state:
            merged = {}
            for entry in captured:
                if entry['path'] == path and entry['method'] == 'GET' and entry['size']:
                    data = json.loads(archive.read(entry['resource']))
                    merged.update({str(row['id']): row for row in data.get('items', [])})
            (folder / ('large-' + path.split('/')[-1] + '-objects.json')).write_text(json.dumps(list(merged.values())), encoding='utf-8')
            print('merged', path, len(merged))
    print(json.dumps({'slow_requests': [item for item in captured if item.get('duration_ms', 0) > 10000]}, indent=2))
