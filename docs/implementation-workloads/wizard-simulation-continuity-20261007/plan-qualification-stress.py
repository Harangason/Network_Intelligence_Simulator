import hashlib,json,shutil
from pathlib import Path
out=Path(__file__).parent.resolve();root=out.parents[2];path=out/'workload.json'
work=json.loads(path.read_text(encoding='utf-8'))
files=['backend/tests/test_wizard_large_routing.py','backend/tests/test_simulation_parameter_defaults.py','docs/migrations/structure_mapping.csv']
for name in files:
    if name not in work['files_inspected']:
        work['files_inspected'].append(name);before=out/'before'/name
        before.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,before)
work.setdefault('repair_history',[]).append(work['repair'])
proof=root/'backend/test-output/release-gates/wizard-simulation-continuity-native-final/2c0112238540/backend-tests.log'
work['repair']={'finding_ids':['MISSING_CATALOG_RESPONSE_MAPPING','UNDECLARED_LARGE_STRESS_PADDING','SIZING_ONLY_TEST_POLICY_DISABLED'],
 'owner':'SHARED','category':'IMPLEMENTATION','cause':'VERIFICATION_CONFIGURATION_AND_MIGRATION_INVENTORY',
 'independent_causes':['Canonical catalog-response files are missing from the migration inventory','The stress fixture relied on undeclared starter padding instead of an explicit physical CAN-FD layout','The focused sizing-only mock omitted the enabled native sizing policy'],
 'root_cause':'The full suite reports21687 passes and2 failures. Two actual new catalog-response files are not mapped. The full captured simulation test formerly obtained artificial64-byte conservative bounds from starter layout; corrected message-aware bounds legitimately require fewer channels. Its fixture must explicitly declare64-byte DLC15/CRC21 transport padding to preserve the >100-channel stress scope. Saved assumptions must be asserted usable without falsely certifying hardware. The new sizing-only mock omitted enabled:true and therefore correctly skipped sizing.',
 'first_failing_layer':'Migration inventory and native stress fixture',
 'reproduction':'Full backend log records missing catalog-response files and37<101 proposed channels; new mock gets no sizing call with a disabled default policy.',
 'affected_files':files,
 'evidence':[{'path':str(proof),'sha256':hashlib.sha256(proof.read_bytes()).hexdigest()}],
 'acceptance_criteria':['Map only the two actual canonical catalog-response files, preserving existing migration entries','Declare padded CAN-FD transport before generation using reviewed native DLC15/wire64/CRC21; do not rewrite captured graph or logical message DLC/cycles/IDs','Retain >100 physical channels, unique identities, ALL route counts, all signal/message preservation and strict native rate/schedule checks','Align this explicitly unqualified simulation fixture with the requested semantics: require hardware qualification false and nominal simulation capacity true for every network; qualified-input positive regressions remain separate and unchanged','Enable the native sizing policy explicitly in the focused mock','Retain all wizard deadlines and eight-case/full gate requirements; no previous failed receipt authorizes delivery'],
 'targeted_tests':['structure completion','full captured routing/capacity stress','sizing-only native/MCP regressions','eight browser cases and complete release gate'],
 'weaken_assertions_to_pass':False,'status':'READY'}
work['revision_before']={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in work['files_inspected']}
work['completion_status']='REPAIRING';path.write_text(json.dumps(work,indent=2),encoding='utf-8')
print('Explicit native padding and stricter simulation/hardware distinction; strong stress scope retained.')
