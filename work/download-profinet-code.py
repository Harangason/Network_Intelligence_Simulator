from pathlib import Path
import httpx,json,hashlib
p=Path('work/profinet-primary');m=json.loads((p/'manifest.json').read_text());sha=next(v['revision']for v in m if'revision'in v)
with httpx.Client(timeout=30,follow_redirects=True)as c:
 r=c.get(f'https://api.github.com/repos/rtlabs-com/p-net/git/trees/{sha}?recursive=1');r.raise_for_status();paths=[v['path']for v in r.json()['tree']if v['type']=='blob']
 wanted=['pf_ppm.c','pf_cpm.c','pf_dcp.c','pf_lldp.c','pf_block_reader.c','pf_cmdev.c','pf_cmina.c']
 for path in paths:
  if Path(path).name not in wanted:continue
  url=f'https://raw.githubusercontent.com/rtlabs-com/p-net/{sha}/{path}';r=c.get(url);r.raise_for_status();target=p/path.replace('/','__');target.write_bytes(r.content)
  m.append(dict(url=url,path=str(target),sha256=hashlib.sha256(r.content).hexdigest(),revision=sha,kind='PINNED_SOURCE'));print(path)
(p/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
