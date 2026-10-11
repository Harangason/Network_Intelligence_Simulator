import json
import re
from pathlib import Path

folder = Path(__file__).resolve().parent
root = folder.parents[2]
receipt_path = root / 'backend/test-output/release-gates/delivery-fe22602c08d5/264282c9a63a/receipt.json'
receipt = json.loads(receipt_path.read_text())
phases = ['storage-tests', 'typecheck', 'frontend-tests', 'backend-tests', 'production-build', 'browser-e2e', 'small-http', 'large-http']
checks = {row['name']: row['exit_code'] for row in receipt['checks']}
active = next((phase for phase in phases if phase not in checks), 'deployment')
result = {'status': receipt['status'], 'checks': checks, 'active': active,
          'source_sha256': receipt['initial_source_sha256'], 'image_id': receipt.get('image_id'),
          'error': receipt.get('error')}
for phase in (active, 'backend-tests', 'frontend-tests', 'browser-e2e'):
    path = receipt_path.parent / (phase + '.log')
    if not path.exists():
        continue
    with path.open('rb') as stream:
        stream.seek(max(0, path.stat().st_size - 12000))
        tail = stream.read().decode('utf-8', errors='replace')
    percentages = re.findall(r'\[\s*(\d+)%\]', tail)
    browser = re.findall(r'\[(\d+)/(\d+)\]', tail)
    listed = re.findall(r'\bok\s+(\d+)\s+e2e', tail)
    summaries = [line.strip()[:220] for line in tail.splitlines() if re.search(r'\d+ (passed|failed)|# (tests|pass|fail) |ERROR|Timeout|[1-9]\d*\) \[', line)]
    result[phase] = {'bytes': path.stat().st_size, 'pytest_percent': percentages[-1] if percentages else None,
                     'browser_case': browser[-1] if browser else [listed[-1], '104'] if listed else None, 'summary': summaries[-3:]}
work_path = folder / 'workload.json'
work = json.loads(work_path.read_text())
work['active_release_receipt'] = str(receipt_path)
work_path.write_text(json.dumps(work, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=True))
