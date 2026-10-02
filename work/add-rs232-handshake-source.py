from pathlib import Path
import httpx,json,hashlib,logging
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
p=Path('work/rs-phy-primary');url='https://www.ti.com/lit/an/snla037b/snla037b.pdf'
r=httpx.get(url,timeout=20,follow_redirects=True);r.raise_for_status();assert r.content.startswith(b'%PDF')
t=p/'ti-rs232-handshake.pdf';t.write_bytes(r.content)
rd=PdfReader(t);(p/'ti-rs232-handshake.txt').write_text('\n'.join('PDF_PAGE'+str(i+1)+'\n'+(v.extract_text()or'')for i,v in enumerate(rd.pages)),encoding='utf-8')
m=json.loads((p/'manifest.json').read_text());m=[v for v in m if v['url']!=url];m.append(dict(url=url,path=str(t),sha256=hashlib.sha256(r.content).hexdigest(),kind='ORIGINAL_PRIMARY'));(p/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(len(rd.pages))
