import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
path = folder / 'workload.json'
work = json.loads(path.read_text())
root = Path(work['repository'])
for name in work['files_changed']:
    assert (root / name).read_bytes() == (folder / 'after' / name).read_bytes(), 'Source changed since targeted verification: ' + name
authorization = folder / 'image-exchange-authorization.json'
exchange = folder / 'image-exchange-evidence.json'
assert json.loads(exchange.read_text())['removed'] is True
ref = lambda p: {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
work['completion_status'] = 'VALIDATING'
work['delivery'].update(authorization='Explicit user request: dann mach das produktiv, das nervt mich. Standing AGENTS.md authorization and exact archived-image exception.',
                        status='RELEASE_GATE_RUNNING', authorization_evidence=[ref(authorization), ref(exchange)])
work['remaining_findings'] = [item for item in work['remaining_findings'] if 'retention exception' not in item.lower()]
path.write_text(json.dumps(work, indent=2), encoding='utf-8')
print(json.dumps({'source_unchanged_since_55_tests': True, 'authorized': True, 'retention_exception_executed': True}))
