from pathlib import Path
import json,hashlib,httpx
from pypdf import PdfReader
p=Path('work/profibus-primary');p.mkdir(exist_ok=True);manifest=[]
urls={'system2016':'https://uk.profibus.com/fileadmin/media/downloadsection/PROFIBUS_Systembeschreibung_ENG_web.pdf',
 'step7v13':'https://cache.industry.siemens.com/dl/files/579/59193579/att_22016/v1/profibus_step7_v13_function_manual_en-US_en-US.pdf',
 'abb-master':'https://help.plc.abb.com/AB281_en/ce0696233adc50929e52b5ecad1e74be_4_en_us.html'}
with httpx.Client(follow_redirects=True,timeout=25)as c:
 for name,url in urls.items():
  try:
   r=c.get(url);r.raise_for_status();ext='.pdf'if r.content.startswith(b'%PDF')else'.html';target=p/(name+ext);target.write_bytes(r.content)
   if ext=='.pdf':
    reader=PdfReader(target);text='\n'.join('PAGE '+str(i+1)+'\n'+(page.extract_text()or'')for i,page in enumerate(reader.pages));(p/(name+'.txt')).write_text(text,encoding='utf-8')
   manifest.append(dict(url=url,path=str(target),sha256=hashlib.sha256(r.content).hexdigest(),kind=ext));print(name,len(r.content))
  except Exception as e:print(name,type(e).__name__,str(e)[:100])
(p/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
