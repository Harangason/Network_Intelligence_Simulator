"""Reject only this task's unapplied detached plan; canonical objects remain unchanged."""
import json
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.request import build_opener, HTTPCookieProcessor, Request

HERE = Path(__file__).resolve().parent
old = json.loads((HERE / 'before-encoding-repair-prepared-reconciliation-proposal.json').read_text(encoding='utf-8'))['data']
opener = build_opener(HTTPCookieProcessor(CookieJar()))
csrf = None
def call(path, method='GET', data=None):
    headers = {'X-Project-ID': '20261009072206008-4bb505f1', 'Content-Type': 'application/json'}
    if method == 'POST':
        headers.update({'X-Review-CSRF': csrf, 'X-Human-Review': 'confirmed', 'Origin': 'http://127.0.0.1:13500'})
    with opener.open(Request('http://127.0.0.1:13500/api/engineering/agent/' + path, method=method,
        headers=headers, data=json.dumps(data).encode() if data is not None else None), timeout=180) as response:
        return json.load(response)
proposal = call('proposals/' + old['proposal_id'])
assert proposal['success'] and proposal['data']['status'] in ('VALIDATED', 'REJECTED')
if proposal['data']['status'] != 'REJECTED':
    csrf = call('review-session')['csrf_token']
    proposal = call('proposals/' + old['proposal_id'] + '/review', 'POST',
        {'revision': proposal['data']['revision'], 'decision': 'reject'})
assert proposal['success'] and proposal['data']['status'] == 'REJECTED'
(HERE / 'rejected-encoding-plan.json').write_text(json.dumps(proposal, ensure_ascii=True), encoding='utf-8')
print(json.dumps({'status': 'REJECTED', 'proposal_id': old['proposal_id'], 'canonical_object_changes': 0}))
