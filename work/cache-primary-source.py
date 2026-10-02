"""Cache original technical source with secure system trust and hash."""
import hashlib,json,ssl,sys,logging
from pathlib import Path
import httpx
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.CRITICAL)
folder=Path('work')/(sys.argv[1]+'-primary');folder.mkdir(exist_ok=True)
manifest=folder/'manifest.json';items=json.loads(manifest.read_text())if manifest.exists()else[]
for i,url in enumerate(sys.argv[2:]):
 data=httpx.get(url,verify=ssl.create_default_context(),follow_redirects=True,timeout=90).raise_for_status().content
 pdf=data.startswith(b'%PDF');path=folder/('source'+str(len(items)+1)+('.pdf'if pdf else '.html'));path.write_bytes(data)
 if pdf:
  r=PdfReader(path);path.with_suffix('.txt').write_text('\n'.join(f'\nPAGE {j+1}\n'+(p.extract_text()or'')for j,p in enumerate(r.pages)),encoding='utf-8')
 else:
  from html.parser import HTMLParser
  class Text(HTMLParser):
   def __init__(self):super().__init__();self.parts=[]
   def handle_data(self,d):self.parts.append(d)
  t=Text();t.feed(data.decode('utf-8',errors='replace'));path.with_suffix('.txt').write_text('\n'.join(t.parts),encoding='utf-8')
 items.append(dict(url=url,path=str(path),sha256=hashlib.sha256(data).hexdigest(),kind='ORIGINAL_PRIMARY'))
 manifest.write_text(json.dumps(items,indent=2)+'\n')
 print(dict(url=url,path=str(path),bytes=len(data)))
manifest.write_text(json.dumps(items,indent=2)+'\n')
