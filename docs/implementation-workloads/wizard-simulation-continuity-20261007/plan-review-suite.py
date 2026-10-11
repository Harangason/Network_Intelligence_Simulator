import hashlib,json,shutil
from pathlib import Path
out=Path(__file__).parent.resolve(); root=out.parents[2]
path=out/'workload.json'; work=json.loads(path.read_text(encoding='utf-8'))
affected=['frontend/e2e/wizard.spec.ts']
for name in [*affected,'frontend/src/features/agent/lib/wizard-progress-watchdog.test.mjs']:
    if name not in work['files_inspected']:
        work['files_inspected'].append(name)
        before=out/'before'/name; before.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(root/name,before)
work.setdefault('repair_history',[]).append(work['repair'])
evidence=[out/'before-review-suite-catalog-browser.json',out/'before-review-suite-catalog-browser.log',
    root/'docs/WIZARD_RELEASE_GATE.md']
work['repair']={'finding_ids':['EXPANDED_CONTINUITY_CASE_BUDGET'],'owner':'TOOL_CHECKER',
    'category':'TEST_INTEGRATION','cause':'ADDED_MANUAL_REPETITIONS_SHARE_FULL_WORKFLOW_CASE',
    'root_cause':'The original full nine-stage browser has an unchanged contractually required 20-minute case limit. Adding 27 complete save/reload/return loops to it consumes the entire case before remaining workflow execution. Candidate 27 passes individual model/routing/topology readiness; the latest failure is the outer 1,200,000ms test timer in a verification read, not a proposal readiness assertion.',
    'first_failing_layer':'Browser case workload partition',
    'reproduction':'Four smaller cases pass; large reaches topology repeated returns and hits whole-test 20-minute timer after all model/routing detours and several topology returns.',
    'evidence':[{'path':str(file),'sha256':hashlib.sha256(file.read_bytes()).hexdigest()} for file in evidence],
    'affected_files':affected,
    'acceptance_criteria':['Keep the full real nine-stage test, unchanged fixture/1404 signals/encodings/ALL-scope evidence/restart/assertions and 20-minute limit',
        'Keep one complete three-bus save/reload/return cycle at each proposal phase in that full test',
        'Add a separate real captured large case for each model/routing/topology pending review, each preserving all original nine repeated returns (three seeds times three buses)',
        'Explicitly label these three cases as review-only coverage, never nine-stage success',
        'Total repeated return coverage grows from 27 to 36; each case retains 20 minutes, each return 60 seconds and automatic progress/write deadlines unchanged',
        'Retain independent negative watchdog regressions proving forbidden timer resets still fail',
        'No application change or fixture/model writes via hidden repair; reuse the exact candidate image for changed verification inputs'],
    'targeted_tests':['frontend wizard progress watchdog clock regressions','eight-case browser scope: native defaults, small full nine-stage, two strict native negatives, large full nine-stage, three large review-only continuity cases'],
    'weaken_assertions_to_pass':False,'status':'READY'}
work['revision_before']={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in work['files_inspected']}
work['remaining_findings']=['Complete eight-case review/full-workflow scope and full release gate pending','Exact production delivery pending']
work['completion_status']='REPAIRING'
path.write_text(json.dumps(work,indent=2,ensure_ascii=False),encoding='utf-8')
print('Preserve full workflow and every deadline; add separate review-only cases with more return coverage.')
