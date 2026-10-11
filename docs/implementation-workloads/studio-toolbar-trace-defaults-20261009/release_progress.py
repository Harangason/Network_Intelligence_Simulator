"""Read this task's current release logs without touching its processes."""
import json
import re
from pathlib import Path

workload = json.loads((Path(__file__).parent / 'workload.json').read_text(encoding='utf-8-sig'))
p = Path(workload['release_recovery']['active_receipt']).parent
r = json.loads((p / 'receipt.json').read_text())
data = {'status': r['status'], 'checks': r['checks'], 'error': r.get('error')}
stages = [name for name in ('backend-tests', 'production-build', 'browser-e2e', 'small-http', 'large-http')
          if (p / (name + '.log')).exists()]
for name in stages[-1:]:
    log = p / (name + '.log')
    value = log.read_text(encoding='utf-8', errors='replace')
    lines = value.splitlines()
    percents = re.findall(r'\[\s*(\d+)%\]', value)
    tail = []
    for line in lines[-3:]:
        if len(line) > 1500:
            try:
                report = json.loads(line)
                tail.append({key: report.get(key) for key in ('phase', 'project', 'job_id', 'statuses') if key in report})
            except ValueError:
                tail.append(line[:500] + ' [truncated]')
        else:
            tail.append(line)
    data[name] = {'progress_percent': percents[-1] if percents else None,
                  'tail': tail, 'bytes': log.stat().st_size}
    if name == 'backend-tests':
        progress = re.findall(r'(?m)^[.FEsxXu]+(?:\s+\[\s*\d+%\])?$', value)
        data[name]['failure_markers'] = sum(row.count('F') + row.count('E') for row in progress)
print(json.dumps(data, ensure_ascii=True))
