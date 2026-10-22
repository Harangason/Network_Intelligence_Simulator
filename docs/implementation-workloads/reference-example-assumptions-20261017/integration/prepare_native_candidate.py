"""Freeze verified inputs and prepare one normal production-build test candidate."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
module_spec = importlib.util.spec_from_file_location('release_delivery_owner',ROOT/'scripts/release-and-deploy.py')
owner = importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(owner)
source, commit, verification = owner.current_identity()
expected = json.loads((OUT/'current-release-input-identity.json').read_text(encoding='utf-8'))
assert (source,commit,verification) == tuple(expected[key] for key in ('source_sha256','commit_id','verification_sha256')), 'Source/test drift since the 159/143/typecheck verification'
removal = json.loads((OUT.parent/'archive-review-66a892b0b219/removal-result.json').read_text(encoding='utf-8'))
assert removal['status']=='REMOVED' and removal['image_count_after']==99 and removal['production_unchanged']
manifest = json.loads((OUT/'current-owned-manifest.json').read_text(encoding='utf-8'))
for relative,row in manifest.items():
    assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==row['current'], ('PLAN_STALE',relative)
env = {**os.environ,'NIS_E2E_LOCAL_AI_BASE_URL':'http://host.docker.internal:11434/v1'}
destination = ROOT/'backend/test-output/release-gates/reference-example-native-2d0d2b566456'
command = [sys.executable,str(ROOT/'scripts/run-release-gate.py'),'--prepare','--output',str(destination)]
record = {'at_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':source,'commit_id':commit,
    'verification_sha256':verification,'owned_file_hashes':{key:row['current'] for key,row in manifest.items()},
    'command':command,'output_directory':str(destination),'development_base':None,
    'local_ai_base_url':env['NIS_E2E_LOCAL_AI_BASE_URL'],'scope':'Normal production Dockerfile candidate preparation only; not a full release PASS or productive delivery.'}
(OUT/'candidate-freeze.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'STARTING_PREPARE','source':source,'output_directory':str(destination)}),flush=True)
result=subprocess.run(command,cwd=ROOT,env=env)
raise SystemExit(result.returncode)
