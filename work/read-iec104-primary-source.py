"""Read pinned upstream code only as evidence; never execute downloaded code."""
from pathlib import Path
import urllib.request
import hashlib
import json
root=Path('work/iec104-primary-source-v2.3.2');root.mkdir(parents=True,exist_ok=True)
files=['lib60870-C/src/iec60870/cs104/cs104_connection.c',
       'lib60870-C/src/iec60870/cs104/cs104_slave.c',
       'lib60870-C/src/inc/api/iec60870_common.h',
       'user_guide.adoc']
manifest=[]
for relative in files:
    url='https://raw.githubusercontent.com/mz-automation/lib60870/v2.3.2/'+relative
    data=urllib.request.urlopen(url,timeout=25).read()
    target=root/Path(relative).name;target.write_bytes(data)
    manifest.append({'source':url,'path':str(target),'sha256':hashlib.sha256(data).hexdigest()})
    lines=data.decode('utf-8').splitlines();found=set()
    keys=('apciParameters.k =','apciParameters.w =','apciParameters.t','defaultAPCIParameters',
          'sizeOfCA =','sizeOfCOT =','sizeOfIOA =','maxSizeOfASDU =','tcpPort =','localPort =')
    print(relative)
    for i,line in enumerate(lines):
        if any(key in line for key in keys):
            for j in range(max(0,i-2),min(len(lines),i+12)):
                if j not in found:print(f'{j+1}: {lines[j]}');found.add(j)
(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
