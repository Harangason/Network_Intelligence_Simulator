from pathlib import Path
import hashlib,json,logging,httpx
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
f=Path('work/nmea2000-primary');f.mkdir(exist_ok=True)
sources=[('nmea','https://www.nmea.org/nmea-2000.html'),('guide','https://actisense.com/wp-content/uploads/2021/08/Complete-Guide-to-NMEA-2000_Revision_4_2021.pdf'),('warwick','https://www.can-cia.org/fileadmin/cia/documents/publications/cnlm/june_2024/cnlm_24-1_p9_nmea_2000_conformance_testing_and_product_certification_dr_chris_quigley_warwick_control_technologies.pdf'),('simma','https://simmasoftware.com/assets/images/nmea-2000-users-manual.pdf')]
m=[]
with httpx.Client(timeout=40,follow_redirects=True)as c:
 response=c.get('https://api.github.com/repos/ttlappalainen/NMEA2000/commits/master');response.raise_for_status();sha=response.json()['sha']
 (f/'library-commit.txt').write_text(sha+'\n')
 for filename in('NMEA2000.cpp','NMEA2000.h','N2kMsg.h','N2kMessages.cpp'):
  sources.append((filename,'https://raw.githubusercontent.com/ttlappalainen/NMEA2000/'+sha+'/src/'+filename))
 for name,url in sources:
  path=f/(name if '.'in name else name+('.pdf'if url.endswith('.pdf')else'.html'))
  if not path.exists():r=c.get(url);r.raise_for_status();path.write_bytes(r.content)
  e=dict(name=name,url=url,path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size)
  if path.suffix=='.pdf':
   pdf=PdfReader(path);pages=f/(name+'-pages');pages.mkdir(exist_ok=True)
   for i,page in enumerate(pdf.pages,1):(pages/f'{i:03}.txt').write_text(page.extract_text()or'',encoding='utf-8')
   e['pages']=len(pdf.pages)
  m.append(e);print(json.dumps(e),flush=True)
(f/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
