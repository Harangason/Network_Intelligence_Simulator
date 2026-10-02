from pathlib import Path
import urllib.request,json,hashlib
root=Path('work/iec61850-primary-source-v1.6');root.mkdir(parents=True,exist_ok=True)
files=['src/iec61850/server/impl/ied_server_config.c','config/stack_config.h','src/iec61850/client/ied_connection.c','src/iec61850/inc/iec61850_common.h','src/iec61850/inc/iec61850_model.h','src/iec61850/server/mms_mapping/reporting.c']
manifest=[]
for relative in files:
 url='https://raw.githubusercontent.com/mz-automation/libiec61850/v1.6/'+relative
 try:
  data=urllib.request.urlopen(url,timeout=25).read();target=root/Path(relative).name;target.write_bytes(data)
  manifest.append({'source':url,'path':str(target),'sha256':hashlib.sha256(data).hexdigest()})
  print(relative,len(data))
 except Exception as exc:print(relative,type(exc).__name__,str(exc))
(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
