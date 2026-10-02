from pathlib import Path
import hashlib,json,logging,httpx,zipfile
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
f=Path('work/ocpp-primary');m=[]
sources=[('v21-errata','https://openchargealliance.org/download/a164930cec4d71ccc0801617091a291fd833fdebfb682ec65c659b23e085d749'),('v201-errata','https://openchargealliance.org/download/46b1a248048c0221159baf9f5947af523110728e8666795a4c757bb868dd38ac')]
with httpx.Client(timeout=60,follow_redirects=True)as c:
 for name,url in sources:
  p=f/(name+'.zip')
  if not p.exists():r=c.get(url);r.raise_for_status();p.write_bytes(r.content)
  e=dict(name=name,url=url,path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
  with zipfile.ZipFile(p)as z:
   e['members']=z.namelist()
   for member in z.namelist():
    if not member.lower().endswith('.pdf'):continue
    target=(f/name/member).resolve();assert target.is_relative_to((f/name).resolve()),member
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(member))
    reader=PdfReader(target);pages=target.parent/(target.stem+'-pages');pages.mkdir(exist_ok=True)
    for i,page in enumerate(reader.pages,1):(pages/f'{i:04}.txt').write_text(page.extract_text()or'',encoding='utf-8')
  m.append(e);print(json.dumps(e),flush=True)
(f/'errata-manifest.json').write_text(json.dumps(m,indent=2)+'\n')
