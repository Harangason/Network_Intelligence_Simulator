"""Recompute ordinary capacity and preflight after the authorized model correction."""
import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

folder = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--saved', action='store_true', help='Report the completed refresh without running it again.')
args = parser.parse_args()
alignment = json.loads((folder / 'existing-project-alignment-verification.json').read_text())
assert alignment['status'] == 'APPLIED_AND_VERIFIED'
project = alignment['project']
base = 'http://127.0.0.1:13500/api/engineering/'
headers = {'X-Project-ID': project, 'Content-Type': 'application/json'}

def call(path, method='GET'):
    with urlopen(Request(base + path, headers=headers, method=method,
                         data=b'{}' if method == 'POST' else None), timeout=300) as response:
        return json.load(response)

if args.saved:
    capacity = json.loads((folder / 'existing-project-refreshed-capacity.json').read_text())
    preflight = json.loads((folder / 'existing-project-refreshed-preflight.json').read_text())
else:
    capacity = call('capacity/calculate', 'POST')
    (folder / 'existing-project-refreshed-capacity.json').write_text(json.dumps(capacity), encoding='utf-8')
    preflight = call('preflight', 'POST')
    (folder / 'existing-project-refreshed-preflight.json').write_text(json.dumps(preflight), encoding='utf-8')
latest = call('preflight')
assert latest['id'] == preflight.get('snapshot_id', preflight.get('id')) and not latest['is_outdated']
results = latest['results']
workflow = call('workflow?view=summary')
report = {'project': project, 'capacity_snapshot': capacity.get('id'), 'capacity_status': capacity.get('status'),
          'preflight_snapshot': latest['id'], 'preflight_status': results.get('preflight_status'),
          'ready_for_simulation': results.get('ready_for_simulation'), 'preflight_is_current': True,
          'findings': [{'code': row.get('code'), 'severity': row.get('severity'), 'message': row.get('message')}
                       for row in preflight.get('findings', [])], 'workflow_statuses': workflow.get('statuses'),
          'scope': 'Ordinary recalculation of the corrected model; no warning approval or new simulation run.'}
(folder / 'existing-project-refreshed-assessments.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({key: report[key] for key in ('capacity_status', 'preflight_status', 'ready_for_simulation', 'workflow_statuses')}))
