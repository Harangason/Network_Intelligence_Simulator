from pathlib import Path
import json,hashlib,httpx
from pypdf import PdfReader
p=Path('work/profibus-primary');m=json.loads((p/'manifest.json').read_text())
urls={'pf-pa2008':'https://files.pepperl-fuchs.com/webcat/navi/productInfo/doct/tdoct1681__eng.pdf',
 'eh-pa2024':'https://bdih-download.endress.com/file/2c7dadbefef6c6a4dcbe11ac9b0fad10/BA01691DEN_0324-00.pdf'}
with httpx.Client(timeout=35,follow_redirects=True)as c:
 for name,url in urls.items():
  r=c.get(url);r.raise_for_status();assert r.content.startswith(b'%PDF');target=p/(name+'.pdf');target.write_bytes(r.content);rd=PdfReader(target)
  pages=range(len(rd.pages))if name=='pf-pa2008'else list(range(63,70))+list(range(197,201))+[36,37,39,51,52,81,82]
  text='\n'.join('PAGE '+str(i+1)+'\n'+(rd.pages[i].extract_text()or'')for i in pages);(p/(name+'.txt')).write_text(text,encoding='utf-8')
  m.append(dict(url=url,path=str(target),sha256=hashlib.sha256(r.content).hexdigest(),kind='.pdf',extracted_pages=[i+1 for i in pages]));print(name,len(rd.pages))
(p/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
rd=PdfReader(p/'pno1997.pdf');pages=list(range(107,121))+list(range(895,909));text='\n'.join('PAGE '+str(i+1)+'\n'+(rd.pages[i].extract_text()or'')for i in pages)
(p/'pno-timing-pa.txt').write_text(text,encoding='utf-8')
for a,b in [(895,902),(902,906)]:
 print('\n'.join('PAGE '+str(i+1)+'\n'+(rd.pages[i].extract_text()or'')for i in range(a,b)))
