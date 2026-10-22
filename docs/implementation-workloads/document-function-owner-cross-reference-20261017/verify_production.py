"""Read-only exact image, source files and actual source-owner counterprobe."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.request import urlopen

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('receipt', type=Path)
args = parser.parse_args()
receipt = json.loads(args.receipt.read_text(encoding='utf-8'))
freeze = json.loads((OUT / 'source-freeze.json').read_text(encoding='utf-8'))
assert receipt['status'] == 'PASS'
assert receipt['initial_source_sha256'] == freeze['source_sha256']
assert receipt['verification_sha256'] == freeze['verification_sha256']
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']


def read_docker(*command, payload=None):
    result = subprocess.run([docker, *command], input=payload, capture_output=True, text=True, encoding='utf-8', check=True)
    return result.stdout.strip()


image = read_docker('inspect', 'NetworkIS', '--format', '{{.Image}}')
assert image == receipt['image_id']
with urlopen('http://127.0.0.1:13500/api/ready', timeout=20) as response:
    ready = json.load(response)
with urlopen('http://127.0.0.1:13500/api/build-info', timeout=20) as response:
    build = json.load(response)
assert ready['status'] == 'ready' and build['source_sha256'] == freeze['source_sha256']
code = "import hashlib,json,sys;from pathlib import Path;print(json.dumps({p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in json.load(sys.stdin)}))"
actual = json.loads(read_docker('exec', '-i', 'NetworkIS', 'python', '-c', code, payload=json.dumps(list(freeze['files']))))
assert actual == freeze['files']
inputs_raw = (OUT / 'actual-source-counterprobe-inputs.json').read_text(encoding='utf-8')
node = """import fs from 'node:fs';
import assert from 'node:assert/strict';
import {documentSourceFunctionAssignments,documentFactIdentity} from './frontend/src/features/agent/lib/document-clarification.ts';
const x=JSON.parse(fs.readFileSync(0,'utf8'));
const result=documentSourceFunctionAssignments(x.facts,x.owners);
assert.equal(Object.keys(result).length,23);
const global=x.facts.find(f=>f.name==='Fahrdynamikregelung'&&f.source_context[0]==='4. Systemfunktionen');
assert.equal(result[documentFactIdentity(global)],'Chassis Domain Controller (CDC)');
assert.equal(x.facts.filter(f=>f.kind==='FUNCTION'&&!result[documentFactIdentity(f)]).length,15);
console.log(JSON.stringify({status:'PASSED',assignments:23,unresolved:15,global_owner:result[documentFactIdentity(global)]}));"""
frontend = json.loads(read_docker('exec', '-i', 'NetworkIS', 'node', '--experimental-strip-types', '--input-type=module', '-e', node, payload=inputs_raw))
backend_code = """import ast,json,sys
from pathlib import Path
x=json.load(sys.stdin)
tree=ast.parse(Path('backend/nis/agent/tools/wizard_generation.py').read_text())
nodes=[n for n in tree.body if (isinstance(n,ast.FunctionDef) and n.name=='_reviewed_document_functions') or (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_CONTROLLER_DEVICE_TYPES' for t in n.targets))]
assert len(nodes)==2
ns={};exec(compile(ast.Module(body=nodes,type_ignores=[]),'actual_product_pure_method','exec'),ns)
pair=[f for f in x['facts'] if f['name']=='Fahrdynamikregelung'];assert len(pair)==2
chains=[{'hardware_name':o['name'],'device_type':'ECU','configuration':{'document_equipment_evidence':{'source_context':o['source_context']},'source_scoped_functions':o['duties']}} for o in x['owners']]
result=ns['_reviewed_document_functions']({'components':pair,'source_sha256':'86865975c689643d9b07ea73e21d68fa6f4a3a8770402ffb537dba2d7ecdf4d7'},[o['name'].casefold() for o in x['owners']],chains)
assert len(result)==2 and len({r['fact_id'] for r in result})==2
assert all(r['host']=='chassis domain controller (cdc)' and r['assignment_source']=='source_scoped_function' for r in result)
print(json.dumps({'status':'PASSED','distinct_source_ids':2,'source_provenance':'source_scoped_function','owner':'chassis domain controller (cdc)'}))"""
backend = json.loads(read_docker('exec', '-i', 'NetworkIS', 'python', '-c', backend_code, payload=inputs_raw))
assert read_docker('inspect', 'NetworkIS', '--format', '{{.Image}}') == image
record = {'status': 'PASSED', 'at_utc': datetime.now(timezone.utc).isoformat(),
          'scope': 'Read-only production identity, readiness, sixteen frozen files and actual original-source pure method probes in the running image. Not a native UI, generated model or simulation PASS.',
          'receipt': str(args.receipt.resolve()), 'receipt_sha256': hashlib.sha256(args.receipt.read_bytes()).hexdigest(),
          'image_id': image, 'source_sha256': build['source_sha256'], 'ready': ready,
          'source_file_hashes': actual, 'frontend_actual_source_probe': frontend, 'backend_actual_source_probe': backend,
          'source_inputs_sha256': hashlib.sha256(inputs_raw.encode()).hexdigest(),
          'project_id': '20261016122109077-dc3a1aeb', 'canonical_writes': False}
(OUT / 'production-verification.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': record['status'], 'image_id': image, 'source_sha256': build['source_sha256']}))
