from pathlib import Path
import hashlib,json,httpx
from html.parser import HTMLParser
class Text(HTMLParser):
 def __init__(self):super().__init__();self.parts=[]
 def handle_data(self,s):
  if s.strip():self.parts.append(s.strip())
p=Path('work/opc-ua-primary');url='https://reference.opcfoundation.org/specs/OPC-10000-8/7.2'
r=httpx.get(url,follow_redirects=True,timeout=60);r.raise_for_status();(p/'part8-deadband.html').write_bytes(r.content)
t=Text();t.feed(r.text);(p/'part8-deadband.txt').write_text('\n'.join(t.parts),encoding='utf-8')
print(dict(url=url,sha256=hashlib.sha256(r.content).hexdigest()))
for part,terms in [('part4',['revisedLifetimeCount','revisedMaxKeepAliveCount','samplingInterval','requestedLifetime','maxAge','timeoutHint']),('part6',['MaxMessageSize','LegacySequenceNumbers','opcua+uajson','ProtocolVersion'])]:
 lines=(p/(part+'.txt')).read_text(encoding='utf-8').splitlines()
 for term in terms:
  indexes=[i for i,line in enumerate(lines)if term in line]
  print(part,term,indexes[:12])
  for i in indexes[-2:]:print('\n'.join(lines[max(0,i-2):i+8]))
