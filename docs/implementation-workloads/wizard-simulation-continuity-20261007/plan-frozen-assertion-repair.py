import hashlib, json
from pathlib import Path
out = Path(__file__).parent
root = out.parents[2]
path = out/'workload.json'
work = json.loads(path.read_text(encoding='utf-8'))
work.setdefault('repair_history',[]).append(work['repair'])
file = out/'frozen-rate-trace-observation.json'
work['repair'] = {
    'finding_ids':['FROZEN_RATE_SCOPE_ASSERTION'], 'owner':'TEST_DATA',
    'root_cause':'The new assertion expects scoped transport fields at the runtime parameter root. Actual frozen CAN-FD network retains data_bitrate 1000000 and can_fd_data_prescaler 2; seed remains runtime-wide.',
    'first_failing_layer':'New browser snapshot assertion uses wrong storage scope',
    'reproduction':'Small wizard completes nine stages; captured frozen response has native rate/prescaler on its CAN-FD network.',
    'evidence':[{'path':str(file.resolve()),'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}],
    'affected_files':['frontend/e2e/wizard.spec.ts'],
    'acceptance_criteria':['Assert seed at runtime root', 'Assert edited data rate and prescaler on every frozen CAN-FD network', 'Keep all nine stages, restore/no START, same run, actual restart and full signal coverage checks'],
    'targeted_tests':['new small wizard'], 'weaken_assertions_to_pass':False, 'status':'READY',
}
work['revision_before'] = {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in work['files_inspected']}
work['remaining_findings'] = ['Large browser performance remains unverified because earlier case failed.', 'Backend readiness failed within launcher startup budget after restart; diagnosis pending.']
path.write_text(json.dumps(work,indent=2),encoding='utf-8')
