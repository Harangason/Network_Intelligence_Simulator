from pathlib import Path
import hashlib,json,httpx,logging
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
folder=Path('work/nb-iot-primary');folder.mkdir(exist_ok=True)
entries=[]
old=Path('work/lte-m-primary');previous=json.loads((old/'manifest.json').read_text())
for entry in previous:
    path=old/(entry['name']+'.pdf');assert hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256']
    entries.append(dict(name=entry['name'],url=entry['url'],path=str(path),sha256=entry['sha256'],pages=entry['pages'],read_scope='NB-IoT review pending, separate from LTE-M review'))
sources=[('nas-008','https://www.etsi.org/deliver/etsi_ts/124000_124099/124008/18.08.00_60/ts_124008v180800p.pdf'),
 ('nas-301','https://www.etsi.org/deliver/etsi_ts/124300_124399/124301/18.09.00_60/ts_124301v180900p.pdf'),
 ('procedures','https://www.etsi.org/deliver/etsi_ts/136200_136299/136213/18.04.00_60/ts_136213v180400p.pdf')]
with httpx.Client(follow_redirects=True,timeout=40)as client:
    for name,url in sources:
        path=folder/(name+'.pdf')
        if not path.exists():r=client.get(url);r.raise_for_status();path.write_bytes(r.content)
        reader=PdfReader(path)
        (folder/(name+'.txt')).write_text('\n'.join(f'\nPDF PAGE {n}\n'+(p.extract_text()or'')for n,p in enumerate(reader.pages,1)),encoding='utf-8')
        entries.append(dict(name=name,url=url,path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),pages=len(reader.pages),bytes=path.stat().st_size,read_scope='pending'))
(folder/'manifest.json').write_text(json.dumps(entries,indent=2)+'\n');print(json.dumps(entries))
