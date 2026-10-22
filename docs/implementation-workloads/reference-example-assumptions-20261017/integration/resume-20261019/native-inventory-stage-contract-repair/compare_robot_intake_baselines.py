"""Read-only source-baseline analysis; never changes a checker or approves a model."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[5]
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration.project_intake import document_source_contexts, document_fact_identity

expected = json.loads((ROOT / '.tool-checker/runs/20261017_src_original_documents_simulation/robotics/expected-source-manifest.json').read_text(encoding='utf-8-sig'))
old_path = Path(expected['prior_adopted_facts']['path'])
raw = old_path.read_bytes()
assert hashlib.sha256(raw).hexdigest() == expected['prior_adopted_facts']['sha256']
state = json.loads((OUT.parents[1] / 'native-scoped-robot/state.json').read_text(encoding='utf8'))
source = Path(state['source']).read_bytes().decode('utf8')
assert hashlib.sha256(source.encode()).hexdigest() == state['original_sha256']
_, contexts = document_source_contexts(source)
context_map = {' / '.join(context): context for context in contexts}
old = [dict(name=row['name'], kind=row['kind'], role=row['role'], quantity=row['quantity'],
    source_quote=row['quote'], source_context=context_map[row['context']]) for row in json.loads(raw)]
response = Path(state['document_response']).read_bytes()
assert hashlib.sha256(response).hexdigest() == state['reviewed_document_response_sha256']
current = json.loads(response)['interpretation']['components']
before = {document_fact_identity(row): row for row in old}
after = {document_fact_identity(row): row for row in current}
missing = [row for key, row in before.items() if key not in after]
added = [row for key, row in after.items() if key not in before]
report = {'at_utc': datetime.now(timezone.utc).isoformat(), 'scope': __doc__,
    'source_sha256': state['original_sha256'], 'historical_fact_count': len(old),
    'actual_native_intake_fact_count': len(current),
    'actual_intake_response_sha256': hashlib.sha256(response).hexdigest(),
    'historical_only': missing, 'actual_only': added,
    'requirements': len(expected['requirements']), 'actual_counts': dict(Counter(row['kind'] for row in current)),
    'accepted_model_available': False, 'checker_or_model_edits': False, 'simulation_pass': False}
(OUT / 'robot-historical-vs-actual-intake-readonly.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
print(json.dumps({key: value for key, value in report.items() if key not in ('historical_only', 'actual_only', 'scope')}, ensure_ascii=False))
print(json.dumps({name: [{key: row.get(key) for key in ('name', 'kind', 'role', 'source_context')} for row in values]
    for name, values in (('historical_only', missing), ('actual_only', added))}, ensure_ascii=False))
