import hashlib,json,shutil
from pathlib import Path
out=Path(__file__).parent.resolve();root=out.parents[2]
path=out/'workload.json';work=json.loads(path.read_text(encoding='utf-8'))
files=['backend/nis/agent/core/engineering_agent.py','backend/nis/agent/tools/wizard_generation.py','backend/nis/agent/tools/services.py','backend/tests/test_simulation_parameter_defaults.py','backend/tests/test_wizard_generation.py']
for name in files:
    if name not in work['files_inspected']:
        work['files_inspected'].append(name)
        before=out/'before'/name;before.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,before)
work.setdefault('repair_history',[]).append(work['repair'])
proof=out/'catalog-browser/wizard-exact-confirmed-50--c2f3c-gh-real-wizard-review-large/error-context.md'
work['repair']={'finding_ids':['CAPACITY_CONTINUATION_REENTERS_SPATIAL_GENERATION'],
 'owner':'PROJECT_PRODUCT','category':'IMPLEMENTATION','cause':'DEFAULT_GENERATION_USED_FOR_ALREADY_COMPLETE_CONFIGURATION',
 'root_cause':'All nine integrated parameter returns pass, but the capacity continuation calls full default generation including spatial zoning although its canonical topology and saved parameters are complete. The first calculation finishes only after about210s; subsequent capacity planning exceeds the unchanged240s progress boundary.',
 'first_failing_layer':'Capacity continuation latency',
 'reproduction':'Captured large browser case fails at frontier4/9 after17.7min; source bcb599d3e966. The same sizing service successfully resolves the restored split graph without spatial generation.',
 'affected_files':files,
 'evidence':[{'path':str(proof),'sha256':hashlib.sha256(proof.read_bytes()).hexdigest()}],
 'acceptance_criteria':['Already complete parameter continuations call only native communication sizing, never regenerate defaults or spatial topology','Sizing-only tool mode explicitly requires complete saved parameters and topology; incomplete inputs fail without writes','Preserve user values, provenance, locked periods, model review and all native constraints','Use the same existing version-checked sizing service and authorized actor','Keep20-minute fullcase,240-second progress,60-second return and180-second manual-write bounds unchanged','Rerun targeted tests, all eight cases and complete gate before exact production delivery'],
 'targeted_tests':['saved-current-graph MCP regression','sizing-only nonmutation and incomplete-input tests','all eight real browser cases','complete release gate'],
 'weaken_assertions_to_pass':False,'status':'READY'}
work['revision_before']={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in work['files_inspected']}
work['completion_status']='REPAIRING';path.write_text(json.dumps(work,indent=2),encoding='utf-8')
print('Current saved configuration is sized without spatial/default regeneration; all deadlines retained.')
