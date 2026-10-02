from pathlib import Path
import httpx,hashlib,json,logging
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
folder=Path('work/modbus-primary');url='https://www.modbus.org/file/secure/modbussecurityprotocol.pdf'
r=httpx.get(url,follow_redirects=True,timeout=60);r.raise_for_status();assert r.content[:4]==b'%PDF'
(folder/'security.pdf').write_bytes(r.content);doc=PdfReader(folder/'security.pdf')
pages=folder/'security-pages';pages.mkdir(exist_ok=True)
for i,page in enumerate(doc.pages):(pages/(str(i+1).zfill(3)+'.txt')).write_text(page.extract_text()or'',encoding='utf-8')
entry=dict(url=url,sha256=hashlib.sha256(r.content).hexdigest(),pages=len(doc.pages),bytes=len(r.content),revision='MB-TCP-Security-v36 2021-07-30',read_scope='pending')
(folder/'security-source.json').write_text(json.dumps(entry,indent=2)+'\n');print(json.dumps(entry))
