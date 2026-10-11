import json,pathlib,re
p=pathlib.Path('backend/test-output/release-gates/delivery-488ac00bf2cd/b106f2e968ff')
r=json.loads((p/'receipt.json').read_text())
print('GATE',json.dumps({k:r.get(k) for k in ['status','checks','error','image_id','base_url']},ensure_ascii=False))
completed={item['name'] for item in r.get('checks',[]) if item.get('exit_code')==0}
for name,n in [('backend-tests',200),('production-build',250),('browser-e2e',350),('small-http',300),('large-http',300)]:
 if name in completed: continue
 f=p/(name+'.log')
 if f.exists():
  t=f.read_text(encoding='utf-8',errors='replace');percent=re.findall(r'\[\s*(\d+)%\]',t);print(name,(percent[-1]+'%' if percent else ''),t[-n:].replace('\n',' '))
