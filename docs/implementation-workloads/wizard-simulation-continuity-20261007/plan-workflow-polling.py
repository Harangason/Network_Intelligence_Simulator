import hashlib,json,shutil
from pathlib import Path
out=Path(__file__).parent.resolve();root=out.parents[2];path=out/'workload.json'
work=json.loads(path.read_text(encoding='utf-8'))
files=['backend/nis/workflow/services/service.py','backend/nis/engineering/simulation_coverage.py',
       'backend/tests/test_non_routed_output_coverage.py','backend/tests/test_simulation_coverage.py','backend/tests/test_workflow.py']
for name in files:
    if name not in work['files_inspected']:
        work['files_inspected'].append(name);before=out/'before'/name
        before.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,before)
work.setdefault('repair_history',[]).append(work['repair'])
evidence=[out/'workflow-polling-before-result.json',out/'workflow-polling-before-profile.txt',
          out/'duration-full-trace-analysis.json',root/'backend/test-output/release-gates/duration-intent-d7d049e2b8d6/860f9d4a7375/receipt.json']
work['repair']={
 'finding_ids':['REPEATED_WORKFLOW_STATUS_GRAPH_DECODING'], 'owner':'PROJECT_PRODUCT',
 'category':'IMPLEMENTATION','cause':'FULL_JSON_DECODE_AND_REPEATED_SIGNAL_SCAN',
 'root_cause':'The unchanged20-minute large case times out during workflow status polling although the eventual server assessment has766PASS and full signal coverage. Frozen isolated profiling gives identical results on three reads but2.031s of2.538s in repeated source artifact checks: full message JSON decode, full hardware rows and a route-by-signal scan. The status checks consume only transmission/transport contracts, canonical channel columns and ID links; unrelated configuration is repeatedly decoded. Parameter validation also repeatedly enumerates the same registry keys per network.',
 'first_failing_layer':'Repeated workflow source-artifact reads under large wizard execution',
 'reproduction':'FAIL receipt860f9d4a7375 real1200000ms timeout at readProject;543summaryGETs. Isolated frozen replay with552hardware,653messages,1404signals,766routes has1.114/0.702/0.736s reads and identical stateSHA d3adb4cb8f9fbbb92668c368c41549307c6eeae726ab7edfab2a82944474cc88.',
 'affected_files':files,'affected_services':['WorkflowStatusService source reconciliation','Shared ID-based simulation coverage'],
 'required_fix':'Project only consumed canonical JSON fields and physical channel columns at SQL read boundaries, preserving malformed types and explicitnull versus absent transport semantics. Build one ID-based child index for coverage and hoist stable native registry key enumeration. No result cache, no narrower inventory, no removed checks or changed timeout budgets.',
 'acceptance_criteria':['Frozen full workflow state and all checks are byte-equivalent before/after on three repeated reads',
 'Missing/native invalid parameters, malformed transmission contracts, explicitnull transport data and authored outdated routes stay strict',
 'ALL/SELECTED/directIO/partial signal transport coverage and exclusions remain exact',
 'Full large wizard completes allnine stages with766evaluatedPASS under its existing20-minute bound',
 'No added live API probes during timing-sensitive full rounds; status comes from existing test logs',
 'Deploy only the completePASS exactimage and preserve the human pendingproposal/run/projectvalues'],
 'targeted_tests':['Isolated frozen profile before/after equivalence','Workflow/coverage/unused-output SQL regressions','Full unchanged release gate and production delivery'],
 'regression_scope':'Canonical workflow source artifacts, native parameter validation and ID-based transport scope',
 'evidence':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in evidence],
 'weaken_assertions_to_pass':False,'status':'READY'}
work['revision_before']={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in work['files_inspected']}
work['completion_status']='REPAIR_PLANNED'
path.write_text(json.dumps(work,indent=2),encoding='utf-8')
print('Measured workflow polling repair planned; latest full round has ended.')
