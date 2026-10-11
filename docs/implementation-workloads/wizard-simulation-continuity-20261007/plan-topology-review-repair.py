import hashlib,json,shutil
from pathlib import Path

out = Path(__file__).parent.resolve(); root=out.parents[2]
path = out/'workload.json'; work=json.loads(path.read_text(encoding='utf-8'))
affected=['backend/nis/agent/tools/validation.py','backend/nis/communication/registry.py',
    'backend/nis/communication/technologies/lin/timing.py','backend/nis/interfaces/http/engineering.py',
    'backend/tests/test_proposal_capacity.py','backend/tests/test_technology_registry_metadata.py']
for name in affected:
    if name not in work['files_inspected']:
        work['files_inspected'].append(name)
        before=out/'before'/name; before.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(root/name,before)
work.setdefault('repair_history',[]).append(work['repair'])
evidence=[out/'before-topology-catalog-browser.json',out/'topology-return-request-diagnostic.json',
    out/'topology-native-review-route-profile.txt',out/'topology-native-return-profile.txt',out/'topology-baseline-image.json']
work['repair']={'finding_ids':['TOPOLOGY_RETURN_NATIVE_REVIEW_COST'],'owner':'PROJECT_PRODUCT','category':'PROJECT_PRODUCT',
    'cause':'REPEATED_NATIVE_OPERATING_POINT_AND_PROFILE_COPY',
    'root_cause':'Corrected full canonical SQL measurement preserves declared networks and validates topology successfully. Parameter review takes 47.84s and topology validation 49.49s under profiling. Each does 1,304 scenario resolutions; 16.9s is repeated LIN schema/constraint copying. Browser parallel review takes 51.219s and topology return exceeds unchanged 60s readiness after all model/routing detours pass.',
    'first_failing_layer':'Complete native topology proposal refresh',
    'reproduction':'Regular e6 candidate: four cases pass; large has nine model and nine routing detours, fails first topology return. Corrected SQL measurement returns VALIDATED; initial diagnostic missing-network findings are input errors, preserved explicitly.',
    'evidence':[{'path':str(file),'sha256':hashlib.sha256(file.read_bytes()).hexdigest()} for file in evidence],
    'affected_files':affected,
    'acceptance_criteria':['Use profile-owned keys and explicit evidence/identity/assumption scopes to share only equal native operating points inside one call',
        'Preserve clocks, provenance, nested capabilities, network scope and unknown-native facts; no cross-request cache',
        'Evaluate LIN derivations against the registered constraints directly; return detached values and preserve every fixed field',
        'Reuse one effective graph for all parameter review calculations; retain all freshness and proposal revision checks',
        'Compare complete captured topology findings, capacity and plans plus native LIN derivations against actual e6 candidate code',
        'Keep all release rules/assertions/deadlines and deploy exact image only after complete gate PASS'],
    'targeted_tests':['test_proposal_capacity.py','test_technology_registry_metadata.py','native technology parameter/default tests','test_engineering_mcp.py','full large browser repeated returns'],
    'weaken_assertions_to_pass':False,'status':'READY'}
work['revision_before']={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in work['files_inspected']}
work['remaining_findings']=['Large topology parameter-return refresh exceeds unchanged readiness due to repeated native calculation','Complete release gate and exact production delivery pending']
work['completion_status']='REPAIRING'
path.write_text(json.dumps(work,indent=2,ensure_ascii=False),encoding='utf-8')
print('Corrected native topology measurement repair planned; no rules weakened.')
