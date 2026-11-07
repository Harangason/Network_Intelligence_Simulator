"""Preserve phase-one evidence and bind the now proven empty-clause failure."""
import hashlib
import json
from pathlib import Path
import shutil

out=Path(__file__).resolve().parent
root=out.parents[2]
directory=out/'intake-cardinality-repair'
def ref(path):
    return {'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
archive=directory/'freeze-01'
assert not archive.exists()
archive.mkdir()
for name in ['source-scope-proof.json','change.diff']:
    shutil.copy2(directory/name,archive/name)
shutil.copytree(directory/'after',archive/'after')
name='backend/nis/agent/orchestration/project_intake.py'
target=directory/'before'/name
target.parent.mkdir(parents=True,exist_ok=True)
assert not target.exists()
target.write_bytes((root/name).read_bytes())
path=out/'workload.json'
work=json.loads(path.read_text(encoding='utf-8'))
for filename,digest in work['frozen_files'].items():
    assert ref(root/filename)['sha256']==digest
work['files_changed'].append(name)
work['files_inspected'].append(name)
work['before'].append(ref(target))
work['revision_before']={filename:ref(root/filename)['sha256'] for filename in work['files_changed']}
work['repair']['affected_files']=work['files_changed']
work['repair']['root_cause'] += ' Second complete native attempt passed five sections then exposed four empty .F02 keys in section6: trailing delimiters in function bullets produce empty component clauses that the private schema permits and the unchanged public resolver correctly rejects. Pure full-window audit proves these four empty references are the only binding errors across all14 complete contiguous sections.'
work['repair']['evidence'] += [ref(out/'attempt-02/native-terminal-diagnostics.json'),ref(out/'attempt-02/prepared-source-audit.json')]
work['repair']['acceptance_criteria'] += ['Never offer an empty delimiter clause as hardware/function/requirement; preserve complete original source lines and literal citations','All prepared private references of the full unchanged source must project through the actual strict public resolver']
work['implementation_plan'].insert(0,'Remove only zero-character clauses created by list delimiters; independent delimiter and complete original private/public regression before another candidate')
path.write_text(json.dumps(work,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'PHASE_TWO_BOUND','files':work['files_changed'],'previous_freeze_preserved':str(archive)}))
