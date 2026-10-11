import hashlib,json,shutil
from pathlib import Path
out=Path(__file__).parent.resolve();root=out.parents[2];path=out/'workload.json'
work=json.loads(path.read_text(encoding='utf-8'))
files=['frontend/src/features/agent/ui/agent-chat-core.tsx','frontend/src/features/agent/lib/proposal-client.ts','frontend/src/features/agent/lib/proposal-client.test.mjs']
for name in files:
    if name not in work['files_inspected']:
        work['files_inspected'].append(name);before=out/'before'/name
        before.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,before)
work.setdefault('repair_history',[]).append(work['repair'])
proof=out/'return-network-diagnostic.json'
work['repair']={'finding_ids':['REPEATED_STALE_FULL_PROPOSAL_READS'],
 'owner':'PROJECT_PRODUCT','category':'IMPLEMENTATION','cause':'DUPLICATE_WIZARD_REVIEW_TRANSFER',
 'root_cause':'WizardModelReview fetches the entire stale proposal on mount and every5s; its child separately restores the same proposal. The captured topology return transfers stale full bodies for10s and7s before starting validation, while repeated parent full reads contend with validation. Two prior validations complete in28/29s; the third starts18s into the unchanged60s return window and is aborted by the timeout. Pure parameter review takes14s under profiling.',
 'first_failing_layer':'Parent wizard proposal loading and polling',
 'reproduction':'Captured real browser trace shows full GETs15:36:55 and15:37:08, then validationPOST15:37:09 pending at15:37:52 timeout.',
 'affected_files':files,
 'evidence':[{'path':str(proof),'sha256':hashlib.sha256(proof.read_bytes()).hexdigest()}],
 'acceptance_criteria':['Restore current status before downloading body; OUTDATED goes straight to current validation, never stale body',
   'Use the existing proposal client for parent loading and compact polling; current full contents and identity remain attached to matching revisions only',
   'Changed active proposal IDs or revisions must fetch their actual full body; malformed or incomplete validation still rejects',
   'Preserve wizard run identity, manual approval/application and all60/240/180/1200-second budgets',
   'Regression verifies repeated matching polls issue only compactGETs and one OUTDATED validationPOST with no approval/application calls'],
 'targeted_tests':['proposal-client nativefrontend tests','typecheck','all eight realbrowser cases and fullrelease gate'],
 'weaken_assertions_to_pass':False,'status':'READY'}
work['revision_before']={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in work['files_inspected']}
work['completion_status']='REPAIRING';path.write_text(json.dumps(work,indent=2),encoding='utf-8')
print('Status-first parent loading and compact proposal polling planned.')
