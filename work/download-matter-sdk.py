import httpx,json,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
s='3bcdd56ba54fb88b2afb4bfef575014671df7aa7'
f=Path('work/matter-primary');tree=json.loads((f/'sdk-tree.json').read_text())
paths=['src/lib/core/CHIPConfig.h','src/messaging/ReliableMessageMgr.cpp','src/messaging/ReliableMessageMgr.h','src/messaging/ReliableMessageProtocolConfig.cpp','src/messaging/ReliableMessageProtocolConfig.h','src/protocols/interaction_model/Constants.h','src/protocols/secure_channel/Constants.h','src/transport/raw/MessageHeader.h','src/transport/raw/MessageHeader.cpp','src/transport/raw/UDP.h','src/transport/raw/TCP.h','src/transport/MessageCounter.h','src/include/platform/CHIPDeviceConfig.h']
known={v['path']for v in tree['tree']}
assert set(paths)<=known,set(paths)-known
def download(path):
 u=f'https://raw.githubusercontent.com/project-chip/connectedhomeip/{s}/{path}';r=httpx.get(u,timeout=40);r.raise_for_status()
 p=f/'sdk'/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(r.content)
 return {'path':path,'url':u,'sha256':hashlib.sha256(r.content).hexdigest(),'revision':'v1.6.1.0/'+s,'scope':'Reading pending'}
with ThreadPoolExecutor(max_workers=4)as pool:result=list(pool.map(download,paths))
(f/'sdk-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
print('Downloaded',len(result),'pinned SDK sources')
