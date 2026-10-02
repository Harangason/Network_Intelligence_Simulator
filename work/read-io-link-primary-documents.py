"""Download selected publisher documents as read-only evidence; inspect no code."""
import hashlib,json,urllib.request,zipfile,io
from pathlib import Path
root=Path('work/io-link-primary-documents');root.mkdir(exist_ok=True)
sources=[('https://io-link.com/fileadmin/user_upload/Downloads/Package_2025/IOL-Interface-Spec_10002_V1.1.5_Oct2025.zip','interface115.zip'),
 ('https://io-link.com/fileadmin/user_upload/Downloads/Package_2024/IOL-Interface-Spec_10002_V114_Jun24.pdf','interface114.pdf')]
manifest=[]
for url,name in sources:
    raw=urllib.request.urlopen(url,timeout=60).read();(root/name).write_bytes(raw)
    manifest.append({'url':url,'path':str(root/name),'sha256':hashlib.sha256(raw).hexdigest()})
    if name.endswith('.zip'):
        z=zipfile.ZipFile(io.BytesIO(raw));print(z.namelist())
        for entry in z.infolist():
            if entry.filename.lower().endswith('.pdf'):
                target=root/Path(entry.filename).name;data=z.read(entry);target.write_bytes(data)
                manifest.append({'url':url,'archive_entry':entry.filename,'path':str(target),'sha256':hashlib.sha256(data).hexdigest()})
(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Read-only source manifest:',root/'manifest.json')
