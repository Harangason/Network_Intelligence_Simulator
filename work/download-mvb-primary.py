from pathlib import Path
import hashlib,json,httpx,logging
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
folder=Path('work/mvb-primary');folder.mkdir(exist_ok=True)
entries=[]
sources=[('abb_pcnode_1995','https://www.daube.ch/ddd/files/mvb_kit_c2.pdf','ABB MVBVirtualTerminal/PCNode TN-AC-95/185 December19 1995 chapter2 on technical author website; historical implementation qualifier, not current full IEC61375-3-1'),
 ('imc_fieldbus','https://www.imc-tm.cn/fileadmin/Public/Downloads/Datasheets/imc_optional_accessories/imc_Accessories_EN_TDs/TD_Digital_Fieldbus.pdf','imc fieldbus data sheet actual printed revision to verify; nativeMVB qualification not all-edition standard'),
 ('lapp_mvb_cable','https://www.lapp.ch/media/PIM_NEU/Datenbl%C3%A4tter/DB2173001EN.pdf','LAPP UNITRONICTRAINMVB2173001 data sheet November27 2025; actualcable electrical/environmental limits')]
with httpx.Client(follow_redirects=True,timeout=30)as client:
    for name,url,revision in sources:
        path=folder/(name+'.pdf')
        if not path.exists():r=client.get(url);r.raise_for_status();path.write_bytes(r.content)
        reader=PdfReader(path);pages=folder/name;pages.mkdir(exist_ok=True)
        for n,page in enumerate(reader.pages,1):(pages/f'{n:03}.txt').write_text(page.extract_text()or'',encoding='utf-8')
        entries.append(dict(name=name,url=url,revision=revision,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),pages=len(reader.pages),bytes=path.stat().st_size,read_scope='pending'))
(folder/'manifest.json').write_text(json.dumps(entries,indent=2)+'\n');print(json.dumps(entries))
