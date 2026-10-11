import hashlib,json,logging,zipfile
from pathlib import Path
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.CRITICAL)
folder=Path('work/usb-primary');manifest=folder/'manifest.json';items=json.loads(manifest.read_text())
selected={'source4.zip':['usb_20.pdf','USB 2.0 Double Isochronous IN ECN.pdf','USB 2.0 ECN VBUS Max Limit.pdf','2002_05_28_errata.pdf'],'source5.zip':['USB 3.2 Revision 1.1.pdf']}
for item in items:
 name=Path(item['path']).name
 if name not in selected:continue
 with zipfile.ZipFile(folder/name)as z:
  for member in z.namelist():
   if Path(member).name not in selected[name]:continue
   path=folder/(name[:-4]+'-'+Path(member).name);data=z.read(member);path.write_bytes(data)
   r=PdfReader(path);path.with_suffix('.txt').write_text('\n'.join('\nPAGE '+str(i+1)+'\n'+(p.extract_text()or'')for i,p in enumerate(r.pages)),encoding='utf-8')
   item.setdefault('selected_members',[]).append(dict(member=member,path=str(path),sha256=hashlib.sha256(data).hexdigest(),pages=len(r.pages)))
   print(dict(path=str(path),pages=len(r.pages)))
 manifest.write_text(json.dumps(items,indent=2)+'\n')
