from pathlib import Path
import httpx,json,hashlib,logging
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
f=Path('work/matter-primary');f.mkdir(exist_ok=True)
u='https://csa-iot.org/wp-content/uploads/2026/09/23-27349-012_Matter-1.6.1-Core-Specification.pdf'
p=f/'matter-core-161.pdf'
r=httpx.get(u,follow_redirects=True,timeout=90,headers={"User-Agent":"Mozilla/5.0","Referer":"https://csa-iot.org/developer-resource/specifications-download-request/"});r.raise_for_status();assert r.content[:4]==b'%PDF';p.write_bytes(r.content)
doc=PdfReader(p);(f/'matter-core-161.txt').write_text('\n'.join('PDF PAGE '+str(i+1)+'\n'+(page.extract_text()or'')for i,page in enumerate(doc.pages)),encoding='utf-8')
(f/'manifest.json').write_text(json.dumps([{'name':'matter-core-161','url':u,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'pages':len(doc.pages),'scope':'Reading pending'}],indent=2)+'\n')
print(len(doc.pages),len(r.content))

