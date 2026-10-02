"""Read pinned upstream source as evidence; never execute it."""
from pathlib import Path
import urllib.request
import hashlib
import json
root=Path('work/iec101-primary-source-v2.3.2');root.mkdir(parents=True,exist_ok=True)
files=['lib60870-C/src/iec60870/cs101/cs101_master.c',
       'lib60870-C/src/iec60870/cs101/cs101_slave.c',
       'lib60870-C/src/iec60870/cs101/cs101_asdu.c',
       'lib60870-C/src/iec60870/link_layer/link_layer.c',
       'lib60870-C/src/inc/api/cs101_information_objects.h',
       'lib60870-C/src/inc/api/cs101_master.h']
manifest=[]
for relative in files:
    url='https://raw.githubusercontent.com/mz-automation/lib60870/v2.3.2/'+relative
    data=urllib.request.urlopen(url,timeout=25).read()
    target=root/Path(relative).name;target.write_bytes(data)
    manifest.append({'source':url,'path':str(target),'sha256':hashlib.sha256(data).hexdigest()})
    text=data.decode('utf-8');lines=text.splitlines()
    keys=('defaultAppLayerParameters','defaultLinkLayerParameters','timeoutForAck =','timeoutRepeat =',
          'addressLength =','maxSizeOfASDU =','sizeOfCA =','sizeOfCOT =','sizeOfIOA =','SerialPort_create')
    found=set()
    print(relative)
    for i,line in enumerate(lines):
        if any(key in line for key in keys):
            for j in range(max(0,i-2),min(len(lines),i+12)):
                if j not in found: print(f'{j+1}: {lines[j]}');found.add(j)
(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
