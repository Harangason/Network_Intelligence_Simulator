"""Extract bounded request evidence from the actual failed Playwright trace."""
import collections
import hashlib
import json
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
trace = ROOT / 'backend/test-output/release-gates/delivery-0365fbec85ea/8d4503be8753/browser/equipment-inventory-descri-99758-eserves-its-draft-on-reload/trace.zip'
counts, reads = collections.Counter(), []
with zipfile.ZipFile(trace) as archive:
    for name in archive.namelist():
        if not name.endswith('.network'):
            continue
        for line in archive.read(name).decode().splitlines():
            row = json.loads(line).get('snapshot', {})
            request, response = row.get('request', {}), row.get('response', {})
            url = request.get('url', '')
            if '/generation-experience/retrieve' in url:
                body = request.get('postData', {})
                contents = archive.read(body['_file']).decode() if body.get('_file') else body.get('text', '')
                counts[contents] += 1
            if '/workflow?view=summary' in url:
                reads.append({'duration_ms': row.get('time'), 'status': response.get('status'),
                              'network_error': response.get('_failureText')})
result = {'trace_path': str(trace), 'trace_sha256': hashlib.sha256(trace.read_bytes()).hexdigest(),
          'experience_requests': sum(counts.values()), 'distinct_payloads': len(counts),
          'payload_counts': dict(counts), 'workflow_read_results': reads,
          'typing_assertions': 'Passed before reload; exact reload assertion failed with restore-service error',
          'repair': 'Stable semantic retrieval scope with cancellable 250 ms debounce; no timeout or assertion relaxation',
          'targeted_typecheck': {'command': 'node node_modules/typescript/bin/tsc --noEmit --incremental false',
                                 'exit_code': 0, 'execution_session': 57722},
          'full_gate_status': 'FAIL; partial browser run stopped for repair; no production deployment'}
(HERE / 'query-storm-evidence.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(result['experience_requests'], 'requests;', result['distinct_payloads'], 'unique payload')
