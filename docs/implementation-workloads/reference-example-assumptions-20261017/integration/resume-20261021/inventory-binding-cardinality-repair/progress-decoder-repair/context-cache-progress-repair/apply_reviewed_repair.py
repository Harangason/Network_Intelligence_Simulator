"""Apply reviewed draft only to its exact before revision, after RED and guard."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = Path.cwd()
work = json.loads((HERE / 'workload.json').read_text(encoding='utf-8'))
source = ROOT / 'backend/nis/agent/orchestration/local_reasoner.py'
assert hashlib.sha256(source.read_bytes()).hexdigest() == work['revision_before'][str(source.relative_to(ROOT)).replace('\\', '/')]
red = HERE / 'red.xml'
assert 'failures="3"' in red.read_text(encoding='utf-8')
test_file = ROOT / 'backend/tests/test_reference_reasoner.py'
work['revision_before']['backend/tests/test_reference_reasoner.py'] = hashlib.sha256(test_file.read_bytes()).hexdigest()
work['repair']['evidence'].append({'path': str(red), 'sha256': hashlib.sha256(red.read_bytes()).hexdigest()})
(HERE / 'workload.json').write_text(json.dumps(work, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
guard = subprocess.run([sys.executable, '-X', 'utf8', 'F:/CodexOrdner/skills/lokaler-implementierungs-agent/scripts/implementation_guard.py',
    'before-apply', '--workload', str(HERE / 'workload.json')], check=True, capture_output=True, text=True)
(HERE / 'before-apply-guard.json').write_text(guard.stdout, encoding='utf-8')
draft = HERE / 'planned-local_reasoner-v2.py'
planned = draft.read_text(encoding='utf-8')
# Keep the exact wire response, including whitespace, on corrective retry too.
planned = planned.replace("payload['messages'] = [*messages, {'role': 'assistant', 'content': raw},",
                          "payload['messages'] = [*messages, {'role': 'assistant', 'content': native_content},")
source.write_text(planned, encoding='utf-8', newline='\n')
print('Applied reviewed append-only context/progress repair after three RED cases and passing revision/campaign guard.')
