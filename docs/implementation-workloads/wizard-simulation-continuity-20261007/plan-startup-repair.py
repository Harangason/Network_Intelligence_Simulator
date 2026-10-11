import hashlib, json, shutil
from pathlib import Path
out = Path(__file__).parent
root = out.parents[2]
path = out/'workload.json'
work = json.loads(path.read_text(encoding='utf-8'))
work.setdefault('repair_history',[]).append(work['repair'])
files = ['scripts/dev/launch-networkis.py','backend/tests/test_server_startup.py']
evidence = [out/name for name in ['performance-app-state.json','performance-backend-startup.log','backend-startup-profile.log','backend-startup.prof']]
work['repair'] = {
    'finding_ids':['BACKEND_COLD_START_BUDGET'], 'owner':'PROJECT_PRODUCT',
    'root_cause':'The launcher kills its still-running backend after 20 seconds. The required complete catalog/import initialization alone measured 20.5 seconds under profiling; captured restart exits at 21.66 seconds with no backend exception, before readiness. Recovery and cold imports need a bounded startup allowance distinct from wizard stage progress.',
    'first_failing_layer':'Launcher cold-start readiness deadline',
    'reproduction':'Existing I2C browser test restarts disposable candidate; container exits 1 with Backend wurde nicht bereit, no OOM, fixed host port unchanged.',
    'evidence':[{'path':str(file.resolve()),'sha256':hashlib.sha256(file.read_bytes()).hexdigest()} for file in evidence],
    'affected_files':files,
    'acceptance_criteria':['Bound backend initialization by 90 seconds on initial start and automatic restart', 'Require matching instance health and retain prompt failure on dead process', 'Keep frontend/database checks and all browser/native/wizard watchdog budgets unchanged', 'Real restart and full large graph must pass before release'],
    'targeted_tests':['test_server_startup.py','new small wizard','Raspberry Pi','exact confirmed 50/250/250'],
    'weaken_assertions_to_pass':False,'status':'READY',
}
for name in files:
    if name not in work['files_inspected']:
        work['files_inspected'].append(name)
        before = out/'before'/name; before.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(root/name,before)
work['revision_before'] = {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in work['files_inspected']}
path.write_text(json.dumps(work,indent=2),encoding='utf-8')
