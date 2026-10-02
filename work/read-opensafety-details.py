from pathlib import Path
import hashlib,json,httpx
p=Path('work/opensafety-primary');commit=json.loads((p/'revision.json').read_text())['commit'];tree=json.loads((p/'tree.json').read_text())['tree']
for entry in tree:
 path=entry['path']
 if entry['type']=='blob'and(path.startswith('src/eplssrc/')and path.count('/')<3 or 'SOD' in path and 'contrib'in path):print(path)
files=['doc/software/concept_nwstructure.md','doc/software/structure_spdo.md','doc/software/structure_sdn.md','doc/integration_guide/integrate_sn_scaling.md','src/eplssrc/contrib/EPLScfg.h','src/eplssrc/SN/EPLScfgCheck.h','src/eplssrc/SN/SCFM.h','src/eplssrc/SN/SDN.h','src/eplssrc/SN/SDNmain.c','src/eplssrc/SN/SPDO.h','src/eplssrc/SN/SPDOrxConsSm.c','src/eplssrc/SN/SPDOrxSyncConsSm.c','src/eplssrc/SN/SPDOtxProdSm.c','src/eplssrc/SN/SPDOtxSyncProdSm.c']
manifest=json.loads((p/'manifest.json').read_text())
with httpx.Client(follow_redirects=True,timeout=60)as c:
 for file in files:
  assert any(v['path']==file for v in tree)
  url='https://raw.githubusercontent.com/rknall/openSAFETY/'+commit+'/'+file;r=c.get(url);r.raise_for_status();target=p/file;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(r.content)
  manifest.append(dict(url=url,path=str(target),sha256=hashlib.sha256(r.content).hexdigest(),commit=commit))
(p/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
