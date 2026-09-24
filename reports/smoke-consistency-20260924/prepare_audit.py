"""Record this bounded smoke/consistency audit without changing prior campaigns."""
from pathlib import Path
import hashlib, importlib.util, json, subprocess, sys, os
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
CLI = Path('F:/CodexOrdner/plugins/cache/plugins-cli/tool-checker/1.0.0+codex.20260923165202/skills/tool-checker/scripts/tool_check.py')
TASK = 'smoke-consistency-20260924'
def save(name, data):
    (OUT/name).write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
def call(*args):
    result = subprocess.run([sys.executable,str(CLI),'--state',str(ROOT/'.tool-checker/state'),'--task',TASK,*args], capture_output=True,text=True)
    (OUT/'checker-setup.log').open('a',encoding='utf-8').write(result.stdout+result.stderr)
    if result.returncode: raise RuntimeError(result.stdout+result.stderr)
    return result.stdout

rules = ['WIZARD_EXECUTION_CONTRACT.md','WIZARD_RELEASE_GATE.md','SPATIAL_ARCHITECTURE_CONTRACT.md','COMMUNICATION_DESIGN_CONTRACT.md','NETWORK_NAMING_CONTRACT.md','GENERATION_RULE_MANAGER.md']
groups = [
 ('BACKEND','Full isolated backend regression','All collected backend tests finish with no failures; skips explicitly assessed.'),
 ('FRONTEND','Full frontend regression','All frontend library and agent tests pass.'),
 ('TYPES','TypeScript consistency','TypeScript compiler reports no errors.'),
 ('HTTP','Registered endpoint smoke','All registered backend and frontend method bindings dispatch without 5xx, 405, timeout or connection failure on the isolated stack.'),
 ('BROWSER','Browser functional continuity','All existing Playwright cases pass with actual persistence, workflow and trace assertions; blocked or skipped cases prevent full success.'),
 ('WORKFLOW','HTTP end-to-end workflow','Small and large real workflow acceptance pass with persisted model, simulation and complete scope evidence.'),
 ('REVIEW','Code and contract consistency review','Review current source, test coverage and runtime results for reproducible function continuity defects; unresolved findings remain failures.')]
source = {'title':'60-minute smoke and consistency audit','domain':'engineering','purpose':'User-requested bounded code/smoke/functional consistency assessment; does not supersede prior industry campaign or assert full product release acceptance.',
 'global_rules':['Never test the product database or product stack.','Collect all round results before repairs.','Retain existing user changes.','Report actual coverage and limits.'],
 'architecture_rules':[], 'rule_files':[str(ROOT/'docs'/n) for n in rules],
 'test_cases':[{'test_id':i,'title':title,'input':criterion,'source_lines':[1,1],'mutating':False,'browser_required':False,'completion_criteria':[criterion],'tags':['smoke','consistency'],'overall_timeout':3600} for i,title,criterion in groups]}
save('suite-source.json',source)
spec=importlib.util.spec_from_file_location('buildinfo',ROOT/'scripts/write-build-info.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
manifest=json.loads((OUT/'initial-source.json').read_text()) if (OUT/'initial-source.json').exists() else mod.build_manifest(); save('initial-source.json',manifest)
files=[]
for base in ['backend','frontend/src','frontend/e2e','frontend/scripts','config','scripts']:
    for directory, dirs, names in os.walk(ROOT/base):
        dirs[:] = [d for d in dirs if d not in {'.venv','runtime','test-output','__pycache__','generated','node_modules','.pytest_cache','backend'}]
        for name in names:
            p=Path(directory)/name
            if p.suffix in {'.py','.ts','.tsx','.mjs','.json'}: files.append(str(p))
save('build.json',{'build_id':manifest['build_id'],'commit_id':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'skill_version':'tool-checker-1.2.0','mcp_registry_version':'content-hashed source','model_schema_version':'content-hashed source','technology_profile_version':'content-hashed source','files':sorted(set(files))})
status=subprocess.run(['git','status','--short','--untracked-files=no'],cwd=ROOT,capture_output=True,text=True)
(OUT/'initial-git-status.txt').write_text(status.stdout+status.stderr,encoding='utf-8')
save('inventory.json',{'scope':source['purpose'],'started_at':datetime.now(timezone.utc).isoformat(),'deadline':'2026-09-24T08:14:22+00:00','groups':groups,'source_manifest':manifest,'prior_campaigns':'Preserved; separate user-requested smoke/consistency scope.','rules':[{'path':str(ROOT/'docs'/n),'sha256':hashlib.sha256((ROOT/'docs'/n).read_bytes()).hexdigest()} for n in rules]})
call('ingest',str(OUT/'suite-source.json'),'--id',TASK)
call('verify-source')
(OUT/'dry-run.json').write_text(call('dry-run','all'),encoding='utf-8')
call('campaign','start','--id',TASK)
call('campaign','run','--id',TASK,'--build',str(OUT/'build.json'))
print('Audit inventory and campaign recorded.')
