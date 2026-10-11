import hashlib,json,shutil
from pathlib import Path
out=Path(__file__).parent.resolve(); root=out.parents[2]; path=out/'workload.json'
work=json.loads(path.read_text(encoding='utf-8'))
files=['backend/nis/intelligence/engineering/intelligence/network_planning.py',
       'backend/tests/test_automatic_resource_planning.py']
for name in files:
    if name not in work['files_inspected']:
        work['files_inspected'].append(name); before=out/'before'/name
        before.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(root/name,before)
work.setdefault('repair_history',[]).append(work['repair'])
proof=out/'stress-padding-diagnostic.json'
work['repair']={'finding_ids':['SIMULATION_LOAD_IGNORED_BY_SEGMENT_PLANNER'],
 'owner':'PROJECT_PRODUCT','category':'IMPLEMENTATION','cause':'QUALIFICATION_AWARE_CONSUMER_GAP',
 'root_cause':'Native capacity deliberately separates hardware load (null without qualification) from usable simulation_capacity. The segment planner reads only hardware LOAD_KEYS and transmission delay, silently treating a validated CAN-FD simulation load of10/11.5/15 percent as zero; only LIN schedule failures are split, yielding37 channels despite explicitly padded frames.',
 'first_failing_layer':'Network distribution consumer of native capacity snapshots',
 'reproduction':'stress-padding-diagnostic.json records the exact current padded native source snapshot and37 LIN-only physical channels; CAN-FD simulation_capacity_verified=true and native760-bit frame are retained but planning load is0.',
 'affected_files':files,
 'evidence':[{'path':str(proof),'sha256':hashlib.sha256(proof.read_bytes()).hexdigest()}],
 'acceptance_criteria':['Use validated native simulation loads and native per-segment delays in detached planning rows; never edit captured capacity data or promote hardware/functional timing acceptance',
   'Reject invalid/incomplete/nonfinite simulation load instead of treating it as zero',
   'Preserve source/recipient grouping, hardware hard limits, schedule checks, fixed inventory and guarded physical proposals',
   'Retain >100-channel captured padded stress, route counts and all encoding/message preservation checks',
   'Add pure parity/immutability and invalid simulation consumer regressions and require the unchanged complete release gate'],
 'targeted_tests':['automatic resource planning','captured native distribution replay','full captured routing stress','complete release gate'],
 'weaken_assertions_to_pass':False,'status':'READY'}
work['revision_before']={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in work['files_inspected']}
work['completion_status']='REPAIRING';path.write_text(json.dumps(work,indent=2),encoding='utf-8')
print('Native simulation consumer repair planned; qualification remains false.')
