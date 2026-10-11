"""Close implementation evidence only after release and real delivery passed."""
import argparse
import difflib
import hashlib
import json
import shutil
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--receipt', type=Path, required=True)
args = parser.parse_args()
folder = Path(__file__).resolve().parent
root = folder.parents[2]
receipt = json.loads(args.receipt.read_text(encoding='utf-8-sig'))
assert receipt['status'] == 'PASS'
assert all(check['exit_code'] == 0 for check in receipt['checks'])
required = {'storage-tests','typecheck','frontend-tests','backend-tests','browser-e2e','small-http','large-http'}
assert required <= {check['name'] for check in receipt['checks']}
live = json.loads((folder / 'production-verification.json').read_text())
ui = json.loads((folder / 'production-ui-verification.json').read_text())
assert live['running_image'] == live['tested_image'] == receipt['image_id']
assert all(live['project_unchanged'].values())
assert ui['project'] == '20261009072206008-4bb505f1'
assert ui['formats'] == '3 BLF, DBC, PCAP'
assert ui['toolbar_overflow'] is False
restoration = json.loads((folder / 'eip-pause-state.json').read_text())
assert not restoration['paused_ids']
assert restoration.get('restored_at')
assert all(after['paused'] == before['paused'] and after['running'] == before['running']
           for before, after in zip(restoration['before'], restoration['after_resume']))

def ref(path):
    path = path.resolve()
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

work = json.loads((folder / 'workload.json').read_text())
comparison_path = folder / 'performance-comparison.json'
comparison = json.loads(comparison_path.read_text())
comparison.update(release_gate_pending=False, release_receipt=ref(args.receipt))
comparison_path.write_text(json.dumps(comparison, indent=2))
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
    changes.extend(difflib.unified_diff(prior,current,fromfile='before/'+relative,tofile='after/'+relative))
diff = folder / 'implementation.diff'
diff.write_text(''.join(changes),encoding='utf-8')
work.update(before=before_refs, after=after_refs, diff=[ref(diff)])
gate = args.receipt.resolve().parent
def passed(*paths):
    return {'status':'PASSED','evidence':[ref(path) for path in paths]}
work['outcomes'] = {
    'responsive_toolbar':passed(folder/'targeted-browser/report.json',folder/'toolbar-production-954.jpg'),
    'native_trace_defaults':passed(folder/'targeted-browser/report.json',folder/'production-ui-verification.json'),
    'canonical_blf_dbc':passed(gate/'backend-tests.log',folder/'offline-project-dbc-summary.json',folder/'dbc-second-decoder.json'),
    'light_explanation':passed(folder/'light-warning-evidence.json'),
    'production_delivery':passed(args.receipt,folder/'production-verification.json'),
    'wizard_sizing_performance':passed(folder/'performance-comparison.json', folder/'performance-targeted-final.xml', args.receipt),
}
work['validations'] = {
    'targeted_regression':passed(folder/'targeted-browser/report.json',gate/'backend-tests.log'),
    'typecheck':passed(args.receipt,gate/'typecheck.log'),
    'release_gate':passed(args.receipt),
    'live_verification':passed(folder/'production-verification.json',folder/'production-ui-verification.json'),
    'eip_restoration':passed(folder/'eip-pause-state.json'),
    'sizing_regression':passed(folder/'performance-targeted-final.xml', folder/'performance-comparison.json'),
}
if 'wizard_sizing_performance' not in work['required_outcomes']:
    work['required_outcomes'].append('wizard_sizing_performance')
if 'sizing_regression' not in work['validation_requirements']:
    work['validation_requirements'].append('sizing_regression')
if 'eip_restoration' not in work['validation_requirements']:
    work['validation_requirements'].append('eip_restoration')
work['delivery'].update(tested_version=receipt['image_id'],running_version=live['running_image'],checks={
    'release':passed(args.receipt),
    'deployment':passed(folder/'deployment.log',folder/'production-verification.json'),
    'health':passed(folder/'production-verification.json'),
    'functional':passed(folder/'production-ui-verification.json',folder/'toolbar-production-954.jpg'),
})
work.update(completion_status='COMPLETED',remaining_findings=[])
(folder/'workload.json').write_text(json.dumps(work,indent=2),encoding='utf-8')
print('Complete release and delivery evidence recorded.')
