from pathlib import Path
import hashlib,json,logging,httpx
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
f=Path('work/one-wire-primary');f.mkdir(exist_ok=True)
sources=[('temperature','https://www.analog.com/media/en/technical-documentation/data-sheets/ds18b20.pdf'),('bridge','https://www.analog.com/media/en/technical-documentation/data-sheets/DS2482-100.pdf'),('identity','https://www.analog.com/media/en/technical-documentation/data-sheets/DS1990A.pdf')]
m=[]
with httpx.Client(timeout=60,follow_redirects=True)as c:
 for name,url in sources:
  p=f/(name+('.pdf'if url.lower().endswith('.pdf')else'.html'))
  if not p.exists():r=c.get(url);r.raise_for_status();p.write_bytes(r.content)
  e=dict(name=name,url=url,path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
  if p.suffix=='.pdf':
   reader=PdfReader(p);pages=f/(name+'-pages');pages.mkdir(exist_ok=True)
   for i,page in enumerate(reader.pages,1):(pages/f'{i:03}.txt').write_text(page.extract_text()or'',encoding='utf-8')
   e['pages']=len(reader.pages)
  m.append(e);print(json.dumps(e),flush=True)
(f/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
