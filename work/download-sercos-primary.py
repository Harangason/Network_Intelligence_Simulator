from pathlib import Path
import httpx,json,hashlib,logging,re
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
p=Path('work/sercos-primary');p.mkdir(exist_ok=True);m=[]
urls={'principle':'https://www.sercos.org/technology/functions-and-features/transmission-principle/',
 'ucc':'https://www.sercos.org/technology/functions-and-features/uc-channel/',
 'brochure':'https://www.sercos.org/downloads/brochures/?cHash=584b637215724278782d4ba6b3f5cfc2&tx_vdsercosdownloads_downloads%5Baction%5D=download&tx_vdsercosdownloads_downloads%5Bcontroller%5D=File&tx_vdsercosdownloads_downloads%5Bfile%5D=Sercos_Sercos_III_Broschuere_2016_EN_US__V02_web.pdf'}
with httpx.Client(timeout=30,follow_redirects=True)as c:
 for name,url in urls.items():
  try:r=c.get(url);r.raise_for_status()
  except httpx.HTTPError as e:print(name,type(e).__name__,flush=True);continue
  f=p/(name+('.pdf'if r.content.startswith(b'%PDF')else'.html'));f.write_bytes(r.content)
  m.append(dict(url=url,path=str(f),sha256=hashlib.sha256(r.content).hexdigest(),kind='ORIGINAL_PRIMARY'))
  if f.suffix=='.pdf':
   doc=PdfReader(f);f.with_suffix('.txt').write_text('\n'.join('PDF_PAGE'+str(i+1)+'\n'+(v.extract_text()or'')for i,v in enumerate(doc.pages)),encoding='utf-8');print(name,len(doc.pages),flush=True)
  else:f.with_suffix('.txt').write_text(re.sub('<[^>]+>',' ',r.text),encoding='utf-8');print(name,len(r.content),flush=True)
(p/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
