import hashlib, json, shutil, subprocess
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FILES = ['frontend/src/features/workflow/stage_08_results_analysis/results-workbench.tsx', 'frontend/src/features/workflow/stage_09_intelligence/intelligence-workbench.tsx', 'frontend/src/app/globals.css', 'AGENTS.md']
NEW = ['frontend/src/features/workflow/stage_08_results_analysis/runtime-chart-tools.tsx', 'frontend/src/features/workflow/stage_08_results_analysis/runtime-chart-data.ts', 'frontend/src/features/workflow/stage_08_results_analysis/runtime-chart-data.test.mjs']
def evidence(p): return {'path':str(p), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
before=[]; revisions={}
for name in FILES:
    p=ROOT/name; target=HERE/'before'/name
    target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(p,target)
    before.append(evidence(target)); revisions[name]=evidence(p)['sha256']
for name in NEW:
    assert not (ROOT/name).exists(); revisions[name]=None
w={'goal_id':HERE.name,'goal_type':'implementation','kind':'implementation','repository':str(ROOT),
   'project_scope':'NIS results/intelligence UI, saved simulation chart tools',
   'requested_change':'Remove sizing from Intelligence and standalone stale Results banner; fill expanded charts, add model views, zoom/types/network overlays and partner jitter; explain forecast vs simulated evidence. Small checks and direct frontend delivery, no image/full run.',
   'modify_code':True,'allow_repair':True,'revision_before':revisions,'before':before,
   'required_outcomes':['placement','expanded_charts_model_views','trend_tools','partner_jitter','forecast_provenance','verified_direct_production_delivery'],
   'validation_requirements':['typecheck','chart_data','focused_browser','production'],
   'constraints':['Only small scoped checks, no image/full release gate','Preserve frozen model, source identity and unknown evidence'],
   'forbidden_changes':['No backend/model/database changes','No EIP deployment','No full PASS claim'],
   'unresolved_decisions':[],'files_changed':FILES+NEW,'implementation_plan':['Reuse saved metrics and chart architecture','Finite values, actual interval evidence and explicit limits','Build staged frontend and roll back if unhealthy','Focused data/type/browser checks and verify artifact'],
   'delivery':{'decision':'YES','authorization':'Standing human instruction: small checks, no image or big test, direct production','target':'Existing NetworkIS frontend'},'completion_status':'IMPLEMENTING'}
(HERE/'workload.json').write_text(json.dumps(w,indent=2),encoding='utf-8')
docker=json.loads((ROOT/'config/networkis.resources.json').read_text())['paths']['docker_cli']
code="""import json,urllib.request
base='http://127.0.0.1:15050/api/engineering'
def get(path):
 return json.load(urllib.request.urlopen(urllib.request.Request(base+path,headers={'X-Project-ID':'20261009072206008-4bb505f1'}),timeout=90))
s=get('/workflow/simulation-snapshots/9992352a-af18-4a63-a50b-52d7e77ce4df?view=configuration')
r=s.get('calculated_metrics') or {}
print(json.dumps({'snapshot':s.get('id'),'overview':r.get('overview'),'network_examples':(r.get('networks') or [])[:2],'keys':list(r)}))
"""
result=subprocess.check_output([docker,'exec','NetworkIS','python','-c',code],text=True)
(HERE/'forecast-source.json').write_text(result,encoding='utf-8')
data=json.loads(result)
print(json.dumps({'snapshot':data['snapshot'],'overview':data['overview'],'network':data['network_examples'][:1]},indent=2))
