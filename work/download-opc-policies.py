from pathlib import Path
import json,hashlib,httpx,re
from html.parser import HTMLParser
root=Path('work/opc-ua-primary')
class Links(HTMLParser):
 def __init__(self):super().__init__();self.current=None;self.body=[];self.links=[];self.text=[];self.skip=0
 def handle_starttag(self,tag,attrs):
  if tag in('script','style'):self.skip+=1
  if tag=='a':self.current=dict(attrs).get('href');self.body=[]
  if tag in('p','tr','td','th','div','h1','h2','h3','h4','li'):self.text.append('\n')
 def handle_endtag(self,tag):
  if tag in('script','style'):self.skip=max(0,self.skip-1)
  if tag=='a'and self.current:self.links.append((self.current,''.join(self.body)));self.current=None
 def handle_data(self,data):
  if not self.skip:self.text.append(data)
  if self.current:self.body.append(data)
manifest=json.loads((root/'manifest.json').read_text());metadata=[]
with httpx.Client(timeout=40,follow_redirects=True)as c:
 r=c.get('https://profiles.opcfoundation.org/profile/');r.raise_for_status();p=Links();p.feed(r.text)
 (root/'profiles-index.html').write_bytes(r.content)
 manifest.append(dict(url=str(r.url),path=str(root/'profiles-index.html').replace('\\','/'),sha256=hashlib.sha256(r.content).hexdigest(),bytes=len(r.content)))
 selections=dict((url,title.strip())for url,title in p.links if 'SecurityPolicy'in title and 'PubSub'not in title)
 print('selected security pages',len(selections),flush=True)
 for relative,title in selections.items():
  url='https://profiles.opcfoundation.org'+relative if relative.startswith('/')else relative
  q=c.get(url);q.raise_for_status();v=Links();v.feed(q.text);text=''.join(v.text)
  identifiers=re.findall(r'http://opcfoundation.org/UA/SecurityPolicy#[A-Za-z0-9_]+',text)
  if not identifiers:raise ValueError((title,'missing actualURI'))
  name=re.sub(r'[^A-Za-z0-9]+','-',title).strip('-');path=root/(name+'.html');path.write_bytes(q.content);(root/(name+'.txt')).write_text(text,encoding='utf-8')
  manifest.append(dict(url=str(q.url),path=str(path).replace('\\','/'),sha256=hashlib.sha256(q.content).hexdigest(),bytes=len(q.content)))
  metadata.append(dict(title=title,url=str(q.url),uri=identifiers[0],deprecated='Deprecated'in text,legacy='LegacySequenceNumbers set to TRUE'in text,zero_based='LegacySequenceNumbers set to FALSE'in text,forbidden='shall not be supported by any application'in text))
  print(metadata[-1],flush=True)
(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');(root/'policy-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
