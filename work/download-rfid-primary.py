from pathlib import Path
import httpx,json,hashlib
from pypdf import PdfReader
p=Path('work/rfid-primary');p.mkdir(exist_ok=True);m=[]
with httpx.Client(timeout=20,follow_redirects=True)as c:
 for name,url in {
  'gs1-gen2-301':'https://ref.gs1.org/standards/gen2/3.0.1/',
  'ti-hf-trf7970a':'https://www.ti.com/lit/ds/symlink/trf7970a.pdf',
  'ti-lf-mrd2':'https://www.ti.com/lit/ug/scbu049/scbu049.pdf'}.items():
  try:r=c.get(url);r.raise_for_status()
  except httpx.HTTPError as e:print(name,type(e).__name__,flush=True);continue
  t=p/(name+('.pdf'if r.content.startswith(b'%PDF')else'.html'));t.write_bytes(r.content)
  m.append(dict(url=url,path=str(t),sha256=hashlib.sha256(r.content).hexdigest(),kind='ORIGINAL_PRIMARY'))
  if t.suffix=='.pdf':
   rd=PdfReader(t);(p/(name+'.txt')).write_text('\n'.join('PDF_PAGE'+str(i+1)+'\n'+(v.extract_text()or'')for i,v in enumerate(rd.pages)),encoding='utf-8');print(name,len(rd.pages),flush=True)
  else:print(name,len(r.content),flush=True)
(p/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
