from pathlib import Path
import httpx,json,hashlib
from pypdf import PdfReader
p=Path('work/profibus-primary');url='https://cache.industry.siemens.com/dl/files/969/25553969/att_7167/v1/pzdpsi_af4xx_e.pdf'
r=httpx.get(url,timeout=30,follow_redirects=True);r.raise_for_status();assert r.content.startswith(b'%PDF')
target=p/'pyrometer-dp-cable.pdf';target.write_bytes(r.content);rd=PdfReader(target)
content='\n'.join('PAGE '+str(i+1)+'\n'+(page.extract_text()or'')for i,page in enumerate(rd.pages));(p/'pyrometer-dp-cable.txt').write_text(content,encoding='utf-8')
m=json.loads((p/'manifest.json').read_text());m.append(dict(url=url,path=str(target),sha256=hashlib.sha256(r.content).hexdigest(),kind='.pdf'));(p/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
lines=content.splitlines();i=next(i for i,v in enumerate(lines)if'Table 5.2'in v);print('\n'.join(lines[max(0,i-15):i+38]));print(content[:600])
