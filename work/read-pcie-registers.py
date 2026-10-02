from pathlib import Path
import hashlib,json,httpx,re
p=Path('work/pcie-primary');manifest=json.loads((p/'manifest.json').read_text())
urls={'registers':'https://raw.githubusercontent.com/torvalds/linux/v6.12/include/uapi/linux/pci_regs.h',
 'microchip-flow':'https://onlinedocs.microchip.com/oxy/GUID-E54C85EF-C33B-4E1E-A006-276B04B0FF9B-en-US-12/GUID-338089CA-526B-4997-933F-DC927FDC0071.html',
 'microchip-capabilities':'https://onlinedocs.microchip.com/oxy/GUID-E54C85EF-C33B-4E1E-A006-276B04B0FF9B-en-US-12/GUID-8352C297-864E-4338-82C3-137EC74AEEA2.html'}
with httpx.Client(follow_redirects=True,timeout=30)as c:
 for name,url in urls.items():
  r=c.get(url);r.raise_for_status();target=p/(name+('.h'if name=='registers'else'.html'));target.write_bytes(r.content)
  manifest.append(dict(url=url,path=str(target),sha256=hashlib.sha256(r.content).hexdigest(),content_type=r.headers.get('content-type')))
  content=r.text
  if name=='registers':
   print('\n'.join(line for line in content.splitlines()if any(k in line for k in('PCI_EXP_DEVCAP','PCI_EXP_DEVCTL','PCI_EXP_LNK','PCI_ERR','PCI_VC','PCI_EXP_SLTCAP','PCI_EXP_DPC'))))
  else:print(name,re.sub('<[^>]*>',' ',content)[-14000:])
(p/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
