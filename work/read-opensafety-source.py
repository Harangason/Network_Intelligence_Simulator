from pathlib import Path
import hashlib,json,httpx
p=Path('work/opensafety-primary');p.mkdir(exist_ok=True)
base='https://api.github.com/repos/rknall/openSAFETY'
with httpx.Client(follow_redirects=True,timeout=60)as c:
 r=c.get(base+'/commits/master');r.raise_for_status();commit=r.json()['sha']
 r=c.get(base+'/git/trees/'+commit,params={'recursive':'1'});r.raise_for_status();tree=r.json();assert not tree.get('truncated')
 (p/'tree.json').write_text(json.dumps(tree,indent=2)+'\n')
 (p/'revision.json').write_text(json.dumps(dict(repository=base,commit=commit),indent=2)+'\n')
 paths=[v['path']for v in tree['tree']if v['type']=='blob']
 print(commit)
 for path in paths:
  if path.startswith('doc/')or any(v in path.lower()for v in('eplscfg','scf','spdo','snmt','sod','sfm','shnf','crc','sdn','constants','version.txt')):print(path)
 manifest=[]
 for file in('README.md','License.md','ChangeLog.md','version.txt'):
  url='https://raw.githubusercontent.com/rknall/openSAFETY/'+commit+'/'+file;r=c.get(url);r.raise_for_status();(p/file).write_bytes(r.content)
  manifest.append(dict(url=url,path=str(p/file),sha256=hashlib.sha256(r.content).hexdigest(),commit=commit))
 (p/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
