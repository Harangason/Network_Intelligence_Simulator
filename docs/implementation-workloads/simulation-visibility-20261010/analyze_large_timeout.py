"""Read the actual failed trace; retain timings without modifying tests or models."""
import json
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
trace = ROOT / 'backend/test-output/release-gates/delivery-f87cc6f48f53/ba52fd62fb41/browser/wizard-exact-confirmed-50--c2f3c-gh-real-wizard-review-large/trace.zip'
with zipfile.ZipFile(trace) as archive:
    records = [json.loads(line) for line in archive.open('test.trace')]
    selected = {}
    for record in records:
        for attachment in record.get('attachments', []):
            name = attachment['name']
            if name in ('write-request-timings', 'workflow-progress-boundaries', 'workflow-page-failures'):
                selected[name] = json.loads(archive.read(attachment['file']))
    (HERE / 'large-timeout-attachments.json').write_text(json.dumps(selected, indent=2), encoding='utf-8')
    before = {row['callId']: row for row in records if row['type'] == 'before'}
    calls = []
    for row in records:
        if row['type'] != 'after' or row['callId'] not in before:
            continue
        start = before[row['callId']]
        duration = row['endTime'] - start['startTime']
        if duration > 5000:
            calls.append({'duration_ms': round(duration), 'start_ms': round(start['startTime']),
                'title': start.get('title'), 'class': start.get('class'), 'method': start.get('method'),
                'url': start.get('params', {}).get('url'), 'error': row.get('error')})
    (HERE / 'large-timeout-slow-calls.json').write_text(json.dumps(calls, indent=2), encoding='utf-8')
print(json.dumps({'attachments': list(selected), 'slow_calls': sorted(calls, key=lambda row: row['duration_ms'], reverse=True)[:15]}, indent=2))
