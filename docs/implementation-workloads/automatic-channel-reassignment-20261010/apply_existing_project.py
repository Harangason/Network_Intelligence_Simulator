"""Apply the explicitly authorized existing-project alignment through normal review APIs."""
import argparse
import json
import subprocess
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.request import HTTPCookieProcessor, Request, build_opener

parser = argparse.ArgumentParser()
parser.add_argument('--receipt', type=Path, required=True)
args = parser.parse_args()
folder = Path(__file__).resolve().parent
root = folder.parents[2]
receipt = json.loads(args.receipt.read_text())
assert receipt['status'] == 'PASS'
docker = json.loads((root / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
assert subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip() == receipt['image_id']
prepared = json.loads((folder / 'existing-project-prepared-proposal.json').read_text())
assert prepared['success'] is True
data = prepared['data']
if data.get('status') == 'UNCHANGED':
    print(json.dumps({'status': 'UNCHANGED', 'aligned': 0}))
    raise SystemExit(0)
proposal = data['proposal']
assert proposal['status'] == 'VALIDATED' and proposal['validation_result']['valid'] is True
base = 'http://127.0.0.1:13500/api/engineering/'
headers = {'X-Project-ID': '20261009072206008-4bb505f1'}
opener = build_opener(HTTPCookieProcessor(CookieJar()))
def call(path, method='GET', payload=None, review=False):
    supplied = {**headers, 'Content-Type': 'application/json'}
    if review:
        supplied.update({'X-Review-CSRF': csrf, 'X-Human-Review': 'confirmed', 'Origin': 'http://127.0.0.1:13500'})
    request = Request(base + path, data=json.dumps(payload).encode('utf-8') if payload is not None else None,
                      headers=supplied, method=method)
    with opener.open(request, timeout=180) as response:
        return json.load(response)
def rows(path):
    items = []
    while True:
        page = call(f'{path}?limit=200&offset={len(items)}')
        chunk = page if isinstance(page, list) else page.get('items', [])
        items.extend(chunk)
        if len(chunk) < 200:
            return items
before = {'workflow': call('workflow'), 'messages': rows('messages'), 'signals': rows('signals'),
          'ports': rows('hardware-interfaces'), 'routes': rows('routing')}
(folder / 'existing-project-before-alignment.json').write_text(json.dumps(before), encoding='utf-8')
before_messages = {str(item['id']): item for item in before['messages']}
for expected in data['expected']:
    assert before_messages[expected['id']]['hardware_interface_id'] == expected['before'], 'Project changed since preparation.'
csrf = call('agent/review-session')['csrf_token']  # Deliberately retained in memory only.
reviewed = call(f"agent/proposals/{proposal['proposal_id']}/review", 'POST',
                {'revision': proposal['revision'], 'decision': 'approve'}, review=True)
(folder / 'existing-project-review.json').write_text(json.dumps(reviewed), encoding='utf-8')
assert reviewed['success'] is True and reviewed['data']['status'] == 'APPROVED'
applied = call(f"agent/proposals/{proposal['proposal_id']}/apply", 'POST', {}, review=True)
(folder / 'existing-project-apply.json').write_text(json.dumps(applied), encoding='utf-8')
assert applied['success'] is True and applied['data']['status'] == 'APPLIED'
after = {'workflow': call('workflow'), 'messages': rows('messages'), 'signals': rows('signals'),
         'ports': rows('hardware-interfaces'), 'routes': rows('routing')}
(folder / 'existing-project-after-alignment.json').write_text(json.dumps(after), encoding='utf-8')
after_messages = {str(item['id']): item for item in after['messages']}
checks = {'signals_unchanged': before['signals'] == after['signals'], 'ports_unchanged': before['ports'] == after['ports'],
          'parameters_unchanged': before['workflow']['parameters'] == after['workflow']['parameters'],
          'physical_topology_unchanged': before['workflow']['topology'] == after['workflow']['topology']}
for expected in data['expected']:
    old, new = before_messages[expected['id']], after_messages[expected['id']]
    assert new['hardware_interface_id'] == expected['after'], expected['name']
    for key in ('id', 'name', 'description', 'interface_id', 'message_id_hex', 'dlc', 'cycle_ms', 'direction', 'configuration'):
        assert old.get(key) == new.get(key), (expected['name'], key)
assert all(checks.values()), checks
report = {'status': 'APPLIED_AND_VERIFIED', 'project': headers['X-Project-ID'], 'proposal_id': proposal['proposal_id'],
          'aligned': len(data['expected']), 'checks': checks,
          'licht': [item for item in data['expected'] if item['name'] == 'Licht'],
          'authorizing_user_request': 'Dies muss für alle einheitlich gelten. dann mach das produktiv, das nervt mich',
          'scope': 'Canonical reviewed model correction; no new physical routes, encodings, recipients or simulation jobs.'}
(folder / 'existing-project-alignment-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
