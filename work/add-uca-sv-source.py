from pathlib import Path
import hashlib,httpx,json,logging
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
p=Path('work/sv-primary');m=json.loads((p/'manifest.json').read_text())
urls=['http://iec61850.ucaiug.org/Implementation%20Guidelines/DigIF_spec_9-2LE_R2-1_040707-CB.pdf','https://gitlab.com/wireshark/wireshark/uploads/284e5e5a19549602b692b63e0ebf1f7d/digif_spec_9-2le_r2-1_040707-cb.pdf']
with httpx.Client(timeout=20,follow_redirects=True)as c:
 for u in urls:
  try:r=c.get(u);r.raise_for_status();assert r.content.startswith(b'%PDF')
  except (httpx.HTTPError,AssertionError)as e:print(type(e).__name__,u,flush=True);continue
  f=p/'uca-9-2le.pdf';f.write_bytes(r.content);rd=PdfReader(f)
  f.with_suffix('.txt').write_text('\n'.join('PDF_PAGE'+str(i+1)+'\n'+(v.extract_text()or'')for i,v in enumerate(rd.pages)),encoding='utf-8')
  m.append(dict(url=u,path=str(f),sha256=hashlib.sha256(r.content).hexdigest(),kind='AUTHORED_UCA_PRIMARY'if'ucaiug.org'in u else'AUTHORED_UCA_PRIMARY_PUBLIC_MIRROR'))
  print(len(rd.pages),u,flush=True);break
(p/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
