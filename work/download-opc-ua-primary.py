from pathlib import Path
import hashlib,json,httpx
from html.parser import HTMLParser
folder=Path('work/opc-ua-primary');folder.mkdir(exist_ok=True,parents=True)
class Text(HTMLParser):
 def __init__(self):super().__init__();self.lines=[];self.skip=0
 def handle_starttag(self,tag,attrs):
  if tag in('script','style'):self.skip+=1
  if tag in('p','tr','td','th','div','h1','h2','h3','h4','li'):self.lines.append('\n')
 def handle_endtag(self,tag):
  if tag in('script','style'):self.skip=max(0,self.skip-1)
 def handle_data(self,data):
  if not self.skip:self.lines.append(data)
manifest=[]
for part in(4,6,7):
 url=f'https://reference.opcfoundation.org/specs/OPC-10000-{part}/full'
 with httpx.Client(timeout=50,follow_redirects=True)as c:r=c.get(url);r.raise_for_status()
 path=folder/f'part{part}.html';path.write_bytes(r.content);p=Text();p.feed(r.text)
 (folder/f'part{part}.txt').write_text(''.join(p.lines),encoding='utf-8')
 manifest.append(dict(url=url,path=str(path).replace('\\','/'),sha256=hashlib.sha256(r.content).hexdigest(),bytes=len(r.content)))
 print(dict(part=part,bytes=len(r.content)),flush=True)
(folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
