"""Read the real failed Playwright transport and check the same isolated read endpoint."""
import json
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen
from datetime import datetime, timezone

here = Path(__file__).resolve().parent
root = here.parents[2]
folder = root / 'backend/test-output/release-gates/delivery-resumed-studio-20261011/63ad5d2d7fa8/browser/wizard-exact-confirmed-50--8c6d1-rn-review-only-large-return'
rows = []
with zipfile.ZipFile(folder / 'trace.zip') as archive:
    for name in archive.namelist():
        if not name.endswith('.trace'):
            continue
        for line in archive.read(name).decode('utf-8').splitlines():
            item = json.loads(line)
            if item.get('type') in {'before', 'after'}:
                rows.append(item)
failed = [row for row in rows if row.get('error')]
calls = {row['callId']: row for row in rows if row.get('type') == 'before'}
details = [{'before': calls.get(row.get('callId')), 'after': row} for row in failed]
project = 'nis-e2e-large-return-routing-5e292137-f956-46af-ae8e-df6456f8d91e'
checks = []
for _ in range(3):
    request = Request('http://127.0.0.1:56237/api/engineering/workflow/parameters', headers={'X-Project-ID': project})
    with urlopen(request, timeout=60) as response:
        body = json.load(response)
        checks.append({'status': response.status, 'project_id': body.get('project_id'), 'parameter_keys': sorted(body.get('parameters', {}))})
evidence = {'captured_at': datetime.now(timezone.utc).isoformat(), 'failed_calls': details,
    'same_isolated_endpoint_reads': checks, 'recent_transport_events': rows[-12:]}
(here / 'transport-diagnosis.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
print(json.dumps({'failed_calls': details, 'counterchecks': [{'status': item['status'], 'project_id': item['project_id']} for item in checks]}))
