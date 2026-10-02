from pathlib import Path
import hashlib,json,httpx
from pypdf import PdfReader
p=Path(__file__).parent/'mil1553-primary';p.mkdir(exist_ok=True)
url='https://www.astronics.com/docs/default-source/ballard-technology/certificates/mil-std-1553c-dla.pdf?sfvrsn=17e2b258_2'
r=httpx.get(url,follow_redirects=True,timeout=60);r.raise_for_status()
f=p/'MIL-STD-1553C.pdf';f.write_bytes(r.content)
reader=PdfReader(f)
pages=p/'pages';pages.mkdir(exist_ok=True)
for i,page in enumerate(reader.pages,1):(pages/f'{i:02}.txt').write_text(page.extract_text(),encoding='utf-8')
(p/'manifest.json').write_text(json.dumps({'source':url,'canonical_revision_status':'https://quicksearch.dla.mil/qsDocDetails.aspx?ident_number=36973','edition':'MIL-STD-1553C 28 February2018','pages':len(reader.pages),'bytes':len(r.content),'sha256':hashlib.sha256(r.content).hexdigest(),'read_scope':'PENDING'},indent=2)+'\n')
print(len(reader.pages),len(r.content))
