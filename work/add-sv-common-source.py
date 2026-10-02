from pathlib import Path
import json,hashlib
p=Path('work/sv-primary/manifest.json');m=json.loads(p.read_text());f=Path('work/iec61850-primary-source-v1.6/iec61850_common.h')
u='https://raw.githubusercontent.com/mz-automation/libiec61850/v1.6/src/iec61850/inc/iec61850_common.h'
if not any(v['url']==u for v in m):m.append(dict(url=u,path=str(f),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),kind='ORIGINAL_PRIMARY'))
p.write_text(json.dumps(m,indent=2)+'\n')
