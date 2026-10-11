from pathlib import Path
import hashlib,json,ssl,zipfile,io
import httpx
url='https://downloads.sourceforge.net/project/tcnopen/TRDP/3.0.0.0/3.0.0.0.zip'
p=Path('work/trdp-primary');p.mkdir(exist_ok=True)
archive=p/'3.0.0.0.zip'
if not archive.exists():archive.write_bytes(httpx.get(url,verify=ssl.create_default_context(),follow_redirects=True,timeout=90).raise_for_status().content)
with zipfile.ZipFile(archive)as z:
 names=[n for n in z.namelist()if n.endswith(('trdp_types.h','trdp_private.h','trdp_pdcom.c','trdp_mdcom.c','trdp_utils.c','trdp_if_light.h','vos_utils.c','vos_sock.c'))]
 print(names)
 for n in names:
  dest=p/'release'/n;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(n))
manifest=json.loads((p/'manifest.json').read_text())
if not any(v['url']==url for v in manifest):
 manifest.append(dict(url=url,path=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),kind='ORIGINAL_PRIMARY_RELEASE_ARCHIVE',selected_files=names))
(p/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
