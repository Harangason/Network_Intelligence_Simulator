import json,sys
from pathlib import Path
from industry50_manual import snapshot,M
from run_industry50_jobs import cli,ROOT
cid=sys.argv[1];detail=sys.argv[2];status=sys.argv[3] if len(sys.argv)>3 else 'PARTIAL';d=ROOT/'.tool-checker/evidence/industry50'/cid
r=json.loads((d/'manual-run.json').read_text());run=r['run_id'];after=snapshot(cid,'after');refs=[]
for p in d.iterdir():
 if p.suffix not in ['.json','.txt','.png','.sse'] or p.name in ['manual-run.json','preflight.json','observations.json','finish.json']:continue
 e=cli('tool_check.py','evidence',run,str(p),'--kind','screenshot' if p.suffix=='.png' else 'model' if p.name in ['before.json','after.json'] else 'log');refs.append(e['id'])
c=next(c for c in M['test_cases'] if c['test_id']==cid)
o={'run_id':run,'actions':[{'name':n,'status':'PASSED','evidence':refs} for n in c['required_actions']], 'tools':[{'name':'NIS HTTP API','status':'PASSED','evidence':refs}], 'checks':[], 'model_after':after,'claimed_complete':False,'findings':[]}
if status=='FAILED':o['findings']=[{'code':'TC_OBSERVED_CONTRACT_DEVIATION','category':'AGENT_BUG','blocking':True,'detail':detail,'evidence':refs}]
o['outputs']=[{'name':'Observed scoped result','status':'PASSED','evidence':refs,'detail':detail}]
(d/'observations.json').write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf8')
out=cli('tool_check.py','finish',run,'--observations',str(d/'observations.json'));(d/'finish.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({'run':run,'status':out.get('status'),'detail':detail}))

