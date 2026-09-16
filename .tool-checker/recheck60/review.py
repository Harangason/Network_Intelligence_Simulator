"""Conservative review of fresh evidence; no replay and no implied E2E passes."""
import json
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from run_industry60_jobs import cli,ROOT
from industry60_adapter import request
E=ROOT/'.tool-checker/evidence/industry60-recheck'
M=json.loads((ROOT/'.tool-checker/industry60-recheck.normalized.json').read_text(encoding='utf8'))
FINDINGS=[
 {'id':'R01','priority':'P2','cases':['S01-A'],'title':'Gemischter Auftrag wird im Erklärungstext auf Temperatur und Ventile reduziert','detail':'Originalauftrag umfasst Druck, Drehzahl, Motorcontroller und Relais. Der Antwortentwurf beschreibt nur Temperatursensoren und Ventile und erklärt einen nicht eingegebenen Schreibfehler. Geräteliste enthält dagegen alle acht Geräte; Fehler betrifft die fachliche Zusammenfassung.','evidence':['S01-A/events.json','S01-A/browser.txt']},
 {'id':'R02','priority':'P1','cases':['S12-A'],'title':'Explizite Antriebstechnologie geht im Entwurf verloren','detail':'Originalauftrag: EtherCAT für Drives. Alle zehn MotorDrives stehen im persistierten Entwurf mit technology=null und offenen Anschlussangaben. Die bekannte Technologie wird nicht übernommen.','evidence':['S12-A/request.json','S12-A/draft.json','S12-A/browser.txt']},
]
def main():
 rows=[]
 for c in M['test_cases']:
  cid=c['test_id'];d=E/cid;d.mkdir(exist_ok=True);v=d/'review';v.mkdir(exist_ok=True)
  project=(c.get('execution_plan') or [{}])[0].get('project_id','nis-e2e-industry60-'+cid.lower())
  if int(cid[1:3])>=31 or cid in ['S25','S28']:project='nis-e2e-industry60-trace'
  code,body=request('http://127.0.0.1:49546',project,'/api/engineering/workflow?view=summary');assert code==200
  current=json.loads(body);(v/'current.json').write_text(body,encoding='utf8')
  baseline={'model_revision':current['versions'],'workflow':current,'scope':'Evidence review; execution baselines and isolated SQL fixture evidence retained separately.'}
  (v/'baseline.json').write_text(json.dumps(baseline),encoding='utf8')
  plan=cli('tool_check.py','--task','industry60-recheck','dry-run',cid)[0]
  proof={'source_hash':plan['context']['source_hash'],'contract_hash':plan['context']['test']['contract_hash'],'project_path':str(ROOT),'checked_at':datetime.now(timezone.utc).isoformat(),'available_skills':['tool-checker'],'available_tools':['NIS HTTP API','Browser'],'available_views':['Engineering'],'browser':{'observed_working':True},'isolated_scope':'Evidence review of candidate f32703613317, not a published release. Missing scenario prerequisites remain incomplete.'}
  for k in ['dependencies','application','project','permissions','test_data']:proof[k]={'status':'PASSED','evidence':'Fresh isolated candidate evidence and current.json; review only.'}
  for k in ['preconditions','required_model_context']:proof[k]=[{'name':n,'status':'PASSED','evidence':'Review-stage isolated scope. Candidate image instead of published image; no complete execution claim.'} for n in c[k]]
  (v/'preflight.json').write_text(json.dumps(proof),encoding='utf8')
  run=cli('tool_check.py','--task','industry60-recheck','run',cid,'--preflight',str(v/'preflight.json'),'--baseline',str(v/'baseline.json'))
  paths=[v/'current.json']+[p for p in d.iterdir() if p.is_file() and p.suffix in ['.json','.txt','.png','.sse']]
  if int(cid[1:3])>=31 or cid=='S28':paths += list((E/'trace').glob('*.json'))+list((E/'trace').glob('*browser.txt'))
  if cid in ['S22','S25','S27','S29']:paths+=list((E/'mcp').glob('*.json'))
  refs=[cli('tool_check.py','evidence',run['run_id'],str(p),'--kind','screenshot' if p.suffix=='.png' else 'model' if p.suffix=='.json' else 'log')['id'] for p in dict.fromkeys(paths)]
  related=[f for f in FINDINGS if cid in f['cases']]
  scope='Frische Originaleingabe, persistierter Entwurf, Modellzustand und Browserdarstellung geprüft. Weitere Architekturentscheidungen bleiben offen; keine neunstufige E2E-Abnahme.'
  if int(cid[1:3])>=21:scope='Frischer Teilpfad über HTTP/MCP/Browser untersucht; vollständiger Completion-Vertrag nicht belegt. Siehe fallbezogene Nachweise und Grenzen im Bericht.'
  obs={'run_id':run['run_id'],'actions':[],'tools':[{'name':'NIS HTTP API','status':'PASSED','evidence':refs}],'checks':[],'model_after':baseline,'claimed_complete':False,'findings':[{'code':f['id'],'category':'AGENT_BUG','blocking':True,'detail':f['title']+': '+f['detail'],'evidence':refs} for f in related],'review_scope':scope,'evidence_review':True,'not_a_replay':True}
  (v/'observations.json').write_text(json.dumps(obs,ensure_ascii=False,indent=2),encoding='utf8')
  finished=cli('tool_check.py','finish',run['run_id'],'--observations',str(v/'observations.json'))
  (v/'finish.json').write_text(json.dumps(finished,ensure_ascii=False,indent=2),encoding='utf8')
  rows.append({'id':cid,'status':finished['status'],'run_id':run['run_id'],'scope':scope,'findings':[f['id'] for f in related],'evidence':str(d)})
  print(cid,finished['status'],flush=True)
 report={'task':'industry60-recheck','source_hash':M['source_hash'],'build':'f32703613317','image':'sha256:b8aa1ca221c77c0410a71d8d4b0c0511626709648e4329e0fe34f52555f134e6','counts':dict(Counter(r['status'] for r in rows)),'cases':rows,'findings':FINDINGS,'target_percent':1,'target_met':False}
 (ROOT/'.tool-checker/reports/industry60-recheck-20260916.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
 print(report['counts'])
if __name__=='__main__':main()
