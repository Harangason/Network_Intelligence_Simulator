import hashlib
import json
import logging
from pathlib import Path
import httpx
from pypdf import PdfReader

logging.getLogger('pypdf').setLevel(logging.ERROR)
folder=Path('work/lvds-primary');folder.mkdir(parents=True,exist_ok=True)
manifest=[]
with httpx.Client(headers={'User-Agent':'Mozilla/5.0','Accept':'application/pdf'},follow_redirects=True,timeout=90)as client:
    for name,url in [('owners-4th','https://www.ti.com/lit/ug/snla187/snla187.pdf'),
       ('multidrop-revision-a','https://www.ti.com/lit/an/slla108a/slla108a.pdf'),
       ('driver-047a','https://www.ti.com/lit/ds/symlink/ds90lv047a.pdf'),
       ('receiver-048a','https://www.ti.com/lit/ds/symlink/ds90lv048a.pdf')]:
        response=client.get(url);response.raise_for_status();body=response.content
        assert body.startswith(b'%PDF'),(name,response.headers.get('content-type'))
        path=folder/(name+'.pdf');path.write_bytes(body);reader=PdfReader(path)
        (folder/(name+'.txt')).write_text('\n\n'.join('PAGE '+str(i+1)+'\n'+p.extract_text()for i,p in enumerate(reader.pages)),encoding='utf-8')
        manifest.append(dict(name=name,url=url,sha256=hashlib.sha256(body).hexdigest(),pages=len(reader.pages),scope='Downloaded primary source; detailed section review pending'))
(folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps([{k:v for k,v in r.items()if k in ('name','pages','sha256')}for r in manifest]))
