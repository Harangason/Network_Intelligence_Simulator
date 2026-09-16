import json,collections
from pathlib import Path
from industry50_adapter import request
r=Path('.tool-checker');m=json.loads((r/'industry50.normalized.json').read_text(encoding='utf8'));expected={c['id']:c['counts'] for c in json.loads(Path('tests/fixtures/industry40.json').read_text())['cases']}
for c in m['test_cases'][:40]:
 p=r/'evidence/industry50'/c['test_id'];f=p/'draft.json'
 if not f.exists() and (p/'history.json').exists():
  status,body=request('http://127.0.0.1:60023',c['execution_plan'][0]['project_id'],'/api/engineering/agent/project-draft');f.write_text(body,encoding='utf8')
 if not f.exists():continue
 d=json.loads(f.read_text())['data'];counts=collections.Counter(x['role'] for x in d['devices']);old=r/'evidence/industry40-stabilization-intake'/f"{c['test_id']}.json"
 oldc=collections.Counter(x['role'] for x in json.loads(old.read_text())['draft']['data']['devices']) if old.exists() else {}
 bad={role:(expected[c['test_id']][key],counts[role]) for key,role in [('sensors','SENSOR'),('actuators','ACTUATOR'),('ecus','CONTROLLER'),('gateways','GATEWAY')] if expected[c['test_id']][key] is not None and counts[role]!=expected[c['test_id']][key]}
 print(c['test_id'],'BAD',bad,'old',dict(oldc),'unknown',sum(not x['known_kind'] for x in d['devices']),len(d['devices']))
