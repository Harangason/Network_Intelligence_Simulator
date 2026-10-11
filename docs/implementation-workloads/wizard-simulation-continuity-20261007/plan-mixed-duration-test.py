import hashlib,json,shutil
from pathlib import Path
out=Path(__file__).parent.resolve();root=out.parents[2];path=out/'workload.json'
work=json.loads(path.read_text(encoding='utf-8'))
history=out/'before-mixed-duration-test'
history.mkdir(exist_ok=True)
for name in ('duration-intent-browser.json','duration-intent-browser.log','duration-intent-browser-cleanup.json'):
    shutil.copyfile(out/name,history/name)
failure=history/'duration-intent-browser.json'
work['repair'].setdefault('test_corrections',[]).append({
 'owner':'TEST_DATA','first_failing_layer':'New mixed-project E2E duration assertion',
 'root_cause':'The existing fixture has CAN-FD as primary but edits Ethernet in a mixed project. confirmTechnologyParameters intentionally stores secondary protocol values in technology_parameters. It must not invent or overwrite a global primary duration. The new assertion incorrectly required global duration provenance that this fixture never saved. The independent primary CAN-FD same-value duration intent case passed.',
 'required_fix':'Assert the original global duration and provenance are unchanged from the saved fixture, while Ethernet scoped duration is saved as1; retain all existing native persistence and central-default protection checks.',
 'evidence':{'path':str(failure),'sha256':hashlib.sha256(failure.read_bytes()).hexdigest()},
 'weaken_existing_assertions':False})
work['revision_before']={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in work['files_inspected']}
path.write_text(json.dumps(work,indent=2,ensure_ascii=False),encoding='utf-8')
print('Reloaded revisions; planned correction of the newly added mixed-project assertion only.')
