import json,re,urllib.request,pathlib
root=pathlib.Path(__file__).resolve().parent
gate=pathlib.Path('backend/test-output/release-gates/delivery-598e574496cb/54a8f70a0299')
r=json.loads((gate/'receipt.json').read_text())
print('GATE',json.dumps({'status':r['status'],'checks':r['checks'],'error':r.get('error')},ensure_ascii=False))
p=gate/'backend-tests.log'
if p.exists():
 t=p.read_text(encoding='utf-8',errors='replace'); percentages=re.findall(r'\[\s*(\d+)%\]',t); print('BACKEND', percentages[-1]+'%' if percentages else 'starting',t[-220:].replace('\n',' '))
p=root/'targeted-browser.log'
if p.exists(): print('BROWSER',p.read_text(encoding='utf-8',errors='replace')[-700:])
prep=json.loads((root/'prepared/efa53ff9fe54/receipt.json').read_text())
try:
 projects=json.load(urllib.request.urlopen(prep['base_url']+'/api/engineering/projects',timeout=5))['items']
 if projects:
  project=projects[0]['project_id']; d=json.load(urllib.request.urlopen(urllib.request.Request(prep['base_url']+'/api/engineering/workflow?view=summary',headers={'X-Project-ID':project}),timeout=5)); e=d.get('context',{}).get('agent_execution',{}); print('TARGET',json.dumps({'project':project,'active_step':d['active_step'],'done':sum(v in ['COMPLETE','APPROVED','WARNING'] for v in d['statuses'].values()),'state':e.get('state'),'message':e.get('message','')[:150]},ensure_ascii=False))
except Exception as e: print('TARGET_READ',type(e).__name__)
