from pathlib import Path
import hashlib,json,httpx,re
from pypdf import PdfReader
p=Path('work/pcie-primary');manifest=json.loads((p/'manifest.json').read_text())
url='https://cdrdv2-public.intel.com/655062/ug-01097-1_5.pdf'
r=httpx.get(url,follow_redirects=True,timeout=45);r.raise_for_status();path=p/'stratix-v.pdf';path.write_bytes(r.content)
manifest.append(dict(url=url,path=str(path),sha256=hashlib.sha256(r.content).hexdigest(),content_type='application/pdf'))
reader=PdfReader(path);text='\n'.join('PAGE '+str(i+1)+'\n'+(page.extract_text()or'') for i,page in enumerate(reader.pages));(p/'stratix-v.txt').write_text(text,encoding='utf-8')
(p/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
terms=['Maximum payload','Max payload','Max_Payload','read request','Completion timeout range','Completion Timeout Value','Read Completion Boundary','Link width','2.5','credit','LCRC','ECRC','Replay','Traffic Class','Virtual Channel','No Snoop','Relaxed Ordering']
for term in terms:
 hits=list(re.finditer(re.escape(term),text,re.I));print('\nTERM',term,'HITS',len(hits))
 for hit in hits[:3]:print(text[max(0,hit.start()-250):hit.start()+1700])
