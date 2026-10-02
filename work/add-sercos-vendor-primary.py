from pathlib import Path
import json,httpx,hashlib,re,logging
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
p=Path('work/sercos-primary');m=json.loads((p/'manifest.json').read_text())
urls={'hilscher-api':'https://www.hilscher.com/fileadmin/cms_upload/de/Resources/pdf/Sercos_Master_Protocol_API_11_EN.pdf',
 'phases':'https://product-help.schneider-electric.com/Machine%20Expert/V2.0/en/m262serc/m262serc/D-SE-0096491.html',
 'cycle':'https://product-help.schneider-electric.com/Machine%20Expert/V1.1/de/m262serc/m262serc/Sercos_Basics/Sercos_Basics-5.htm'}
with httpx.Client(timeout=25,follow_redirects=True)as c:
 for name,url in urls.items():
  try:r=c.get(url);r.raise_for_status()
  except httpx.HTTPError as e:print(name,type(e).__name__,flush=True);continue
  f=p/(name+('.pdf'if r.content.startswith(b'%PDF')else'.html'));f.write_bytes(r.content)
  m.append(dict(url=url,path=str(f),sha256=hashlib.sha256(r.content).hexdigest(),kind='ORIGINAL_PRIMARY'))
  if f.suffix=='.pdf':
   rd=PdfReader(f);f.with_suffix('.txt').write_text('\n'.join('PDF_PAGE'+str(i+1)+'\n'+(v.extract_text()or'')for i,v in enumerate(rd.pages)),encoding='utf-8');print(name,len(rd.pages),flush=True)
  else:f.with_suffix('.txt').write_text(re.sub('<[^>]+>',' ',r.text),encoding='utf-8');print(name,len(r.content),flush=True)
(p/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
