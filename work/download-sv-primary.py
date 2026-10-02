from pathlib import Path
import httpx,hashlib,json,logging
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
p=Path('work/sv-primary');p.mkdir(exist_ok=True);manifest=[]
base='https://raw.githubusercontent.com/mz-automation/libiec61850/v1.6/src/sampled_values/'
urls={'uca-9-2le':'https://iec61850.ucaiug.org/Implementation%20Guidelines/DigIF_spec_9-2LE_R2-1_040707-CB.pdf',
 'abb-edition':'https://library.e.abb.com/public/7d0e72aaacea4129a414f227327fcce9/REC615_iec61850eng_2NGA002470_ENa.pdf',
 'sv-publisher':base+'sv_publisher.c','sv-subscriber':base+'sv_subscriber.c',
 'sv-publisher-h':base+'sv_publisher.h','sv-subscriber-h':base+'sv_subscriber.h'}
with httpx.Client(timeout=30,follow_redirects=True)as c:
 for name,url in urls.items():
  try:r=c.get(url);r.raise_for_status()
  except httpx.HTTPError as e:print(name,type(e).__name__,flush=True);continue
  path=p/(name+('.pdf'if r.content.startswith(b'%PDF')else'.txt'));path.write_bytes(r.content)
  manifest.append(dict(url=url,path=str(path),sha256=hashlib.sha256(r.content).hexdigest(),kind='ORIGINAL_PRIMARY'))
  if path.suffix=='.pdf':
   doc=PdfReader(path);path.with_suffix('.txt').write_text('\n'.join('PDF_PAGE'+str(i+1)+'\n'+(page.extract_text()or'')for i,page in enumerate(doc.pages)),encoding='utf-8');print(name,len(doc.pages),flush=True)
  else:print(name,len(r.content),flush=True)
(p/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
