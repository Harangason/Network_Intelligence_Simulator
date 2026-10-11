import hashlib,json,shutil
from pathlib import Path
out=Path(__file__).parent.resolve();root=out.parents[2]
path=out/'workload.json';work=json.loads(path.read_text(encoding='utf-8'))
files=['backend/nis/engineering/capacity/service.py','backend/nis/communication/technologies/ethernet/timing.py','backend/nis/agent/core/engineering_agent.py','backend/tests/test_technology_parameter_review.py','backend/tests/test_simulation_parameter_defaults.py','backend/tests/test_capacity_can_schedule.py','backend/tests/test_wizard_generation.py','frontend/e2e/wizard.spec.ts']
for name in files:
    if name not in work['files_inspected']:
        work['files_inspected'].append(name)
        before=out/'before'/name;before.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,before)
work.setdefault('repair_history',[]).append(work['repair'])
work['repair']={'finding_ids':['CONFIRMED_RATE_DROPS_SAVED_SCENARIO','NATIVE_LAYOUT_INCONSISTENT','POST_SPLIT_SIZING_STALE'],
 'owner':'PROJECT_PRODUCT','category':'IMPLEMENTATION','cause':'SCENARIO_CONFIGURATION_AND_GRAPH_CURRENCY',
 'root_cause':'Captured disposable SQL demonstrates rate-only ingress drops native configuration; conservative CAN-FD timing uses starter padding rather than native message layout; Ethernet assumed dependent PHY/layout values do not follow authoritative rates; physical segment splits leave communication sizing stale.',
 'first_failing_layer':'Native simulation capacity/preflight',
 'reproduction':'Nine full large-project returns pass; native preflight blocks two LIN schedules and eight Ethernet profiles. Restored isolated SQL independently reproduces the same findings.',
 'affected_files':files,
 'evidence':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in [out/'native-preflight-diagnostic.json',out/'native-preflight-resolver-before.json']],
 'acceptance_criteria':['Native per-message padding is used consistently by nominal and conservative CAN-FD timing; explicitly fixed padding remains fixed','Only assumed Ethernet dependent values may be derived from native profile constraints; confirmed rates and explicit incompatible PHY values remain authoritative','Hardware/device and functional evidence are never promoted by assumptions','Wizard reruns generated communication sizing after graph changes without resetting or replacing user parameters; locked periods remain locked','Complete explicit-device fixture supplies the required isolated virtual publisher binding','Browser rate expectations match the unchanged 100-Mbit Ethernet fixture prompt; actual changed-value provenance assertions remain strict','All targeted native tests, eight browser cases, complete gate and exact delivery remain mandatory'],
 'targeted_tests':['native simulation/default/rate/negative/capacity suites','captured SQL reproduction','eight browser cases and complete release gate'],
 'weaken_assertions_to_pass':False,'status':'READY'}
work['revision_before']={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in work['files_inspected']}
work['completion_status']='REPAIRING'
path.write_text(json.dumps(work,indent=2),encoding='utf-8')
print('Native constraints and actual graph currency; explicit values and release gates retained.')
