import json,re
from pathlib import Path
out=Path(__file__).parent;root=out.parents[2]
native=json.loads((out/'native-large-document.json').read_text(encoding='utf-8'))
receipt=root/'backend/test-output/release-gates/delivery-c74dcdfd5870/a1c086d28f4b/receipt.json'
r=json.loads(receipt.read_text(encoding='utf-8')) if receipt.exists() else {}
checks=r.get('checks',[]);completed={c['name'] for c in checks if c.get('exit_code')==0}
name=next((n for n in ['backend-tests','production-build','browser-e2e','small-http','large-http'] if n not in completed),'deployment')
log=receipt.parent/(name+'.log') if name!='deployment' else out/'release-and-deploy.log'
tail=''
if log.exists():
 with log.open('rb') as f:
  f.seek(max(0,log.stat().st_size-700));tail=f.read().decode('utf-8',errors='replace')
browser=receipt.parent/'browser-e2e.log'
text=re.sub(r'\x1b\[[0-9;]*m','',browser.read_text(encoding='utf-8',errors='replace')) if browser.exists() else ''
counts={'passed':len(re.findall(r'^\s*ok\s+\d+',text,re.M)),'failed':len(re.findall(r'^\s*(?:x|\u2718|\u00d7)\s+\d+',text,re.M))}
print(json.dumps({'browser_counts':counts,'native':{'status':native['status'],'calls':len(native.get('calls',[])),'error':native.get('error')},'release':{'status':r.get('status'),'passed_checks':[c['name'] for c in checks if c.get('exit_code')==0],'error':r.get('error'),'image':r.get('image_id')},'phase':name,'log_tail':tail},ensure_ascii=True))
