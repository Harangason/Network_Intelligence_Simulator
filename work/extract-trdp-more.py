import zipfile
from pathlib import Path
p=Path('work/trdp-primary')
with zipfile.ZipFile(p/'3.0.0.0.zip')as z:
 for n in z.namelist():
  if n.endswith(('iec61375-2-3.h','tau_marshall.c','tau_marshall.h','vos_types.h')):
   dest=p/'release'/n;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(n));print(n)
