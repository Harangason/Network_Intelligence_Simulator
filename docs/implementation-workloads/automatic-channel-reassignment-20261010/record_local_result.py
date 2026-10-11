import difflib
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
path = folder / 'workload.json'
work = json.loads(path.read_text())
root = Path(work['repository'])
ref = lambda p: {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
log = folder / 'targeted-tests.log'
assert '55 passed' in log.read_text(encoding='utf-8-sig') and ' failed,' not in log.read_text(encoding='utf-8-sig')
files = list(work['revision_before'])
after = folder / 'after'
diff = []
for name in files:
    target = after / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((root / name).read_bytes())
    diff.extend(difflib.unified_diff((folder / 'before' / name).read_text(encoding='utf-8').splitlines(True),
        target.read_text(encoding='utf-8').splitlines(True), fromfile='before/' + name, tofile='after/' + name))
diff_path = folder / 'implementation.diff'
diff_path.write_text(''.join(diff), encoding='utf-8')
gate_folder = root / 'backend/test-output/release-gates/delivery-c3e609343e23'
receipts = list(gate_folder.glob('*/receipt.json'))
assert len(receipts) == 1
receipt = json.loads(receipts[0].read_text())
assert receipt['status'] == 'FAIL'
release_log = folder / 'release-and-deploy.log'
assert 'image retention budget reached' in receipt['error']
report = {'status': 'LOCAL_IMPLEMENTATION_VERIFIED_DELIVERY_PENDING', 'targeted_tests': '55 passed, 1 existing warning',
          'test_scope': ['Shared physical-channel materialization across CAN-FD, LIN, Ethernet and Modbus RTU',
                         'Primary sender alignment, active-primary stability and multichannel preservation',
                         'Actual full captured generated model: capacity split review/apply/reload with unchanged signals and frames'],
          'current_project_read_only_replay': '34 primaries need alignment, including Licht; ownership and technology unchanged',
          'full_nine_stage_release_gate': 'NOT_RUN_STORAGE_BLOCK', 'release_receipt': str(receipts[0]),
          'production_image': 'sha256:ad0de59d2493605616536846bf0e342daf066330da716230442b41921af5a4da',
          'production_contains_new_fix': False, 'product_model_mutations': 0,
          'pending': ['User retention exception for the verified archive of previous unused image ff5438ce73a2',
                      'Complete full release gate, exact tested image deployment and affected functionality verification',
                      'Reconcile existing project references through the canonical reviewed model path; preserve actual unconnected-resource findings']}
result = folder / 'local-verification.json'
result.write_text(json.dumps(report, indent=2), encoding='utf-8')
work['files_changed'] = files
work['after'] = [ref(after / name) for name in files]
work['diff'] = [ref(diff_path)]
work['validations'] = {'targeted_regression': {'status': 'PASSED', 'evidence': [ref(log), ref(result)]},
                       'release_gate': {'status': 'BLOCKED', 'evidence': [ref(receipts[0]), ref(release_log)]}}
work['outcomes'] = {key: {'status': 'PASSED', 'evidence': [ref(log), ref(result)]} for key in
                    ('consistent_primary_binding', 'single_channel_reuse', 'parallel_channel_preservation', 'wizard_regression')}
work['outcomes']['production_delivery'] = {'status': 'PENDING', 'evidence': [ref(result)]}
work['remaining_findings'] = report['pending']
work['completion_status'] = 'WAITING_FOR_DECISION'
work['delivery']['status'] = 'BLOCKED_STORAGE_RETENTION'
work['delivery']['target'] = 'Canonical NetworkIS stack, port 13500'
work['delivery']['running_version'] = report['production_image']
work['storage_review'] = ref(folder / 'storage-review.json')
path.write_text(json.dumps(work, indent=2), encoding='utf-8')
print(json.dumps({'status': report['status'], 'release_receipt': str(receipts[0]), 'deployment_pending': True}))
