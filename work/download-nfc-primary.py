from pathlib import Path
import hashlib,json,httpx,logging
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
folder=Path('work/nfc-primary');folder.mkdir(exist_ok=True)
sources=[('pn7160','https://www.nxp.com/docs/en/data-sheet/PN7160_PN7161.pdf'),
 ('um11495','https://www.nxp.com/docs/en/user-manual/UM11495.pdf')]
entries=[]
with httpx.Client(follow_redirects=True,timeout=40)as client:
    for name,url in sources:
        path=folder/(name+'.pdf')
        if not path.exists():r=client.get(url);r.raise_for_status();path.write_bytes(r.content)
        reader=PdfReader(path);pages=folder/(name+'-pages');pages.mkdir(exist_ok=True)
        for n,p in enumerate(reader.pages,1):(pages/f'{n:03}.txt').write_text(p.extract_text()or'',encoding='utf-8')
        entries.append(dict(name=name,url=url,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),pages=len(reader.pages),bytes=path.stat().st_size,read_scope='pending printed revision review'))
(folder/'manifest.json').write_text(json.dumps(entries,indent=2)+'\n');print(json.dumps(entries))
