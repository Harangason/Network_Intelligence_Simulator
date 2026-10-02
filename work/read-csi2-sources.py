from pathlib import Path
import hashlib,json,httpx
from pypdf import PdfReader
p=Path(__file__).parent/'csi2-primary';p.mkdir(exist_ok=True)
sources={
 'version-matrix':'https://www.mipi.org/hubfs/Specification-Feature-Tables/MIPI-CSI-2-Version-History-Table-March-2026.pdf',
 'ti960':'https://www.ti.com/lit/ds/symlink/ds90ub960-q1.pdf',
 'lattice':'https://www.latticesemi.com/-/media/LatticeSemi/Documents/UserManuals/MQ3/FPGA-IPUG-02321-1-0-MIPI-CSI-DSI-IP-User-Guide.ashx?document_id=55101'}
manifest={}
for name,url in sources.items():
 r=httpx.get(url,follow_redirects=True,timeout=60);r.raise_for_status()
 f=p/(name+'.pdf');f.write_bytes(r.content);reader=PdfReader(f)
 pages=p/(name+'-pages');pages.mkdir(exist_ok=True)
 for i,page in enumerate(reader.pages,1):(pages/f'{i:03}.txt').write_text(page.extract_text(),encoding='utf-8')
 manifest[name]=dict(source=url,sha256=hashlib.sha256(r.content).hexdigest(),bytes=len(r.content),pages=len(reader.pages),read_scope='PENDING')
 print(name,len(reader.pages),len(r.content),flush=True)
(p/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
