import json,time
from pathlib import Path
from industry60_adapter import request
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'.tool-checker/evidence/industry60-recheck/trace'
BASE='http://127.0.0.1:49546';PROJECT='nis-e2e-industry60-trace'
jobs={}
for label in ['golden-canonical','fault-canonical']:
    cfg=json.loads((OUT/(label+'-config.json')).read_text());cfg.pop('output_dir',None)
    code,body=request(BASE,PROJECT,'/api/simulations',{'project_id':PROJECT,'config':cfg})
    (OUT/(label+'-submitted.json')).write_text(body,encoding='utf8')
    if code!=202:raise RuntimeError((code,body))
    job=json.loads(body);jobs[label]=job['id'];print(label,job['id'],flush=True)
    for _ in range(120):
        code,body=request(BASE,PROJECT,'/api/simulations/'+job['id']);current=json.loads(body)
        if current['status'] in ['completed','failed','canceled']:
            (OUT/(label+'-job.json')).write_text(body,encoding='utf8');print(current['status'],flush=True);break
        time.sleep(1)
    code,body=request(BASE,PROJECT,'/api/simulations/'+job['id']+'/trace-window?start_s=12&end_s=16&limit=500')
    (OUT/(label+'-window.json')).write_text(body,encoding='utf8')
(OUT/'canonical-jobs.json').write_text(json.dumps({'project':PROJECT,'base':BASE,'jobs':jobs,'scope':'HTTP simulation jobs from reviewed explicit config; no canonical workflow snapshot fabricated'}),encoding='utf8')
