"""Bind the proven intake failure to the smallest general product repair."""
import hashlib
import json
from pathlib import Path

out = Path(__file__).resolve().parent
root = out.parents[2]
work_path = out/'workload.json'
work = json.loads(work_path.read_text(encoding='utf-8'))
files = ['backend/nis/agent/orchestration/local_reasoner.py','backend/tests/test_qwen_document_intake.py']
def ref(path):
    return {'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
before = []
for name in files:
    target = out/'intake-cardinality-repair/before'/name
    target.parent.mkdir(parents=True,exist_ok=True)
    assert not target.exists()
    target.write_bytes((root/name).read_bytes())
    before.append(ref(target))
work.update(kind='repair',status='REPAIRING',files_inspected=files+['backend/nis/agent/orchestration/project_intake.py'],
            files_changed=files,before=before,revision_before={name:ref(root/name)['sha256'] for name in files})
work['repair'] = {'owner':'PROJECT_PRODUCT','first_failing_layer':'Private document decoder cardinality versus lossless section preparation',
    'root_cause':'First actual neu9 payload has 23 required component references but 25 permitted keys. The splitter checks only required count<=24; native output reaches the correct runtime >24 rejection despite declared maxProperties24. A grammar that permits more selectable keys than the public limit is not intrinsically bounded across providers.',
    'reproduction':'Real llama3.1:8b normal terminal INVALID_INPUT after correction, driver36954 Exit1, worker idle. Fake transport reconstructs the unchanged first payload: required23/possible25/max24, no inference. Exact last native raw answer unavailable; do not invent its selection.',
    'evidence':[ref(out/'intake/response.json'),ref(out/'intake-terminal-and-schema-gap.json')],
    'affected_files':files,'acceptance_criteria':['Bound every selectable private component key set to24 via complete contiguous source sections; preserve all source characters and requirements','Keep public limit24 and existing technology/context/output/timeout/identity/review gates unchanged for every configured model','Save terminal invalid document raw answer and hash for diagnosis, never accept it as a model'],
    'targeted_tests':['backend/tests/test_qwen_document_intake.py'], 'weaken_assertions_to_pass':False}
work['implementation_plan']=['Add independent synthetic and preserved complete source cardinality RED cases and terminal diagnostic RED case','Bound all decoder keys through lossless section subdivision, add terminal-only raw response diagnostic','Targeted GREEN and isolated adjacent regression, then fresh coordinated actual small-model probe','Retire current isolated stack recoverably, freeze changed app identity and prepare one normal matching image','Repeat complete unchanged neu9+25LIN through native review/apply and successful ALL simulation','Required complete release gate and exact tested-image production delivery; five prior preview outcomes remain historical']
work['delivery']={'decision':'YES','authorization':'Standing explicit canonical AGENTS.md exact verified-image production delivery','target':'Canonical NetworkIS production stack','status':'PENDING_REPAIR_AND_FULL_NATIVE_ACCEPTANCE'}
work_path.write_text(json.dumps(work,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':work['status'],'files':files,'required_outcomes':len(work['required_outcomes']),'validations':len(work['validation_requirements'])}))
