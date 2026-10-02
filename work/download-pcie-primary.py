from pathlib import Path
import hashlib,json,httpx
from pypdf import PdfReader
folder=Path('work/pcie-primary');folder.mkdir(exist_ok=True);manifest=[]
urls={
 'base-2.1':'https://www.intel.com/content/dam/support/us/en/programmable/support-resources/fpga-wiki/asset03/pci-express-base-r2.1.pdf',
 'physical':'https://www.intel.com/content/www/us/en/docs/programmable/683724/18-0/physical-layer.html',
 'gen4-5':'https://edc.intel.com/content/www/us/en/design/products/platforms/details/raptor-lake-s/13th-generation-core-processors-datasheet-volume-1-of-2/004/pci-express-architecture/',
 'gen6':'https://pcisig.com/blog/evolution-pci-express-specification-its-sixth-generation-third-decade-and-still-going-strong',
 'gen7':'https://pcisig.com/blog/pcie-70-specification-version-09-final-draft-now-available-member-review',
 'implementation':'https://www.intel.com/content/www/us/en/docs/programmable/813754/24-3/supported-features.html'}
with httpx.Client(follow_redirects=True,timeout=45)as c:
 for name,url in urls.items():
  try:
   r=c.get(url);r.raise_for_status();pdf=r.content.startswith(b'%PDF');target=folder/(name+('.pdf'if pdf else'.html'));target.write_bytes(r.content)
   if pdf:
    reader=PdfReader(target);(folder/(name+'.txt')).write_text('\n'.join('PAGE '+str(i+1)+'\n'+(p.extract_text()or'')for i,p in enumerate(reader.pages)),encoding='utf-8')
   manifest.append(dict(url=url,path=str(target),sha256=hashlib.sha256(r.content).hexdigest(),content_type=r.headers.get('content-type')))
  except Exception as e:print(name,type(e).__name__,str(e)[:120])
(folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print({'downloaded':len(manifest)})
