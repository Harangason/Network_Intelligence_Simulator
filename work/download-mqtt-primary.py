from pathlib import Path
import hashlib,json,httpx
from html.parser import HTMLParser
class Text(HTMLParser):
    def __init__(self):super().__init__();self.lines=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('style','script'):self.skip+=1
        if tag in ('p','div','h1','h2','h3','h4','h5','tr','br'):self.lines.append('\n')
    def handle_endtag(self,tag):
        if tag in ('style','script'):self.skip-=1
        if tag in ('p','div','h1','h2','h3','h4','h5','tr'):self.lines.append('\n')
    def handle_data(self,value):
        if not self.skip:self.lines.append(value)
folder=Path('work/mqtt-primary');folder.mkdir(exist_ok=True);entries=[]
with httpx.Client(follow_redirects=True,timeout=30)as client:
    for version in ('5.0','3.1.1','3.1.1-errata01'):
        url=(f'https://docs.oasis-open.org/mqtt/mqtt/v{version}/os/mqtt-v{version}-os.html'if version!='3.1.1-errata01'else
            'https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/errata01/os/mqtt-v3.1.1-errata01-os.html')
        path=folder/(version+'.html')
        if not path.exists():r=client.get(url);r.raise_for_status();path.write_bytes(r.content)
        # OASIS Word-export HTML declares windows-1252; preserve source bytes/hash.
        p=Text();p.feed(path.read_text(encoding='windows-1252'))
        text='\n'.join(' '.join(x.split())for x in ''.join(p.lines).splitlines()if x.strip())
        (folder/(version+'.txt')).write_text(text,encoding='utf-8')
        entries.append(dict(version=version,url=url,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size,
                            read_scope='pending selected parameter sections'))
(folder/'manifest.json').write_text(json.dumps(entries,indent=2)+'\n');print(json.dumps(entries))
