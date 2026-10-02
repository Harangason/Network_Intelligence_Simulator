from pathlib import Path
import httpx,json,hashlib,logging,ssl
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
p=Path('work/someip-primary');p.mkdir(exist_ok=True);m=[]
urls={'protocol':'https://www.autosar.org/fileadmin/standards/R25-11/FO/AUTOSAR_FO_PRS_SOMEIPProtocol.pdf','sd':'https://www.autosar.org/fileadmin/standards/R25-11/FO/AUTOSAR_FO_PRS_SOMEIPServiceDiscoveryProtocol.pdf','tp':'https://www.autosar.org/fileadmin/standards/R25-11/FO/AUTOSAR_FO_PRS_SOMEIPTransportProtocol.pdf','tp-api':'https://www.autosar.org/fileadmin/standards/R25-11/CP/AUTOSAR_CP_SWS_SOMEIPTransportProtocol.pdf'}
with httpx.Client(timeout=45,follow_redirects=True,verify=ssl.create_default_context())as c:
 for name,url in urls.items():
  try:r=c.get(url);r.raise_for_status();assert r.content.startswith(b'%PDF')
  except (httpx.HTTPError,AssertionError)as e:print(name,type(e).__name__,flush=True);continue
  f=p/(name+'.pdf');f.write_bytes(r.content);doc=PdfReader(f)
  f.with_suffix('.txt').write_text('\n'.join('PDF_PAGE'+str(i+1)+'\n'+(v.extract_text()or'')for i,v in enumerate(doc.pages)),encoding='utf-8')
  m.append(dict(url=url,path=str(f),sha256=hashlib.sha256(r.content).hexdigest(),kind='ORIGINAL_PRIMARY'));print(name,len(doc.pages),flush=True)
(p/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
