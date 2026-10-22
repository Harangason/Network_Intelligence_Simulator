import json,hashlib
from copy import deepcopy
from datetime import datetime,timezone
from backend.nis.agent.tools import conversation,model
from backend.nis.agent.tools.project_draft import DraftCommand
from backend.nis.agent.tools.runtime import ToolAuthority,execute
from backend.nis.agent.api.tool_contract import Permission
EXPECTED_STATE='32d141e32b34fda8d4f65fc9816ff6c41b582a23dc07ba4eaccecaaad2c93585'
EXPECTED_MODEL='1f3dfc87c176e353f4d425fad9d1c8a9093d3d92d9e78a00148b0e84029943c2'
DRAFT='5fa5f2c0-42e2-44a2-ba19-bbb226d0f5c5'
TEXT='Zeige mir deine F\u00e4higkeiten.'
def sha(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
def undo(args):
 state=conversation.read()
 assert sha(state)==EXPECTED_STATE,'Conversation changed; no write allowed'
 assert model.model_revision()==EXPECTED_MODEL,'Model changed; no write allowed'
 counts={k:len(model.objects(v)) for k,v in model.SECTIONS.items()}
 assert not any(counts.values()),'Expected empty canonical model'
 assert state.get('run_id') is None and state.get('active_proposal') is None
 assert not state.get('pending_approvals') and state.get('active_workload') is None
 lease=state.get('lease_until')
 assert not lease or datetime.fromisoformat(lease)<datetime.now(timezone.utc),'Active run lease'
 workload=state.get('engineering_workloads',{}).get(state.get('active_engineering_workload_id'),{})
 assert workload.get('status')=='BLOCKED_WITH_EXPLICIT_CAUSE'
 assert workload.get('goal',{}).get('original_request')==TEXT
 original=deepcopy(state)
 draft=state['engineering_draft']
 assert draft['draft_id']==DRAFT and draft['revision']==1 and draft['devices']==[]
 assert draft['original_requirement']==TEXT and draft['industry'] is None
 assert draft['status']=='NEEDS_DECISION'
 assert not any(draft.get(k) for k in ('pending_model_confirmation','model_confirmation','model_proposal_id'))
 sources=draft['sources']; assert len(sources)==1 and sources[0]['text']==TEXT and sources[0]['source']=='USER'
 opid=sources[0]['operation_id']
 assert draft['edits']==[{'action':'CREATE','devices':[],'industry':None,'revision':1,'operation_id':opid,'remove_device_ids':[]}]
 command=DraftCommand(action='CREATE',operation_id=opid,revision=None,requirement=TEXT)
 signature=hashlib.sha256(json.dumps(command.model_dump(mode='json'),sort_keys=True).encode()).hexdigest()
 op=state['engineering_draft_operations'][opid]
 assert op['signature']==signature and op['result']['draft']==draft
 assert op['result']['receipt']=={'accepted':True,'revision':1,'operation_id':opid}
 archive=state.setdefault('engineering_draft_archive',{})
 assert DRAFT not in archive,'Archive already exists; stop for review'
 archive[DRAFT]=deepcopy(draft)
 state.pop('engineering_draft')
 expected=deepcopy(original)
 expected.setdefault('engineering_draft_archive',{})[DRAFT]=deepcopy(draft)
 expected.pop('engineering_draft')
 assert state==expected
 conversation.write(state)
 actual=conversation.read()
 assert actual==expected,'Unexpected persisted state; rollback'
 assert model.model_revision()==EXPECTED_MODEL,'Unexpected model mutation; rollback'
 return {'status':'ARCHIVED_AND_DEACTIVATED','draft_id':DRAFT,'state':actual,'before_state_sha256':EXPECTED_STATE,'state_sha256':sha(actual),'model_revision':EXPECTED_MODEL,'model_counts':counts,'other_state_preserved':True,'create_signature_verified':signature}
r=execute(ToolAuthority('20261014090941894-67ae8896',actor='codex-smoke-undo'),'restore_accidental_empty_smoke_draft',Permission.GENERATE_PROPOSAL,{'expected_state_sha256':EXPECTED_STATE,'expected_draft_id':DRAFT},undo)
print(json.dumps(r.model_dump(mode='json'),ensure_ascii=True))
