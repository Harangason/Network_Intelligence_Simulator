import json
from pathlib import Path
from industry50_adapter import request
p=Path('.tool-checker/evidence/industry50/S28');j=json.loads((p/'canonical-job-result.json').read_text(encoding='utf8'));print('resultkeys',j['result'].keys());code,body=request('http://127.0.0.1:60023','nis-e2e-industry50-s28','/api/simulations/'+j['id']+'/trace-window?start_s=11&end_s=15&limit=1000');(p/'trace-window.json').write_text(body,encoding='utf8');print('trace http',code);print(json.dumps(j['result'].get('runtime_metrics'),ensure_ascii=False)[:5000])
