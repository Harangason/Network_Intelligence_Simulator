from pathlib import Path
from html.parser import HTMLParser
import hashlib,json,httpx
class Text(HTMLParser):
 def __init__(self):super().__init__();self.parts=[]
 def handle_data(self,s):
  if s.strip():self.parts.append(s.strip())
url='https://reference.opcfoundation.org/specs/OPC-10000-14/full';p=Path('work/opc-pubsub-primary');p.mkdir(exist_ok=True)
r=httpx.get(url,follow_redirects=True,timeout=90);r.raise_for_status();(p/'part14.html').write_bytes(r.content)
t=Text();t.feed(r.text);lines=t.parts;(p/'part14.txt').write_text('\n'.join(lines),encoding='utf-8')
(p/'manifest.json').write_text(json.dumps([dict(url=url,path=str(p/'part14.html'),sha256=hashlib.sha256(r.content).hexdigest(),bytes=len(r.content))],indent=2)+'\n')
for term in ['6.2.4.1','6.2.4.3','6.2.5.5','6.2.6.2','6.2.6.3','6.2.7.1','6.2.9.6','7.3.2','7.3.3','7.3.4','KeyFrameCount','DiscoveryResponseDelay']:
 indexes=[i for i,l in enumerate(lines)if term in l];print(term,indexes[:10])
 for i in indexes[-1:]:print('\n'.join(lines[max(0,i-1):i+16]))
