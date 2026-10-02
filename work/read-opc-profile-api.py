from pathlib import Path
import httpx,re
folder=Path('work/opc-ua-primary')
with httpx.Client(timeout=30,follow_redirects=True)as c:
 r=c.get('https://profiles.opcfoundation.org/static/js/main.e88850d4.js');r.raise_for_status()
(folder/'profiles-app.js').write_bytes(r.content)
for p in('"api"','"api/"','Cp(','Sp(','/get','/list','/all'):
 matches=list(re.finditer(re.escape(p),r.text));print(p,len(matches))
 for v in matches[-7:]:print(r.text[max(0,v.start()-80):v.start()+150])
