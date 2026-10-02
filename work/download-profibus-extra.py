from pathlib import Path
import hashlib,json,httpx
from pypdf import PdfReader
p=Path('work/profibus-primary');manifest=json.loads((p/'manifest.json').read_text())
urls={'acromag2002':'https://www.acromag.com/wp-content/uploads/2019/06/Acromag_Intro_ProfibusDP_698A.pdf',
 'spc3v16':'https://cache.industry.siemens.com/dl/files/972/1172972/att_40451/v1/Spc3he16.pdf'}
with httpx.Client(follow_redirects=True,timeout=25)as c:
 for name,url in urls.items():
  try:
   r=c.get(url);r.raise_for_status();assert r.content.startswith(b'%PDF');target=p/(name+'.pdf');target.write_bytes(r.content);reader=PdfReader(target)
   text='\n'.join('PAGE '+str(i+1)+'\n'+(page.extract_text()or'')for i,page in enumerate(reader.pages));(p/(name+'.txt')).write_text(text,encoding='utf-8')
   manifest.append(dict(url=url,path=str(target),sha256=hashlib.sha256(r.content).hexdigest(),kind='.pdf'));print(name,len(reader.pages))
  except Exception as e:print(name,type(e).__name__,str(e)[:100])
(p/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
