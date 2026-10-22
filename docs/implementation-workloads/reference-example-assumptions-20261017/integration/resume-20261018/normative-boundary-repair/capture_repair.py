"""Record the scoped product repair and read-only original-source diagnosis."""
import difflib
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[5]
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration import project_intake as current

spec = importlib.util.spec_from_file_location('nis_normative_before', OUT / 'before/backend/nis/agent/orchestration/project_intake.py')
before = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = before
spec.loader.exec_module(before)

def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

source_path = Path('C:/Users/marti/PycharmProjects/Benchmark_Modelle/Fahrzeug komplett.txt')
raw = source_path.read_bytes()
assert hashlib.sha256(raw).hexdigest() == '86865975c689643d9b07ea73e21d68fa6f4a3a8770402ffb537dba2d7ecdf4d7'
source = raw.decode('utf-8')
diagnosis = {'original': ref(source_path), 'scope': 'Pure parser grouping comparison, no Qwen or model generation and no database access.'}
for name, owner in [('before', before), ('after', current)]:
    units = owner.document_component_sources(owner.document_source_references(source))
    diagnosis[name] = [unit for unit in units if 'ISO 24089 Software' in unit['text'] or 'R13 Bremsen' in unit['text']]
assert len(diagnosis['before']) == 1 and len(diagnosis['after']) == 2
assert all(not ('R13 Bremsen' in unit['text'] and 'ISO 24089 Software' in unit['text']) for unit in diagnosis['after'])
for unit in diagnosis['after']:
    if 'ISO 24089 Software' in unit['text']:
        assert unit['source_context'][-1].startswith('7.2 ')
        for literal in ['ISO 21434 Cybersecurity', 'ISO 24089 Software‑Updates', 'ISO 14229 Diagnose (UDS)', 'ISO 6469 HV‑Sicherheit']:
            assert literal in unit['text']
(OUT / 'original-source-grouping.json').write_text(json.dumps(diagnosis, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
files = ['backend/nis/agent/orchestration/project_intake.py', 'backend/tests/test_qwen_document_intake.py']
snapshots, changes = [], []
for relative in files:
    old, path = OUT / 'before' / relative, ROOT / relative
    after = OUT / 'after' / relative
    after.parent.mkdir(parents=True, exist_ok=True)
    after.write_bytes(path.read_bytes())
    snapshots.append({'file': relative, 'before': ref(old), 'after': ref(after)})
    changes.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(keepends=True), after.read_text(encoding='utf-8').splitlines(keepends=True), fromfile='before/' + relative, tofile='after/' + relative))
(OUT / 'changes.diff').write_text(''.join(changes), encoding='utf-8')
failure = OUT.parents[1] / 'native-joint-vehicle/document-intake-normative-coverage-failure.ax.txt'
workload = {
    'goal_id': 'nis-native-normative-subchapter-boundaries-20261018', 'repository': str(ROOT),
    'kind': 'repair', 'modify_code': True, 'allow_repair': True, 'status': 'VALIDATING',
    'authorization': 'Stelle die arbeiten fertig; general NIS parser repair and both unchanged original native workflows, followed by the full joint release.',
    'at_utc': datetime.now(timezone.utc).isoformat(), 'unresolved_decisions': [],
    'revision_before': {row['file']: row['before']['sha256'] for row in snapshots},
    'files_changed': files, 'snapshots': snapshots, 'diff': [ref(OUT / 'changes.diff')],
    'repair': {'owner': 'PROJECT_PRODUCT', 'finding_ids': ['NATIVE_NORMATIVE_SUBCHAPTER_CONTEXT_MERGE'],
               'first_failing_layer': 'document_component_sources full-source normative citation grouping',
               'root_cause': 'Adjacent requirement rows were grouped across distinct source contexts. Full-source aggregate then demanded a neighboring subchapter context for correctly scoped window results.',
               'reproduction': 'Full 16-section real local Qwen vehicle intake rejected ISO21434/24089/14229/6469. Pure CRLF regression reproduces per-window PASS followed by aggregate failure.',
               'affected_files': files, 'required_fix': 'Flush a citation group when literal source_context changes; keep source/context validation strict.',
               'acceptance_criteria': ['Complete original quotes preserved in their actual subchapters', 'Windowed results compose with full-source validation', 'Wrong-context and missing requirements still rejected'],
               'targeted_tests': ['backend/tests/test_qwen_document_intake.py', 'backend/tests/test_reference_design.py'],
               'weaken_assertions_to_pass': False,
               'evidence': [ref(failure), ref(OUT / 'original-source-grouping.json'), ref(OUT / 'red.xml'), ref(OUT / 'green.xml')]},
    'native_original_simulations': 'PENDING_NEW_IMAGE', 'full_release_gate': 'PENDING', 'production_delivery': 'PENDING',
}
(OUT / 'workload.json').write_text(json.dumps(workload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': 'SCOPED_REPAIR_RECORDED', 'files': len(files), 'original_normative_contexts': 2, 'native_simulations': 'PENDING'}))
