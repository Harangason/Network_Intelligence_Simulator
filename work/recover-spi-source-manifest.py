import json,hashlib
from pathlib import Path
p=Path('work/spi-primary');items=[]
for i,u in enumerate(['https://www.nxp.com/docs/en/application-note/AN3020.pdf','https://ww1.microchip.com/downloads/en/DeviceDoc/61132B.pdf'],1):
 f=p/('source'+str(i)+'.pdf');items.append(dict(url=u,path=str(f),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),kind='ORIGINAL_PRIMARY'))
(p/'manifest.json').write_text(json.dumps(items,indent=2)+'\n');print(items)
