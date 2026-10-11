"""Capture scoped source evidence; never changes product or release state."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def reference(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


work = json.loads((HERE / 'workload.json').read_text(encoding='utf-8-sig'))
changes = []
after = []
for relative in work['files_changed']:
    original, source = HERE / 'before' / relative, ROOT / relative
    destination = HERE / 'after' / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    after.append(reference(destination))
    changes.extend(difflib.unified_diff(original.read_text(encoding='utf-8').splitlines(keepends=True), source.read_text(encoding='utf-8').splitlines(keepends=True), fromfile='before/' + relative, tofile='after/' + relative))
(HERE / 'changes.patch').write_text(''.join(changes), encoding='utf-8')
work['after'] = after
work['diff'] = [reference(HERE / 'changes.patch')]
frontend = reference(HERE / 'frontend-tests.log')
browser = reference(HERE / 'isolated-browser.log')
report = reference(HERE / 'isolated-browser.json')
receipt = reference(ROOT / 'backend/test-output/release-gates/delivery-882383b8295b/fb01b0e61366/receipt.json')
work['validations'] = {
    'frontend_regression': {'status': 'PASSED', 'scope': '604 frontend unit tests', 'evidence': [frontend]},
    'typecheck': {'status': 'PASSED', 'scope': 'TypeScript check and final production build', 'evidence': [reference(HERE / 'typecheck.log'), reference(HERE / 'frontend-build.log')]},
    'isolated_backend': {'status': 'PASSED', 'scope': '49 technology registry/default tests; disposable SQL database', 'evidence': [reference(HERE / 'isolated-regression.log')]},
    'isolated_browser': {'status': 'PASSED', 'scope': '4 source-host cases. Three real persisted trace imports, one read-only display fixture. No nine-stage wizard release acceptance.', 'evidence': [browser, report]},
    'release_gate': {'status': 'BLOCKED', 'scope': 'Canonical release-and-deploy attempted; failed before checks at 100-image retention budget. Source has subsequently changed; this failed receipt is blocker evidence only.', 'evidence': [receipt, reference(HERE / 'release-and-deploy.log')]},
}
work['outcomes'] = {
    'new_run_after_terminal_history': {'status': 'PARTIAL', 'scope': 'Central guards, terminal-history display and duplicate submit unit/UI checks passed. Actual new job plus reload regression added to real small wizard; not executed yet.', 'evidence': [frontend, browser]},
    'readable_trace_names_and_context': {'status': 'PASSED', 'evidence': [frontend, browser, report]},
    'signal_analysis_navigation': {'status': 'PASSED', 'scope': 'Real imported 150 channels and 1205 samples; late channel 149 and event 1204 reached; clearing selection retained.', 'evidence': [browser, report]},
    'visible_sequence_measurement': {'status': 'PASSED', 'scope': 'Unit timebase checks and display fixture measure 200 ms across pages, then reset; not a functional latency acceptance.', 'evidence': [frontend, browser]},
    'production_delivery': {'status': 'BLOCKED', 'evidence': [receipt]},
}
work['verification_artifacts'] = [reference(HERE / 'test_isolated_browser.py')]
work['tests'] = {'status': 'TARGETED_PASSED_FULL_RELEASE_BLOCKED', 'frontend': 604, 'backend': 49, 'browser': 4, 'complete_wizard_e2e_passed': False}
work['completion_status'] = 'BLOCKED_NOT_DEPLOYED'
work['delivery'].update(status='BLOCKED_IMAGE_RETENTION_AND_AUTO_REVIEW', tested_version=None, running_version='sha256:ebba6b6c79f448b7ad6736b461098310da056b1f951cf873f306f131239e5ba1', checks={'release': {'status': 'BLOCKED', 'evidence': [receipt]}})
work['remaining_findings'] = [
    'Complete immutable-image release gate and actual small-wizard new-job regression have not passed for these changes.',
    'Production still runs the previous image; current changes are not deployed.',
    'Exact failed-image removal was authorized through question replies twice, but auto-review rejected the serialized replies as untrusted transcript approval. Direct current plain-text authorization is required before retrying; no removal or alternative prune occurred.',
]
work['implementation_notes'] = [
    'Raw IDs and evidence remain intact; names resolve only from explicit trace data or the matching frozen model snapshot.',
    'All decoded channels in the loaded window are selectable; picker, plots, values and messages paginate without truncating the loaded dataset. Per-frame parser safety bound remains 64.',
    'Sender/receiver context uses readable columns; technical IDs and original records are available in a lazy properties dialog.',
    'Time measurements require two distinct events with a common proven timebase; delta is visible in ms and microseconds.',
    'Diagram browser case checks original fault/status counts, frequency cells, separate timebases, exact finding links and unavailable cause acceptance for imported traces.',
    'Previous five paused-test UI workloads retain their historical evidence. This follow-up provides only the explicit current scopes above, never complete release evidence.',
]
(HERE / 'workload.json').write_text(json.dumps(work, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
