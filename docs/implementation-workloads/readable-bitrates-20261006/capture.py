import json, sys
from pathlib import Path
from urllib.request import Request, urlopen

out=Path(__file__).parent/sys.argv[1]
out.mkdir(exist_ok=True)
for name,path in {
    'parameters':'/api/engineering/workflow/parameters',
    'build':'/api/build-info', 'ready':'/api/ready',
}.items():
    with urlopen(Request('http://localhost:13500'+path,headers={'X-Project-ID':'20261006151837393-c677c6ca'}),timeout=60) as response:
        value=json.load(response)
    (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    if name=='parameters':
        print({t:{k:v for k,v in g['values'].items() if 'bitrate' in k} for t,g in value['parameters']['simulation_parameter_assumptions'].items()})
    elif name=='build': print(value)
