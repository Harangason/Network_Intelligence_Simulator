import json,subprocess
from pathlib import Path
root=Path.cwd();docker=json.loads((root/'config/networkis.resources.json').read_text())['paths']['docker_cli']
def call(*a):return subprocess.check_output([docker,*a],text=True).strip()
ids=call('ps','-aq','--no-trunc').split();containers=json.loads(call('inspect',*ids)) if ids else [];used={c['Image'] for c in containers}
images=[json.loads(l) for l in call('image','ls','--no-trunc','--format','{{json .}}','networkis').splitlines()]
receipts={}
for parent in (root/'backend/test-output',root/'work'):
 for p in parent.rglob('receipt.json'):
  try:r=json.loads(p.read_text(encoding='utf-8-sig'))
  except (OSError,ValueError):continue
  if r.get('image_id'):receipts.setdefault(r['image_id'],[]).append({'path':str(p),'status':r.get('status')})
result={'production':call('inspect','NetworkIS','--format','{{.Image}}'),'containers':[{'name':c['Name'],'image':c['Image']} for c in containers],'candidates':[]}
for row in images:
 r=receipts.get(row['ID'],[])
 if row['ID'] not in used and row['Tag'].startswith('candidate-') and r and all(x['status']=='FAIL' for x in r):result['candidates'].append({'image_id':row['ID'],'tag':row['Repository']+':'+row['Tag'],'receipts':r,'created':row['CreatedAt']})
out=root/'docs/implementation-workloads/large-document-intake-20261016/cleanup-inventory.json';out.write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'production':result['production'],'eligible_fail_candidates':result['candidates'][:8]}))
