"""Read publisher PDFs as parameter evidence; never execute downloaded content."""
from pathlib import Path
import urllib.request
import hashlib
import json
import io
from pypdf import PdfReader
folder=Path('work/iec61162-primary-documents');folder.mkdir(parents=True,exist_ok=True)
base='https://www.furunousa.com/-/media/sites/furuno/document_library/documents/manuals/public_manuals/'
names=['fa150_operators_manual_j_9252012.pdf','fe700_operators_manual.pdf',
       'vr3000_vr3000s_installation_manual_l1__2-23-11.pdf','vr7000_vr7000s_operators_manual.pdf']
manifest=[]
for name in names:
    url=base+name
    try:
        data=urllib.request.urlopen(url,timeout=30).read()
        pdf=PdfReader(io.BytesIO(data));found=[]
        for index,page in enumerate(pdf.pages):
            text=page.extract_text()or''
            if any(key in text for key in ('Baud rate:','82 characters','IEC61162-450 transmission group','Datagram header','IEC61162-450 TX','IEC61162-450 RX','VERSION NO.')):
                found.append({'page':index+1,'text':text})
        (folder/(name+'.evidence.json')).write_text(json.dumps(found,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        manifest.append({'source':url,'sha256':hashlib.sha256(data).hexdigest(),'pages':len(pdf.pages),'evidence_pages':[p['page']for p in found]})
        print(json.dumps(manifest[-1]))
        for page in found:
            print(page['page'],page['text'][:2500])
    except Exception as error:
        print(name,type(error).__name__,str(error))
(folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
