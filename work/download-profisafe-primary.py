from pathlib import Path
import httpx,json,hashlib
from pypdf import PdfReader
p=Path('work/profisafe-primary');p.mkdir(exist_ok=True);m=[]
sources={
 'pi2016':('https://uk.profibus.com/fileadmin/media/downloadsection/technical_description_&_books/PROFsafe_System_Description_engl_2016_Update.pdf',range(9,16)),
 'siemens2021':('https://cache.industry.siemens.com/dl/files/562/109802562/att_1081588/v1/s7ftsysb_en-US.pdf',list(range(59,66))+list(range(455,463))),
 'driver2020':('https://cache.industry.siemens.com/dl/files/384/109769384/att_991916/v1/profisafe_driver_v2_2_3_programming_manual_en-US_en-US.pdf',list(range(16,20))+list(range(24,45))+list(range(69,81)))}
with httpx.Client(timeout=55,follow_redirects=True)as c:
 for name,(url,pages)in sources.items():
  r=c.get(url);r.raise_for_status();assert r.content.startswith(b'%PDF');target=p/(name+'.pdf');target.write_bytes(r.content);rd=PdfReader(target)
  (p/(name+'.txt')).write_text('\n'.join('PDF_PAGE '+str(i)+'\n'+(rd.pages[i-1].extract_text()or'')for i in pages),encoding='utf-8')
  m.append(dict(url=url,path=str(target),sha256=hashlib.sha256(r.content).hexdigest(),kind='ORIGINAL_PDF',selected_pdf_pages=list(pages)));print(name,len(rd.pages))
(p/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
