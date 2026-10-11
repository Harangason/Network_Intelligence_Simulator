"""Recompute current capacity/preflight after the approved canonical repair."""
import json
from pathlib import Path
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
verified = json.loads((HERE / 'canonical-reconciliation-verification.json').read_text(encoding='utf-8'))
assert verified['status'] == 'APPLIED_AND_VERIFIED'
project = verified['project']
def call(path, method='GET'):
    request = Request('http://127.0.0.1:13500/api/engineering/' + path, method=method,
        headers={'X-Project-ID': project, 'Content-Type': 'application/json'}, data=b'{}' if method == 'POST' else None)
    with urlopen(request, timeout=300) as response:
        return json.load(response)
capacity = call('capacity/calculate', 'POST')
(HERE / 'reconciled-capacity.json').write_text(json.dumps(capacity), encoding='utf-8')
preflight = call('preflight', 'POST')
(HERE / 'reconciled-preflight.json').write_text(json.dumps(preflight), encoding='utf-8')
latest = call('preflight')
assert latest['id'] == preflight.get('snapshot_id', preflight.get('id')) and not latest['is_outdated']
workflow = call('workflow?view=summary')
report = {'project': project, 'capacity_status': capacity.get('status'), 'capacity_snapshot': capacity.get('id'),
    'preflight_snapshot': latest['id'], 'preflight_status': latest['results'].get('preflight_status'),
    'ready_for_simulation': latest['results'].get('ready_for_simulation'), 'current': True,
    'findings': preflight.get('findings', []), 'workflow_statuses': workflow.get('statuses'),
    'scope': 'Current repaired product model; ordinary capacity/preflight, no invented warning acceptance or replacement of historical simulation evidence.'}
(HERE / 'reconciled-assessments.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
assert report['capacity_status'] == 'COMPLETED', report['capacity_status']
assert report['ready_for_simulation'] is True, report
assert not any(item.get('severity') == 'ERROR' for item in report['findings']), report['findings']
print(json.dumps({key: report[key] for key in ['capacity_status', 'preflight_status', 'ready_for_simulation']}))
