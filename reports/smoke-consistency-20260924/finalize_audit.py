"""Verify the final tested source and record the bounded repair result."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, subprocess, sys

ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).resolve().parent
EXCLUDED={'.venv','node_modules','runtime','test-output','tests','__pycache__','generated'}
paths=set()
for relative,suffix in [('backend','.py'),('frontend/src',None),('frontend/scripts',None),('config','.json')]:
    for directory,dirs,names in os.walk(ROOT/relative):
        dirs[:]=[d for d in dirs if d not in EXCLUDED]
        for name in names:
            p=Path(directory)/name
            if suffix is None or p.suffix==suffix: paths.add(p)
paths.update((ROOT/'frontend').glob('*config*'))
paths.update(ROOT/name for name in ('Dockerfile','.dockerignore','generate_realistic_communication_tool.py','scripts/write-build-info.py',
 'scripts/verify-runtime-lock.py','backend/requirements.txt','backend/requirements.lock','backend/pyproject.toml','backend/uv.lock','frontend/package.json','frontend/package-lock.json'))
hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in sorted(paths)
        if p.is_file() and not EXCLUDED.intersection(p.relative_to(ROOT).parts) and p.suffix not in {'.pyc','.tsbuildinfo'}}
source=hashlib.sha256(json.dumps(hashes,sort_keys=True,separators=(',',':')).encode()).hexdigest()
receipt=json.loads((OUT/'repaired-stack/655ad99ad418/receipt.json').read_text())
assert source==receipt['release']['source_sha256'], (source,receipt['release']['source_sha256'])
def save(name,data):
    p=OUT/name;p.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');return str(p)
save('final-source.json',{'checked_at':datetime.now(timezone.utc).isoformat(),'source_sha256':source,'file_count':len(hashes),'matches_tested_image':True,'files':hashes})
affected=['backend/engineering/api.py','backend/engineering/goal_execution/store.py','backend/engineering/agent_tools/capabilities.py','backend/engineering/spatial_zoning.py','backend/app/trace_storage.py','backend/tests/test_smoke_error_contracts.py','backend/tests/test_trace_storage.py']
repair={'repair_id':'AUDIT-API-EMPTY-PROJECT','finding_ids':['556b71962e8ec9cf8843'],'status':'RESOLVED',
 'root_cause':'Unhandled domain/missing-resource exceptions, missing topology fields, and scandir on a lazily-created default output folder.',
 'root_cause_id':'api-input-and-empty-state-contracts','affected_files':[str(ROOT/p) for p in affected],
 'affected_tests':['HTTP'],'required_fix':'Return domain 400/404 responses, preserve revision conflicts, reject absent topology, and browse unused default storage without hiding unavailable custom storage.',
 'acceptance_criteria':['All 284 dispatch bindings produce no server errors.','129 repair and dependent regressions pass.','Project isolation, revision conflicts and real internal exception behavior remain correct.'],
 'regression_scope':'Targeted repair verification only; open consumer/acceptance mismatch prevents full repeat.',
 'verification_passed':True,'evidence':[str(OUT/n) for n in ['repair-regression.xml','http-smoke-repaired.json','workflow-small-repaired.json','browser-repair.json','final-source.json']]}
path=save('repair-record.json',repair)
cli='F:/CodexOrdner/plugins/cache/plugins-cli/tool-checker/1.0.0+codex.20260923165202/skills/tool-checker/scripts/tool_check.py'
p=subprocess.run([sys.executable,cli,'--state',str(ROOT/'.tool-checker/state'),'--task','smoke-consistency-20260924','campaign','repair-record','--id','smoke-consistency-20260924','--file',path],capture_output=True,text=True,encoding='utf-8')
(OUT/'repair-record-result.json').write_text(p.stdout+p.stderr,encoding='utf-8')
if p.returncode: raise RuntimeError(p.stdout+p.stderr)
save('final-result.json',{'finished_at':datetime.now(timezone.utc).isoformat(),'overall':'NOT_PASSED','reason':'AUDIT-01: unconfirmed status consumers / incompatible legacy positive acceptance fixtures remain unresolved.',
 'initial_backend':{'passed':1989,'failed':10,'errors':4,'skipped':2},'initial_frontend':{'passed':449},'initial_browser':{'passed':66,'failed':2},
 'repairs':{'AUDIT-02':'RESOLVED','AUDIT-03':'RESOLVED','targeted_backend_passed':129,'http_bindings':284,'http_failures':0,'targeted_browser_passed':4,'small_http_workflow':'PASSED'},
 'final_source_sha256':source,'deployed':False,'full_retest':False})
print(json.dumps({'source_matches':True,'file_count':len(hashes),'repairs_recorded':True}))
