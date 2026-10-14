"""Accept only a fresh, complete native document run; never invoke the model."""
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

base = Path(__file__).resolve().parent
root = base.parents[2]
owner = root / 'docs/implementation-workloads/qwen-document-intake-20261014'
handoff = json.loads((owner / 'active-full-source-handoff.json').read_text(encoding='utf-8'))
source_bytes = Path(sys.argv[1]).read_bytes()
source = source_bytes.decode('utf-8')
digest = lambda value: hashlib.sha256(value).hexdigest()
assert len(source) == handoff['source_chars'] == 19088
assert digest(source_bytes) == handoff['source_sha256']
assert digest((owner / 'live_probe.py').read_bytes()) == handoff['probe_sha256']
for name, expected in handoff['code_sha256'].items():
    assert digest((root / name).read_bytes()) == expected, name
log = Path(handoff['log'])
terminal = json.loads(log.read_text(encoding='utf-8').splitlines()[-1])
assert terminal['status'] == 'PASS' and terminal['source_chars'] == len(source)
proposal_path = Path(handoff['proposal'])
proposal = json.loads(proposal_path.read_text(encoding='utf-8'))
assert proposal['source_complete'] is True
assert proposal['canonical_writes'] is False and proposal['approval_required'] is True
assert proposal['status'] == 'REVIEW_REQUIRED' and proposal['provider'] == 'local_ollama'
assert proposal['model'] == terminal['model'] == 'qwen3.8:27b'
assert proposal['source_sha256'] == digest(source_bytes)
offset = 0
for segment in proposal['segments']:
    assert segment['start'] == offset and segment['end'] > offset
    assert digest(source[offset:segment['end']].encode('utf-8')) == segment['sha256']
    offset = segment['end']
assert offset == len(source) and len(proposal['segments']) == terminal['segments'] == 7
components = proposal['interpretation']['components']
interpretation = proposal['interpretation']
task = interpretation['proposed_task']
for name in ('Powertrain', 'Chassis', 'ADAS', 'Body', 'Infotainment'):
    assert any(c['kind'] == 'INSTANCE' and c['role'] == 'CONTROLLER' and name in c['name'] for c in components), name
    assert name in task, ('confirmed controller missing from global review task', name)
for role in ('SENSOR', 'ACTUATOR'):
    assert any(c['kind'] == 'CATEGORY' and c['role'] == role and c['quantity'] is None for c in components), role
assert 'Keine Zuordnung konkreter Instanzen' not in task
assert 'Keine Zuordnung zu physischen Geräten, da keine konkreten Instanzen' not in task
global_review_text = '\n'.join([task, *interpretation['assumptions'], *interpretation['open_questions']])
assert not re.search(r'\bR\d{4}\b', global_review_text), 'section-local references leaked into global review'
captures = json.loads(Path(handoff['responses']).read_text(encoding='utf-8'))
scopes_path = owner / 'live-qwen-request-scopes.json'
scopes = json.loads(scopes_path.read_text(encoding='utf-8'))
assert len(captures) == len(scopes) and 7 <= len(scopes) <= 14
assert all(r['model'] == 'qwen3.8:27b' and r['done_reason'] == 'stop' for r in captures)
original_scopes = [q['input'] for q in scopes if 'validation_feedback' not in q['input']]
assert len(original_scopes) == 7
assert ''.join(''.join(q['source_lines'].values()) for q in original_scopes) == source
refs = []
for path in (log, proposal_path, Path(handoff['responses']), scopes_path, owner / 'active-full-source-handoff.json'):
    target = base / ('native-accepted-' + path.name)
    shutil.copyfile(path, target)
    refs.append({'path': str(target), 'sha256': digest(target.read_bytes())})
proof = {'status': 'PASSED', 'accepted_at': datetime.now(timezone.utc).isoformat(),
         'session_id': handoff['session_id'], 'source_chars': len(source),
         'source_sha256': digest(source_bytes), 'code_sha256': handoff['code_sha256'],
         'segments': 7, 'actual_model_calls': len(captures), 'model': proposal['model'],
         'global_task_consistency': 'Five confirmed controllers present; known contradictory local no-instance claims and local reference IDs absent; targeted global-merge tests required separately',
         'canonical_writes': False, 'approval_required': True, 'evidence': refs}
proof_path = base / 'native-full-source-acceptance.json'
proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
work_path = base / 'workload.json'
work = json.loads(work_path.read_text(encoding='utf-8'))
work['validations']['live_qwen_full_source'] = {'status': 'PASSED', 'evidence': [
    {'path': str(proof_path), 'sha256': digest(proof_path.read_bytes())}]}
work_path.write_text(json.dumps(work, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': 'PASSED', 'segments': 7, 'actual_model_calls': len(captures)}))
