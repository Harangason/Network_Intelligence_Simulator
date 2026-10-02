from pathlib import Path
import httpx,hashlib,json,logging
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
folder=Path('work/modbus-primary')
url='https://www.modbus.org/file/secure/messagingimplementationguide.pdf'
r=httpx.get(url,follow_redirects=True,timeout=60);r.raise_for_status();assert r.content[:4]==b'%PDF'
p=folder/'tcp.pdf';p.write_bytes(r.content);doc=PdfReader(p)
pages=folder/'tcp-pages';pages.mkdir(exist_ok=True)
for i,page in enumerate(doc.pages):(pages/(str(i+1).zfill(3)+'.txt')).write_text(page.extract_text()or'',encoding='utf-8')
entry=dict(url=url,sha256=hashlib.sha256(r.content).hexdigest(),pages=len(doc.pages),bytes=len(r.content),revision='V1.0b October24 2006',read_scope='pending')
(folder/'tcp-source.json').write_text(json.dumps(entry,indent=2)+'\n');print(json.dumps(entry))
