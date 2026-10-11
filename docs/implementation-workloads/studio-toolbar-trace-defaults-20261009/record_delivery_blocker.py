"""Preserve reviewed implementation evidence without claiming a release PASS."""
import difflib
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

folder = Path(__file__).resolve().parent
root = folder.parents[2]
gate = root / 'backend/test-output/release-gates/studio-toolbar-full-slot/4faafc428761'
receipt = json.loads((gate / 'receipt.json').read_text(encoding='utf-8-sig'))
assert receipt['status'] == 'FAIL'
restoration = json.loads((folder / 'eip-pause-state.json').read_text())
assert restoration['restored_at'] and not restoration['paused_ids']
assert all(a['running'] == b['running'] and a['paused'] == b['paused']
           for b, a in zip(restoration['before'], restoration['after_resume']))
docker = json.loads((root / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
running = subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip()
assert running != receipt['image_id'], 'Candidate unexpectedly deployed without PASS'
resources = {}
for key, name in receipt['containers'].items():
    kind = 'container' if key in {'db', 'app'} else 'volume' if key == 'runtime' else 'network'
    result = subprocess.run([docker, kind, 'inspect', name], capture_output=True, text=True)
    assert result.returncode != 0 and ('no such' in result.stderr.lower() or 'not found' in result.stderr.lower()), result.stderr
    resources[name] = 'REMOVED'
with urlopen('http://127.0.0.1:13500/api/ready', timeout=30) as response:
    assert response.status == 200
    ready = json.loads(response.read())
blocker = {
    'recorded_at': datetime.now(timezone.utc).isoformat(),
    'release_status': 'FAIL', 'production_delivery': 'NOT_DEPLOYED',
    'candidate_image': receipt['image_id'], 'running_image': running,
    'failure': 'Wizard made no new contiguous stage completion within 240000 ms (frontier 4/9).',
    'stage': 'capacity_timing', 'browser_passed_before_failure': 98,
    'remaining_browser_cases': 'Stopped after observed mandatory case failure; not validated',
    'http_checks': 'Not reached', 'cause': 'Stage exceeded progress limit; underlying performance cause unresolved',
    'checks': receipt['checks'], 'eip_restored': True,
    'disposable_resources': resources, 'production_ready': ready,
}
report = folder / 'delivery-blocker.json'
report.write_text(json.dumps(blocker, indent=2), encoding='utf-8')

def ref(path):
    path = path.resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

work = json.loads((folder / 'workload.json').read_text())
before_refs, after_refs, changes = [], [], []
for relative in work['files_changed']:
    source = root / relative
    before, after = folder / 'before' / relative, folder / 'after' / relative
    after.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, after)
    after_refs.append(ref(after))
    if before.is_file():
        before_refs.append(ref(before))
    prior = before.read_text(encoding='utf-8-sig').splitlines(keepends=True) if before.exists() else []
    current = source.read_text(encoding='utf-8-sig').splitlines(keepends=True)
    changes.extend(difflib.unified_diff(prior, current, fromfile='before/' + relative, tofile='after/' + relative))
diff = folder / 'implementation.diff'
diff.write_text(''.join(changes), encoding='utf-8')
work.update(before=before_refs, after=after_refs, diff=[ref(diff)])

def evidence(status, *paths):
    return {'status': status, 'evidence': [ref(path) for path in paths]}

work['outcomes'] = {
    'responsive_toolbar': evidence('PASSED', folder / 'targeted-browser/report.json', folder / 'toolbar-preview-954.jpg'),
    'native_trace_defaults': evidence('PASSED', folder / 'targeted-browser/report.json'),
    'canonical_blf_dbc': evidence('PASSED', gate / 'backend-tests.log', folder / 'offline-project-dbc-summary.json', folder / 'dbc-second-decoder.json'),
    'light_explanation': evidence('PASSED', folder / 'light-warning-evidence.json'),
    'production_delivery': evidence('BLOCKED', gate / 'receipt.json', report),
}
work['validations'] = {
    'targeted_regression': evidence('PASSED', folder / 'targeted-browser/report.json', gate / 'backend-tests.log'),
    'typecheck': evidence('PASSED', gate / 'receipt.json', gate / 'typecheck.log'),
    'release_gate': evidence('FAILED', gate / 'receipt.json', report),
    'live_verification': evidence('BLOCKED', report),
    'eip_restoration': evidence('PASSED', folder / 'eip-pause-state.json'),
}
if 'eip_restoration' not in work['validation_requirements']:
    work['validation_requirements'].append('eip_restoration')
work['delivery'].update(status='BLOCKED', candidate_version=receipt['image_id'], running_version=running)
work.update(completion_status='BLOCKED', remaining_findings=[
    'Mandatory large wizard capacity_timing stage exceeded its 240-second progress bound despite the authorized temporary EIP worker pause.',
    'Production does not yet contain the toolbar and native trace export changes; a complete PASS receipt and exact-image deployment remain required.',
])
(folder / 'workload.json').write_text(json.dumps(work, indent=2), encoding='utf-8')
print(json.dumps(blocker))
