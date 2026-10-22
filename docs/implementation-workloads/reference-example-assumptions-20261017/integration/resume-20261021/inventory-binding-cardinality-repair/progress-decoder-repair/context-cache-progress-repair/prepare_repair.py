"""Capture actual cancellation and immutable before evidence; no inference/writes to NIS."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.request import Request, urlopen

ROOT = Path.cwd()
HERE = Path(__file__).resolve().parent
C = HERE.parent
W = ROOT / 'docs/implementation-workloads/reference-example-assumptions-20261017'

def save(name, value):
    path = HERE / name
    assert not path.exists(), path
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def get(url, project=None):
    with urlopen(Request(url, headers={'X-Project-ID': project} if project else {}), timeout=20) as response:
        return json.load(response)

processes = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command',
    "@(Get-CimInstance Win32_Process | Where-Object {($_.Name -eq 'python.exe' -and $_.CommandLine -match 'native_original_document_driver.py') -or ($_.Name -eq 'llama-server.exe' -and $_.ParentProcessId -eq 47644)} | Select-Object ProcessId,ParentProcessId,Name) | ConvertTo-Json -Compress"], text=True) or '[]')
assert not processes, processes
provider = get('http://127.0.0.1:11434/api/ps')
assert provider['models'] == [], provider
project = '20261018160006106-ee6625c9'
draft = get('http://127.0.0.1:55339/api/engineering/agent/project-draft', project)
assert draft['data']['status'] == 'REFERENCE_CANCELED', draft['data']['status']
draft_ref = save('canceled-draft.json', draft)
bundle = get('http://127.0.0.1:55339/api/engineering/projects/export', project)
counts = {key: len(value) for key, value in bundle['source_data'].items()}
assert not any(counts.values()), counts
events_path = W / 'integration/native-progress-vehicle/plan-reference/events.ndjson'
events = [json.loads(line) for line in events_path.read_text(encoding='utf-8').splitlines() if line.strip()]
progress = [event for event in events if event.get('type') == 'PROGRESS']
cancel_ref = save('cancellation-74486.json', {
    'at_utc': datetime.now(timezone.utc).isoformat(),
    'authorization': 'Direct human answer: Regulär abbrechen und jetzt reparieren',
    'action': 'Ctrl-C to existing native client session74486; no provider kill/restart',
    'client_session_after': 'Unknown process id74486',
    'native_driver_processes_and_main_workers': processes,
    'provider': provider, 'server_status': draft['data']['status'], 'draft': draft_ref,
    'canonical_counts': counts, 'last_progress': progress[-1] if progress else None,
    'events_sha256': hashlib.sha256(events_path.read_bytes()).hexdigest(),
    'client_state_status_stale': json.loads((events_path.parent.parent / 'state.json').read_text())['status'],
    'normal_result_received': any(event.get('type') == 'RESULT' for event in events),
    'native_driver_exit_code': None,
    'exit_code_note': 'Lost handle; no invented exit code. Server cancellation and actual process/provider end verified independently.',
    'automation': 'DELETED_AT_DIRECT_HUMAN_REQUEST',
    'full_original_acceptance': False,
})
files = ['backend/nis/agent/orchestration/local_reasoner.py', 'backend/tests/test_reference_reasoner.py']
revisions, before = {}, []
for file in files:
    path = ROOT / file
    raw = path.read_bytes()
    revisions[file] = hashlib.sha256(raw).hexdigest()
    copy = HERE / ('before-' + path.name)
    assert not copy.exists(), copy
    copy.write_bytes(raw)
    before.append({'path': str(copy), 'sha256': revisions[file]})
root = json.loads((W / 'integration/workload.json').read_text(encoding='utf-8'))
assert len(root['required_outcomes']) == len(root['validation_requirements']) == 15
cause = C / 'worker-latency-check-20261021T133738Z/root-cause.json'
work = {'repository': str(ROOT), 'kind': 'repair', 'modify_code': True, 'allow_repair': True,
    'campaign_id': 'nis-ea-independent-20260924-run1', 'status': 'REPAIRING',
    'requested_change': 'Lossless append-only native reference context, stable configured capacity and truthful visible response/scope/retry progress.',
    'revision_before': revisions, 'unresolved_decisions': [], 'before': before,
    'required_outcomes': ['cacheable_complete_context', 'truthful_progress', 'both_originals_and_delivery'],
    'validation_requirements': ['red_green', 'isolated_regressions', 'actual_native_cache_probe', 'both_originals_full_gate_delivery'],
    'repair': {'owner': 'PROJECT_PRODUCT', 'first_failing_layer': 'Native reference prompt construction and progress text',
        'root_cause': json.loads(cause.read_text(encoding='utf-8')),
        'reproduction': 'Actual provider log: recurrent checkpoint rollback unavailable after rewritten current_candidate; 29951-token full reprocessing vs 54-token appended retry.',
        'evidence': [cancel_ref, {'path': str(cause), 'sha256': hashlib.sha256(cause.read_bytes()).hexdigest()}],
        'affected_files': files, 'acceptance_criteria': ['Exact prior native message/reply prefix preserved', 'Lossless full input and strict guards', 'Actual visible calls/scope/retry', 'Full originals and exact-image release delivery'],
        'targeted_tests': ['context continuation and independent JSON patch roundtrip', 'unchanged overflow rejection', 'progress and correction retries'],
        'weaken_assertions_to_pass': False},
    'outcomes': {}, 'validations': {}, 'delivery': {'decision': 'YES', 'authorization': 'Standing AGENTS and direct human order'}}
save('workload.json', work)
print(json.dumps({'cancellation': cancel_ref, 'revision_before': revisions, 'original_scope': '15/15 unchanged'}))
