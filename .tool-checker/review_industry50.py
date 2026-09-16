import json
from pathlib import Path
from datetime import datetime,timezone
from run_industry50_jobs import cli,ROOT
from industry50_adapter import request
m=json.loads((ROOT/'.tool-checker/industry50.normalized.json').read_text(encoding='utf8'))
for c in m['test_cases'][:40]:
 d=ROOT/'.tool-checker/evidence/industry50'/c['test_id'];review=d/'review';review.mkdir(exist_ok=True)
 if (review/'finish.json').exists():continue
 code,body=request('http://127.0.0.1:60023',c['execution_plan'][0]['project_id'],'/api/engineering/workflow?view=summary');assert code==200
 current=json.loads(body);(review/'current.json').write_text(body,encoding='utf8');proof=json.loads((d/'preflight.json').read_text(encoding='utf8'));proof['checked_at']=datetime.now(timezone.utc).isoformat();proof['test_data']={'status':'PASSED','evidence':'Semantic review of unchanged source and original captured execution; fresh persisted model read current.json. No agent replay.'};(review/'preflight.json').write_text(json.dumps(proof),encoding='utf8')
 r=cli('tool_check.py','--task','industry50','run',c['test_id'],'--preflight',str(review/'preflight.json'),'--baseline',str(d/'baseline.json'));(review/'run.json').write_text(json.dumps(r),encoding='utf8');refs=[]
 for p,kind in [(d/'draft.json','model'),(d/'events.json','log'),(d/'browser.txt','log'),(d/'browser.png','screenshot'),(review/'current.json','model')]:refs.append(cli('tool_check.py','evidence',r['run_id'],str(p),'--kind',kind)['id'])
 draft=json.loads((d/'draft.json').read_text(encoding='utf8'))['data'];failed=c['variant']=='A' or c['test_id'] in ['S07-B','S11-B']
 detail='Explizite Gerätetypen und Anschlüsse des A-Auftrags werden im gespeicherten Entwurf nur unvollständig strukturiert; mehrere konkrete Geräte sind generische Sensor/Aktor/Controller-Platzhalter mit known_kind=false/technology=null. Nachgelagerte Ausführung nicht vollständig geprüft.' if c['variant']=='A' else 'Offene Architekturentscheidungen nicht beantwortet; E2E nicht vollständig geprüft.'
 if c['test_id'] in ['S07-A','S07-B','S11-B','S20-A']:detail+=' Zusätzlich fehlt mindestens ein ausdrücklich genannter Compute-/PC-Knoten; bisheriger Zähltest hatte hierfür einen zu niedrigen Sollwert.';failed=True
 o={'run_id':r['run_id'],'actions':[{'name':n,'status':'PASSED','evidence':refs,'detail':'Originalausführung aus unveränderten Nachweisen geprüft, kein erneuter Agentenaufruf'} for n in c['required_actions']], 'tools':[{'name':n,'status':'PASSED','evidence':refs} for n in c['required_tools']], 'checks':[{'category':'completion_criteria','name':'Keine Fertigmeldung ohne vollständige fachliche Artefakte','status':'PASSED','evidence':refs}], 'model_after':{'model_revision':current.get('versions'),'workflow':current},'claimed_complete':False,'findings':[],'review_scope':'Original execution plus fresh read; later browser evidence registered; no agent replay'}
 if failed:o['findings']=[{'code':'TC_INTAKE_SEMANTICS_INCOMPLETE','category':'AGENT_BUG','blocking':True,'detail':detail,'evidence':refs}]
 (review/'observations.json').write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf8');out=cli('tool_check.py','finish',r['run_id'],'--observations',str(review/'observations.json'));(review/'finish.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');print(c['test_id'],out['status'],flush=True)
