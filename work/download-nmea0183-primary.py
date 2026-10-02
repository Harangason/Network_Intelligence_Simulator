from pathlib import Path
import httpx,hashlib,json,logging
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
f=Path('work/nmea0183-primary');f.mkdir(exist_ok=True)
sources=[('nmea','https://www.nmea.org/nmea-0183.html'),('ublox20','https://content.u-blox.com/sites/default/files/documents/u-blox-20-HPG-2.00_InterfaceDescription_UBXDOC-304424225-19888.pdf'),('mux','https://actisense.com/wp-content/uploads/2020/01/PRO-MUX-1-User-Manual-issue-1.00.pdf')]
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
