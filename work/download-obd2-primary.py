from pathlib import Path
import hashlib,json,logging,httpx
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
f=Path('work/obd2-primary');f.mkdir(exist_ok=True)
sources=[('elm','https://www.elmelectronics.com/wp-content/uploads/2017/01/ELM327DS.pdf'),('stn','https://www.obdsol.com/wp-content/uploads/stn2120-ds.pdf'),('sae','https://saemobilus.sae.org/standards/j1979-2_202604-e-e-diagnostic-test-modes-obdonuds')]
m=[]
with httpx.Client(timeout=40,follow_redirects=True)as c:
 for name,url in sources:
  p=f/(name+('.pdf'if url.endswith('.pdf')else'.html'))
  if not p.exists():r=c.get(url);r.raise_for_status();p.write_bytes(r.content)
  e=dict(name=name,url=url,path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
  if p.suffix=='.pdf':
   reader=PdfReader(p);pages=f/(name+'-pages');pages.mkdir(exist_ok=True)
   for i,page in enumerate(reader.pages,1):(pages/f'{i:03}.txt').write_text(page.extract_text()or'',encoding='utf-8')
   e['pages']=len(reader.pages)
  m.append(e);print(json.dumps(e),flush=True)
(f/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
