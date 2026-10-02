from pathlib import Path
import hashlib,httpx,json
from pypdf import PdfReader
p=Path('work/profinet-primary');m=json.loads((p/'manifest.json').read_text())
url='https://cache.industry.siemens.com/dl/files/439/109820439/att_1139619/v1/Communication_Fct_en-US.pdf'
r=httpx.get(url,timeout=50,follow_redirects=True);r.raise_for_status();assert r.content.startswith(b'%PDF')
target=p/'siemens2023.pdf';target.write_bytes(r.content);rd=PdfReader(target)
pages=[46,47,48,49,50,137,138,139]
(p/'siemens2023.txt').write_text('\n'.join('PDF_PAGE '+str(i)+'\n'+(rd.pages[i-1].extract_text()or'')for i in pages),encoding='utf-8')
m=[v for v in m if v['url']!=url];m.append(dict(url=url,path=str(target),sha256=hashlib.sha256(r.content).hexdigest(),kind='ORIGINAL_PDF',read_scope='SIMOTION Communication04/2023 A5E33436509B selected PDF46-50/137-139; device-qualified send clock factors/default1ms/IRTdomain, not universal PROFINET timing.'))
(p/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print('pages',len(rd.pages));print((p/'siemens2023.txt').read_text(encoding='utf-8'))
