from pathlib import Path
import hashlib,json,httpx
p=Path('work/opensafety-primary');commit=json.loads((p/'revision.json').read_text())['commit'];manifest=json.loads((p/'manifest.json').read_text())
files=['src/eplssrc/SN/SPDOapi.h','src/eplssrc/SN/SHNF.h','src/tools/oschecksum/include/oschecksum/crc.h','src/tools/oschecksum/include/oschecksum/crc16_AC9A.h','doc/integration_guide/integrate_sn_necessary.md','doc/integration_guide/integrate_sn_callbacks.md']
with httpx.Client(follow_redirects=True,timeout=60)as c:
 for file in files:
  url='https://raw.githubusercontent.com/rknall/openSAFETY/'+commit+'/'+file;r=c.get(url);r.raise_for_status();target=p/file;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(r.content)
  manifest.append(dict(url=url,path=str(target),sha256=hashlib.sha256(r.content).hexdigest(),commit=commit))
(p/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
