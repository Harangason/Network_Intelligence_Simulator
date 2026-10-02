from pathlib import Path
import json,hashlib,httpx
root=Path('work/opc-ua-primary');manifest=json.loads((root/'manifest.json').read_text())
def save(r,name):
 r.raise_for_status();path=root/name;path.write_bytes(r.content)
 manifest.append(dict(url=str(r.url),path=str(path).replace('\\','/'),sha256=hashlib.sha256(r.content).hexdigest(),bytes=len(r.content)))
 return r.json()
with httpx.Client(timeout=40,follow_redirects=True)as c:
 for id in(2278,1530,913,2101,2078):
  result=save(c.get(f'https://profiles.opcfoundation.org/api/profile/get/{id}'),f'profile-{id}.json')
  print(id,str(result)[:1300],flush=True)
(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
