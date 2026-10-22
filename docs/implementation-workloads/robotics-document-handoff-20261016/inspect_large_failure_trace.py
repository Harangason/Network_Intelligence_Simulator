"""Read retained Playwright evidence without touching the active gate."""
from collections import deque
from pathlib import Path
import json
import zipfile

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
path = ROOT / 'backend/test-output/release-gates/robotics-document-handoff-20261016/911347665bea/browser/wizard-exact-confirmed-50--c2f3c-gh-real-wizard-review-large/trace.zip'
result = {'scope': 'Retained trace read only', 'entries': [], 'tails': {}}
with zipfile.ZipFile(path) as archive:
    for entry in archive.infolist():
        if not entry.filename.endswith(('.trace', '.network')):
            continue
        result['entries'].append({'name': entry.filename, 'bytes': entry.file_size})
        tail = deque(maxlen=28)
        with archive.open(entry) as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                except (ValueError, UnicodeError):
                    continue
                if event.get('type') in {'before', 'after', 'error'}:
                    item = {key: event[key] for key in ('type', 'callId', 'apiName', 'class', 'method', 'startTime', 'endTime', 'error') if key in event}
                    params = event.get('params') or {}
                    item['params'] = {key: params[key] for key in ('url', 'method', 'timeout', 'selector') if key in params}
                    tail.append(item)
        result['tails'][entry.filename] = list(tail)
(OUT / 'large-failure-trace-summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=True, indent=2))
