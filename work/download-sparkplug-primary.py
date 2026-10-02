import hashlib,json,ssl
from pathlib import Path
import httpx
from pypdf import PdfReader
p=Path('work/sparkplug-primary');p.mkdir(exist_ok=True)
u='https://sparkplug.eclipse.org/specification/version/3.0/documents/sparkplug-specification-3.0.0.pdf'
data=httpx.get(u,verify=ssl.create_default_context(),follow_redirects=True,timeout=90).raise_for_status().content
f=p/'sparkplug.pdf';f.write_bytes(data);r=PdfReader(f)
(p/'sparkplug.txt').write_text('\n'.join(f'\nPAGE {i+1}\n'+(v.extract_text()or'')for i,v in enumerate(r.pages)),encoding='utf-8')
(p/'manifest.json').write_text(json.dumps([dict(url=u,path=str(f),sha256=hashlib.sha256(data).hexdigest(),kind='ORIGINAL_PRIMARY')],indent=2)+'\n')
print(dict(pages=len(r.pages),sha256=hashlib.sha256(data).hexdigest()))
