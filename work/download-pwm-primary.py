from pathlib import Path
import httpx,hashlib,json
from pypdf import PdfReader
p=Path('work/pwm-primary');p.mkdir(exist_ok=True);m=[]
with httpx.Client(timeout=18,follow_redirects=True)as c:
 for name,url in {
  'linux618-doc':'https://docs.kernel.org/6.18/driver-api/pwm.html',
  'linux618-header':'https://raw.githubusercontent.com/torvalds/linux/v6.18/include/linux/pwm.h',
  'linux618-core':'https://raw.githubusercontent.com/torvalds/linux/v6.18/drivers/pwm/core.c',
  'linux618-dt':'https://raw.githubusercontent.com/torvalds/linux/v6.18/include/dt-bindings/pwm/pwm.h',
  'stm32-an4013':'https://www.st.com/content/ccc/resource/technical/document/application_note/54/0f/67/eb/47/34/45/40/DM00042534.pdf/files/DM00042534.pdf/jcr:content/translations/en.DM00042534.pdf'}.items():
  try:r=c.get(url)
  except httpx.HTTPError as e:
   print(name,type(e).__name__,flush=True);continue
  if r.status_code!=200:print(name,r.status_code);continue
  ext='.pdf'if r.content.startswith(b'%PDF')else'.txt';t=p/(name+ext);t.write_bytes(r.content)
  m.append(dict(url=url,path=str(t),sha256=hashlib.sha256(r.content).hexdigest(),kind='ORIGINAL_PDF'if ext=='.pdf'else'PRIMARY_SOURCE'))
  if ext=='.pdf':
   rd=PdfReader(t);(p/(name+'.txt')).write_text('\n'.join('PDF_PAGE'+str(i+1)+'\n'+(page.extract_text()or'')for i,page in enumerate(rd.pages)),encoding='utf-8');print(name,'pages',len(rd.pages))
  else:print(name,len(r.content))
(p/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
