"""Keep a distinct workload and preserve pre-existing uncommitted revisions."""
from pathlib import Path
import hashlib
import json
import sys

root=Path(__file__).resolve().parents[1]
folder=root/'docs/implementation-workloads/source-directory-20261003'
folder.mkdir(parents=True,exist_ok=True)
path=folder/'workload.json'
data=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {
 'goal_id':'source-directory-20261003','goal_type':'implementation','kind':'implementation',
 'repository':str(root),'project_scope':'Canonical NIS source bibliography and scoped license controls',
 'requested_change':'Searchable deduplicated sortable sources, accurate publication rights and visible enforced technology license clearance.',
 'modify_code':True,'allow_repair':True,
 'constraints':['TechnologyRegistry is canonical','No fabricated access dates or license permissions','No copyrighted source document redistribution','Preserve project data','Exact PASS image delivery'],
 'required_outcomes':['source_directory','rights_review','license_control','production_delivery','documentation'],
 'validation_requirements':['backend','frontend','browser','full_release','live'],
 'forbidden_changes':['Overwrite prior technology audit','Prune historical images','Tests on product SQL database'],
 'unresolved_decisions':[], 'revision_before':{},'files_created':[],
 'context':['User requests source directory in main navigation and explicit licensing distinction.'],
 'implementation_plan':['Derive sources from registered profiles; preserve identity and versions','Record rights decisions with evidence and unresolved status','Sortable searchable accessible directory','Server-enforced scoped clearance, no self-approval endpoint','Tests, exact release and live delivery'],
 'files_inspected':[],'completion_status':'IMPLEMENTING','remaining_findings':[]}
for relative in sys.argv[1:]:
 source=root/relative
 before=folder/'before'/relative
 if not before.exists():
  before.parent.mkdir(parents=True,exist_ok=True)
  before.write_bytes(source.read_bytes() if source.exists() else b'')
 data['revision_before'][relative]=hashlib.sha256(source.read_bytes()).hexdigest() if source.exists() else None
 if not source.exists() and relative not in data['files_created']: data['files_created'].append(relative)
path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
