"""Read-only baseline of this user's explicitly selected project."""
import hashlib,json
from pathlib import Path
from urllib.request import Request,urlopen
out=Path(__file__).parent
before=json.loads((out/'live-before.json').read_text(encoding='utf-8'))
request=Request('http://127.0.0.1:13500/api/engineering/workflow/parameters',headers={'X-Project-ID':before['project']})
with urlopen(request,timeout=60) as response: values=json.load(response)['parameters']
digest=hashlib.sha256(json.dumps(values,sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert digest==before['parameter_sha256'],'User values changed since the recorded baseline; preserve the current values and investigate.'
path=out/'live-before-parameters.json'
if path.exists(): assert json.loads(path.read_text(encoding='utf-8'))==values
else: path.write_text(json.dumps(values,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'unchanged':True,'parameter_count':len(values),
  'simulation_groups':{key:len(group.get('values') or {}) for key,group in (values.get('simulation_parameter_assumptions') or {}).items()},
  'confirmed_groups':{key:len(group.get('values') or {}) for key,group in (values.get('technology_parameters') or {}).items()},
  'explicit_rate_technologies':list((values.get('explicit_technology_bitrates') or {}).keys()),
  'default_technologies':list((values.get('technology_defaults') or {}).keys())}))
