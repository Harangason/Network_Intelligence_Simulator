import hashlib,json,shutil
from pathlib import Path
out=Path(__file__).parent.resolve();root=out.parents[2];path=out/'workload.json'
work=json.loads(path.read_text(encoding='utf-8'))
files=['backend/nis/engineering/simulation_observation.py','backend/nis/interfaces/http/engineering.py',
 'backend/tests/test_simulation_observation.py','frontend/src/features/workflow/lib/workflow-api.ts',
 'frontend/src/features/workflow/lib/workflow-api.test.mjs','frontend/src/features/simulation/ui/simulation-wizard.tsx',
 'frontend/e2e/technology-parameter-review.spec.ts','frontend/e2e/wizard.spec.ts']
for name in files:
 if name not in work['files_inspected']:
  work['files_inspected'].append(name);before=out/'before'/name
  before.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,before)
work.setdefault('repair_history',[]).append(work['repair'])
proof=out/'observation-failure.json'
work['repair']={'finding_ids':['UNTOUCHED_DURATION_PROMOTED_TO_EXPLICIT_REQUEST'],
 'owner':'PROJECT_PRODUCT','category':'IMPLEMENTATION','cause':'BULK_FORM_DURATION_ORIGIN',
 'root_cause':'Every public parameter PATCH invokes mark_user_duration on every submitted duration, and the form submits the entire profile while editing only seed or bus values. The standard1s becomes USER_PARAMETER despite no duration edit. The frozen actual large run requires1.071s for second arrivals; five1000ms LIN routes have one received frame and jitterNOT_EVALUATED, so the strict complete conformance assertion fails.',
 'first_failing_layer':'Public parameter-write duration intent and whole-form submission',
 'reproduction':'Current full release image bcd16a961bba finishes allnine workflow stages; final assertion receivesNOT_EVALUATED. Isolated frozen evidence has duration1, EXPLICIT_PARAMETERS, requirementminimum1.071, five unassessed jitter routes, no missing observations or failed routes.',
 'affected_files':files,'affected_services':['Parameter form','Workflow parameter HTTP boundary','Observation planning'],
 'required_fix':'Identify duration fields explicitly edited by bulk clients; restore trusted unchanged saved origin or resolve a new untouched value from its own TechnologyProfile. Changed or explicitly touched durations, including an identical value and legacy direct API requests, remain user-specified. Keep all existing strict observation and conformance checks.',
 'evidence':[{'path':str(proof),'sha256':hashlib.sha256(proof.read_bytes()).hexdigest()}],
 'acceptance_criteria':['Untouched standard duration survives repeated three-protocol saves without becoming fixed user input',
  'Explicitly edited same-value or changed duration remains exact, including a deliberately short window',
  'Server never trusts a client-supplied default marker over a saved explicit value; new defaults come from the selected native TechnologyProfile',
  'An unrelated bulk save retains existing explicit duration and run/project/proposal identity',
  'The existing planner derives the necessary second-arrival window; no changed routes, requirements, event limits, acceptance rules or test budgets',
  'Actual complete large browser case remains conformancePASS with all766 routes evaluated; alloriginal strict checks retained'],
 'targeted_tests':['Observation planner and HTTP duration intent regressions through isolatedSQL runner','Workflow API request-intent tests andtypecheck','Existing native save/reload E2E andcomplete large wizard case','Full release gate and exact tested image deployment'],
 'weaken_assertions_to_pass':False,'status':'PLANNED_WAITING_FOR_FULL_ROUND'}
work['revision_before']={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in work['files_inspected']}
work['completion_status']='REPAIR_PLANNED'
path.write_text(json.dumps(work,indent=2),encoding='utf-8')
print('Duration intent repair planned; application edits wait for active full round to finish.')
