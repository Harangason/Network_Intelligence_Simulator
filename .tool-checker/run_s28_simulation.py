import json,time
from pathlib import Path
from industry50_adapter import request
p=Path('.tool-checker/evidence/industry50/S28');cfg=json.loads((p/'generated-trace.json').read_text(encoding='utf8'))['configuration'];cfg.pop('output_dir',None);payload={'project_id':'nis-e2e-industry50-s28','config':cfg};(p/'job-request.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8')
code,body=request('http://127.0.0.1:60023','nis-e2e-industry50-s28','/api/simulations',payload);(p/'job-submitted.json').write_text(body,encoding='utf8');assert code==202,(code,body);job=json.loads(body);print(job['id'],flush=True)
for _ in range(60):
 code,body=request('http://127.0.0.1:60023','nis-e2e-industry50-s28','/api/simulations/'+job['id']);current=json.loads(body)
 if current['status'] in ['completed','failed','canceled']:
  (p/'job-result.json').write_text(body,encoding='utf8');print(current['status'],current.get('error'),flush=True);break
 time.sleep(1)
