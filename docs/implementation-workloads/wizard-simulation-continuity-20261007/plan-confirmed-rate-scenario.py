import hashlib,json
from pathlib import Path
out=Path(__file__).parent.resolve();root=out.parents[2]
path=out/'workload.json';work=json.loads(path.read_text(encoding='utf-8'))
work.setdefault('repair_history',[]).append(work['repair'])
files=['backend/nis/engineering/capacity/service.py','backend/tests/test_simulation_parameter_defaults.py','backend/tests/test_technology_parameter_review.py']
proof=[out/'native-preflight-resolver-before.json',out/'before-native-configuration-catalog-browser.log',out/'confirmed-rate-targeted.log']
work['repair']={'finding_ids':['CONFIRMED_RATE_DROPS_SAVED_SCENARIO','LIN_PREFLIGHT_SCHEDULE_DIAGNOSIS_PENDING'],
 'owner':'PROJECT_PRODUCT','category':'IMPLEMENTATION','cause':'RATE_ONLY_EARLY_RETURN',
 'root_cause':'Confirmed native rates short-circuit simulation ingress before saved configuration assumptions are merged. Captured Ethernet has FULL/link_up=true in saved assumptions but neither field in resolved output. Native schedule correctly blocks that incomplete input. Separate LIN schedule failures still require diagnosis.',
 'first_failing_layer':'Capacity simulation parameter ingress',
 'reproduction':'All nine large model/routing/topology returns pass. Full preflight then reports Ethernet PROFILE_INCOMPLETE and two LIN NO_SCHEDULE findings. Captured resolver drops all assumed Ethernet/CAN-FD fields when _rate_evidenced=true.',
 'evidence':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in proof],
 'affected_files':files,
 'acceptance_criteria':['Confirmed rates still merge and validate their saved native configuration assumptions', 'Explicit device/network/user values retain precedence; forged assumption provenance and invalid parameters still fail', 'Unused assumptions overridden by validated confirmed native fields cannot invalidate those facts', 'The complete explicit-device regression supplies every scenario configuration value as explicitly reviewed device input and retains all original output assertions; partial confirmed-rate coverage remains separate', 'Mixed confirmed-rate/assumed-configuration calculations and traces cannot claim hardware evidence', 'Preserve legacy actual-only behavior when no simulation assumptions exist', 'Diagnose LIN schedule failures from restored disposable SQL capture; do not suppress real schedule blockers', 'Run targeted native tests, all eight real browser cases, complete release gate and exact production delivery'],
 'targeted_tests':['simulation defaults, capacity, native review/clock/negative suites','captured isolated SQL preflight diagnostic','eight real browser cases'],
 'weaken_assertions_to_pass':False,'status':'READY'}
work['revision_before']={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in work['files_inspected']}
work['remaining_findings']=['Confirmed-rate scenario repair and LIN schedule diagnosis','Eight-case browser/full gate/production delivery pending']
work['completion_status']='REPAIRING';path.write_text(json.dumps(work,indent=2),encoding='utf-8')
print('Retain native assumptions with confirmed rates; no weakening of schedule or provenance gates.')
