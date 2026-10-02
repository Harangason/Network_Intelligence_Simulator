from pathlib import Path
import hashlib,json,logging,httpx,zipfile
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
f=Path('work/ocpp-primary');f.mkdir(exist_ok=True)
sources=[('v21','https://openchargealliance.org/download/f6531d9fc45e3603186edb68e78b11c281b260f71af967330aaa611bda4888da'),('v201','https://openchargealliance.org/download/caaab79c63336ff203104d9940c8eba29adb7d324c384e0578f7f3b7265e03ac'),('v16','https://openchargealliance.org/download/7b06ab293c68fb6b4f4ae0960e502579c1c5516aa2b7acf0fdcedba585b9ea7f')]
m=[]
with httpx.Client(timeout=60,follow_redirects=True)as c:
 for name,url in sources:
  p=f/(name+'.zip')
  if not p.exists():r=c.get(url);r.raise_for_status();p.write_bytes(r.content)
  e=dict(name=name,url=url,path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
  with zipfile.ZipFile(p)as z:
   e['members']=z.namelist()
   for member in z.namelist():
    if not member.lower().endswith(('.pdf','.json','.xsd')):continue
    target=(f/name/member).resolve()
    assert target.is_relative_to((f/name).resolve()),member
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(member))
    if target.suffix.lower()=='.pdf':
     reader=PdfReader(target);pages=target.parent/(target.stem+'-pages');pages.mkdir(exist_ok=True)
     for i,page in enumerate(reader.pages,1):(pages/f'{i:04}.txt').write_text(page.extract_text()or'',encoding='utf-8')
  m.append(e);print(json.dumps(e),flush=True)
(f/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
