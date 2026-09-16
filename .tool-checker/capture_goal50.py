import json
from pathlib import Path
from industry50_fixtures import api
p=Path('.tool-checker/evidence/industry50/S24');s=json.loads((p/'completed.json').read_text(encoding='utf8'))['conversation']['data']['data'];g=api('nis-e2e-industry50-s24','execution-goals/'+s['active_workload']);(p/'goal.json').write_text(json.dumps(g,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(g,ensure_ascii=False)[-1800:])
(p/'scripted-decision.json').write_text(json.dumps({'decision_source':'SCRIPTED_TEST','decision':'Direkt über Chassis_CAN · CAN_FD','source':'S24 explicitly instructs Ja – direkt anbinden','workload_id':s['active_workload']}),encoding='utf8')
