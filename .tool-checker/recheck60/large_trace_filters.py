"""S39 synthetic 100501-event import: bounded windows and all named search dimensions."""
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
receipt = json.loads((ROOT / 'backend/test-output/industry60-completion/d8a5a6840084/receipt.json').read_text())
base = receipt['base_url']
assert base == 'http://127.0.0.1:56335' and receipt['status'] == 'PREPARED'
project = 'nis-e2e-industry60-large-filters'
folder = ROOT / '.tool-checker/evidence/industry60-completion/S39'
folder.mkdir(parents=True, exist_ok=True)
source = folder / 'source.jsonl'
markers = {'source': 'SRC_NEEDLE', 'destination': 'DST_NEEDLE', 'source_logical_address': '0x0042',
           'network_id': 'NET_NEEDLE', 'technology': 'TECH_NEEDLE', 'message_id': 'MSG_NEEDLE',
           'signal': 'SIGNAL_NEEDLE', 'function_ref': 'FUNCTION_NEEDLE', 'route_ref': 'ROUTE_NEEDLE',
           'faults': ['FAULT_NEEDLE'], 'severity': 'SEVERITY_NEEDLE'}
with source.open('w', encoding='utf8') as stream:
    for i in range(100501):
        event = {'time_s': i / 1000, 'time_basis': 'relative', 'sequence': i, 'technology': 'CAN_FD',
                 'source': 'src', 'destination': 'dst', 'network_id': 'net', 'message_id': 'Message'}
        if i == 50000:
            event.update(markers)
        stream.write(json.dumps(event) + '\n')
headers = {'X-Project-ID': project, 'Content-Type': 'application/octet-stream'}
def request(path, data=None):
    with urllib.request.urlopen(urllib.request.Request(base + path, data=data, headers=headers), timeout=120) as response:
        return json.load(response)
start = time.monotonic()
imported = request('/api/trace-import?filename=large-filter-fixture.jsonl', source.read_bytes())
assert imported['total_events'] == 100501 and len(imported['events']) <= 2000 and imported['next_cursor']
session = imported['session_id']
results = {'import': {'seconds': time.monotonic() - start, 'total': imported['total_events'], 'window': len(imported['events'])}}
for name, value in markers.items():
    query = value[0] if isinstance(value, list) else value
    cursor, found, pages = 0, [], []
    for _ in range(12):
        result = request('/api/trace-import/' + session + '?' + urllib.parse.urlencode({'q': query, 'limit': 10, 'cursor': cursor}))
        found.extend(result['events'])
        pages.append({'scanned': result['scanned'], 'count': result['count'], 'next_cursor': result['next_cursor']})
        if result['next_cursor'] is None:
            break
        assert result['next_cursor'] > cursor
        cursor = result['next_cursor']
    assert result['next_cursor'] is None and len(found) == 1 and found[0]['sequence'] == 50000, (name, result)
    results[name] = {'events': found, 'pages': pages}
first = request('/api/trace-import/' + session + '?start_s=99&end_s=100&limit=500')
second = request('/api/trace-import/' + session + '?start_s=99&end_s=100&limit=500&cursor=' + str(first['next_cursor']))
third = request('/api/trace-import/' + session + '?start_s=99&end_s=100&limit=500&cursor=' + str(second['next_cursor']))
assert [len(page['events']) for page in (first, second, third)] == [500, 500, 1]
assert [event['sequence'] for page in (first, second, third) for event in page['events']] == list(range(99000, 100001))
results['time_pages'] = [{'count': len(page['events']), 'first': page['events'][0]['sequence'],
                        'last': page['events'][-1]['sequence'], 'next_cursor': page['next_cursor']} for page in (first, second, third)]
(folder / 'http-filter-results.json').write_text(json.dumps({'project': project, 'session': session, 'image': receipt['image_id'],
    'origin': 'Synthetic search/window fixture; free-text q tests, not typed-field filtering or downsampling evidence', 'results': results}, indent=2), encoding='utf8')
print(json.dumps({'session': session, 'project': project, 'results': list(results)}), flush=True)
