from pathlib import Path
import hashlib,httpx,json
from pypdf import PdfReader
p=Path('work/profinet-primary');p.mkdir(exist_ok=True);m=[]
urls={'pi2018-update':'https://cl.profibus.com/fileadmin/media/downloadsection/technical_description_&_books/PROFINET_System_Description_engl_2018_Update.pdf',
 'siemens2025':'https://support.industry.siemens.com/cs/attachments/49948856/profinet_step7_function_manual_en-US_en-US.pdf',
 'siemens2012':'https://support.industry.siemens.com/cs/attachments/19292127/profinet_system_description_en-US_en-US.pdf'}
with httpx.Client(timeout=35,follow_redirects=True)as c:
 for name,url in urls.items():
  try:
   r=c.get(url);r.raise_for_status();assert r.content.startswith(b'%PDF');target=p/(name+'.pdf');target.write_bytes(r.content);rd=PdfReader(target)
   content='\n'.join('PAGE '+str(i+1)+'\n'+(page.extract_text()or'')for i,page in enumerate(rd.pages));(p/(name+'.txt')).write_text(content,encoding='utf-8')
   m.append(dict(url=url,path=str(target),sha256=hashlib.sha256(r.content).hexdigest(),kind='ORIGINAL_PDF'));print(name,len(rd.pages))
  except Exception as e:print(name,type(e).__name__,str(e)[:150])
 r=c.get('https://api.github.com/repos/rtlabs-com/p-net/commits/public');r.raise_for_status();sha=r.json()['sha'];print('pnet',sha)
 for path in('include/pnet_api.h','src/pf_types.h','src/device/pf_cmrpc.c','src/common/pf_block_reader.c','src/device/pf_ppm.c','src/device/pf_cpm.c','src/device/pf_dcp.c','src/device/pf_lldp.c','pnet_options.h.in'):
  url=f'https://raw.githubusercontent.com/rtlabs-com/p-net/{sha}/{path}'
  r=c.get(url)
  if r.status_code!=200:print(path,r.status_code);continue
  target=p/(path.replace('/','__'));target.write_bytes(r.content);m.append(dict(url=url,path=str(target),sha256=hashlib.sha256(r.content).hexdigest(),revision=sha,kind='PINNED_SOURCE'))
(p/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
