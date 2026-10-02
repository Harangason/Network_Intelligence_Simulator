from pathlib import Path
import httpx,json,hashlib
p=Path('work/ros2-primary');p.mkdir(exist_ok=True);m=[]
repos={'ros2/ros2_documentation':[], 'ros2/rmw':['rmw/include/rmw/qos_profiles.h','rmw/include/rmw/types.h','rmw/include/rmw/rmw.h','rmw/include/rmw/validate_full_topic_name.h','rmw/include/rmw/time.h'],
 'ros2/rmw_zenoh':['README.md','rmw_zenoh_cpp/config/DEFAULT_RMW_ZENOH_SESSION_CONFIG.json5','rmw_zenoh_cpp/config/DEFAULT_RMW_ZENOH_ROUTER_CONFIG.json5']}
with httpx.Client(timeout=25,follow_redirects=True)as c:
 for repo,wanted in repos.items():
  r=c.get('https://api.github.com/repos/'+repo+'/commits/rolling');r.raise_for_status();sha=r.json()['sha'];print(repo,sha,flush=True)
  r=c.get('https://api.github.com/repos/'+repo+'/git/trees/'+sha+'?recursive=1');r.raise_for_status();paths=[v['path']for v in r.json()['tree']if v['type']=='blob']
  if not wanted:
   names=['Quality-of-Service','Domain-ID','Different-Middleware','Discovery','Executors','Topic-and-Service-Names','Interfaces','Security']
   wanted=[v for v in paths if v.endswith('.rst')and'/Concepts/'in'/'+v and any(n in v for n in names)]
   # Current documentation structure may move concept pages into the ROS-Framework tree.
   if not wanted:wanted=[v for v in paths if v.endswith('.rst')and any(n in Path(v).name for n in names)]
  for path in wanted:
   if path not in paths:print('absent',path,flush=True);continue
   url='https://raw.githubusercontent.com/'+repo+'/'+sha+'/'+path;r=c.get(url);r.raise_for_status()
   t=p/(repo.split('/')[-1]+'__'+path.replace('/','__'));t.write_bytes(r.content)
   m.append(dict(url=url,path=str(t),sha256=hashlib.sha256(r.content).hexdigest(),revision=sha,kind='PINNED_PRIMARY_SOURCE'))
   print(path,len(r.content),flush=True)
(p/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
