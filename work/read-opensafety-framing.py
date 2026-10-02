from pathlib import Path
import hashlib,json,httpx
p=Path('work/opensafety-primary');commit=json.loads((p/'revision.json').read_text())['commit'];tree=json.loads((p/'tree.json').read_text())['tree'];manifest=json.loads((p/'manifest.json').read_text())
files=['src/eplssrc/SN/EPLStypes.h','src/eplssrc/contrib/EPLStarget.h','src/eplssrc/SN/SFSint.h','src/eplssrc/SN/SFSdeser.c','src/eplssrc/SN/SFSser.c','src/eplssrc/SN/SFSmain.c','src/eplssrc/SN/SPDOint.h','src/eplssrc/SN/SPDOmappcom.cin','src/tools/oschecksum/include/oschecksum/crc8.h','src/tools/oschecksum/include/oschecksum/crc16.h','src/tools/oschecksum/crc_protocol.c']
with httpx.Client(follow_redirects=True,timeout=60)as c:
 for file in files:
  assert any(v['path']==file for v in tree);url='https://raw.githubusercontent.com/rknall/openSAFETY/'+commit+'/'+file;r=c.get(url);r.raise_for_status();target=p/file;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(r.content)
  manifest.append(dict(url=url,path=str(target),sha256=hashlib.sha256(r.content).hexdigest(),commit=commit))
(p/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
