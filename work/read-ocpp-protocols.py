from pathlib import Path
import zipfile,io,logging
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
f=Path('work/ocpp-primary')
for name in ('v21','v201','v16'):
 p=f/(name+'.zip')
 if not p.exists():continue
 with zipfile.ZipFile(p)as z:
  for member in z.namelist():
   if not any(k in member.lower()for k in ('ocpp-j','errata','ocpp-s','ocpp1.6-j'))or not member.lower().endswith('.pdf'):continue
   reader=PdfReader(io.BytesIO(z.read(member)));pages=f/'protocol-pages'/name/Path(member).stem;pages.mkdir(parents=True,exist_ok=True)
   for i,page in enumerate(reader.pages,1):(pages/f'{i:04}.txt').write_text(page.extract_text()or'',encoding='utf-8')
   print(name,member,len(reader.pages),flush=True)
