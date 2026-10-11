"""Archive a primary ZIP; list members without executing or extracting them."""
import hashlib,json,ssl,sys,zipfile
from pathlib import Path
import httpx
folder=Path('work')/(sys.argv[1]+'-primary');folder.mkdir(exist_ok=True)
manifest=folder/'manifest.json';items=json.loads(manifest.read_text())if manifest.exists()else[]
for url in sys.argv[2:]:
 data=httpx.get(url,verify=ssl.create_default_context(),follow_redirects=True,timeout=90).raise_for_status().content
 path=folder/('source'+str(len(items)+1)+'.zip');path.write_bytes(data)
 with zipfile.ZipFile(path)as z:members=z.namelist()
 items.append(dict(url=url,path=str(path),sha256=hashlib.sha256(data).hexdigest(),kind='ORIGINAL_PRIMARY',members=members))
 manifest.write_text(json.dumps(items,indent=2)+'\n')
 print(dict(url=url,path=str(path),bytes=len(data),pdfs=[x for x in members if x.lower().endswith('.pdf')]))
