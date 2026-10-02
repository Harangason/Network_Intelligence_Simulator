from pathlib import Path
import hashlib,json,httpx,re
from pypdf import PdfReader
p=Path('work/powerlink-primary');p.mkdir(exist_ok=True);manifest=[]
urls={'ds301':'https://www.br-automation.com/downloads_br_productcatalogue/assets/EPSG_301_V-1-5-1_DS-c710608e.pdf',
 'multiple-asnd':'https://www.br-automation.com/fileadmin/EPSG_302-B_V-1-1-1_DS-39befa02.pdf'}
with httpx.Client(follow_redirects=True,timeout=45)as c:
 for name,url in urls.items():
  try:
   r=c.get(url);r.raise_for_status();target=p/(name+'.pdf');target.write_bytes(r.content);reader=PdfReader(target)
   text='\n'.join('PAGE '+str(i+1)+'\n'+(page.extract_text()or'')for i,page in enumerate(reader.pages));(p/(name+'.txt')).write_text(text,encoding='utf-8')
   manifest.append(dict(url=url,path=str(target),sha256=hashlib.sha256(r.content).hexdigest(),pages=len(reader.pages)))
   print(name,len(reader.pages))
  except Exception as e:print(name,type(e).__name__,str(e)[:160])
(p/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
