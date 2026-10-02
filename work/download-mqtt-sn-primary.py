from pathlib import Path
import hashlib,json,httpx,logging
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
folder=Path('work/mqtt-sn-primary');folder.mkdir(exist_ok=True)
commit='1f1fd60538cce4f6d8cf76f9a54c9c166c628367'
url=f'https://raw.githubusercontent.com/oasis-open/mqtt-sn-sample-resources/{commit}/docs/MQTT-SN_spec_v1.2.pdf'
path=folder/'MQTT-SN_spec_v1.2.pdf'
with httpx.Client(follow_redirects=True,timeout=30)as client:
    if not path.exists():r=client.get(url);r.raise_for_status();path.write_bytes(r.content)
reader=PdfReader(path);pages=folder/'pages';pages.mkdir(exist_ok=True)
for n,page in enumerate(reader.pages,1):
    (pages/f'{n:03}.txt').write_text(page.extract_text()or'',encoding='utf-8')
entry=dict(url=url,commit=commit,revision='MQTT-SN Version1.2 November14 2013 IBM contribution, not OASIS ratified MQTT-SN2.0',
    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),pages=len(reader.pages),bytes=path.stat().st_size,read_scope='pending')
(folder/'manifest.json').write_text(json.dumps([entry],indent=2)+'\n');print(json.dumps(entry))
