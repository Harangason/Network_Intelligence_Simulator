from pathlib import Path
import httpx,ssl,hashlib,json,logging
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
p=Path('work/spacewire-primary');p.mkdir(exist_ok=True)
u='https://ecss.nl/wp-content/uploads/2019/05/ECSS-E-ST-50-12C-Rev.1%2815May2019%29.pdf'
with httpx.Client(timeout=35,follow_redirects=True,verify=ssl.create_default_context())as c:
 r=c.get(u);r.raise_for_status();assert r.content.startswith(b'%PDF')
f=p/'ecss.pdf';f.write_bytes(r.content);doc=PdfReader(f)
f.with_suffix('.txt').write_text('\n'.join('PDF_PAGE'+str(i+1)+'\n'+(v.extract_text()or'')for i,v in enumerate(doc.pages)),encoding='utf-8')
(p/'manifest.json').write_text(json.dumps([dict(url=u,path=str(f),sha256=hashlib.sha256(r.content).hexdigest(),kind='ORIGINAL_PRIMARY')],indent=2)+'\n')
print(len(doc.pages),hashlib.md5(r.content).hexdigest(),flush=True)
