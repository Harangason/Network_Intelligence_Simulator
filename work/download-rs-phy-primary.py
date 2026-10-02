from pathlib import Path
import httpx,json,hashlib
from pypdf import PdfReader
p=Path('work/rs-phy-primary');p.mkdir(exist_ok=True);m=[]
with httpx.Client(timeout=25,follow_redirects=True)as c:
 for name,url in {
  'ti-rs232-glossary':'https://www.ti.com/lit/an/slla037a/slla037a.pdf',
  'ti-rs232-design':'https://www.ti.com/lit/an/sdaa219/sdaa219.pdf',
  'ti-rs422-485':'https://www.ti.com/lit/an/slla070d/slla070d.pdf',
  'ti-rs485-design':'https://www.ti.com/lit/an/slla272d/slla272d.pdf'}.items():
  try:r=c.get(url);r.raise_for_status()
  except httpx.HTTPError as e:print(name,type(e).__name__,flush=True);continue
  t=p/(name+('.pdf'if r.content.startswith(b'%PDF')else'.html'));t.write_bytes(r.content)
  m.append(dict(url=url,path=str(t),sha256=hashlib.sha256(r.content).hexdigest(),kind='ORIGINAL_PRIMARY'))
  if t.suffix=='.pdf':
   rd=PdfReader(t);(p/(name+'.txt')).write_text('\n'.join('PDF_PAGE'+str(i+1)+'\n'+(v.extract_text()or'')for i,v in enumerate(rd.pages)),encoding='utf-8');print(name,len(rd.pages),flush=True)
  else:print(name,len(r.content),flush=True)
(p/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
