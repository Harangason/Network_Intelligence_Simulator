"""Verify deployed source parsing and real UI evidence without product SQL tests."""
from pathlib import Path
import datetime
import json
import subprocess
OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[3]
NATIVE = OUT
identity = json.loads((OUT / 'production-identity-verification.json').read_text(encoding='utf-8'))
native = json.loads((NATIVE / 'native-verification.json').read_text(encoding='utf-8'))
ui = json.loads((OUT / 'production-ui-verification.json').read_text(encoding='utf-8'))
assert identity['status'] == native['status'] == ui['status'] == 'PASSED'
assert ui['image_id'] == identity['image_id']
assert ui['source_sha256'] == identity['source_sha256']
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']
assert subprocess.check_output([docker, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip() == identity['image_id']
program = '''from pathlib import Path
from collections import Counter
import hashlib,json,re,sys
from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
data=Path('/app/frontend/e2e/fixtures/document-intake-industrial-robotics.md').read_bytes()
assert hashlib.sha256(data).hexdigest()=='8fc201a55e8b0afeb7b708ac70abd0c72a7b25eb17d90fceca71d80a291f3cef'
source=data.decode('utf-8')
units=document_component_sources(document_source_references(source))
counts=Counter(unit['policy']['kind'] for unit in units)
assert dict(counts)=={'CATEGORY':68,'FUNCTION':97,'REQUIREMENT':50,'INSTANCE':1}
assert len(units)==216 and all(unit['required'] for unit in units)
requirements=[unit['text'] for unit in units if unit['policy']['kind']=='REQUIREMENT']
complete=re.findall(r'^- \\*\\*(REQ-\\d{3}-[A-Z]+-\\d{3}):\\*\\* ([^\\r\\n]+)',source,re.M)
assert len(complete)==110 and all(any(identifier in quote and text in quote for quote in requirements) for identifier,text in complete)
assert all('TC-' not in unit['text'] for unit in units)
assert not any(unit['policy']['kind'] in {'INSTANCE','CATEGORY'} and unit['text'] in {'MES','Historian','Fleet Manager','Lagerverwaltung','Safety Zones','Datenbank'} for unit in units)
assert not any(name.startswith(('sqlalchemy','psycopg')) for name in sys.modules), 'A pure source probe must not initialize a database stack'
print(json.dumps({'status':'PASSED','scope':'Read-only pure source parser in the actual production image; no SQL imports/statements, model writes, Qwen call or canonical generation.','source_sha256':hashlib.sha256(data).hexdigest(),'source_chars':len(source),'required_units':len(units),'component_counts':dict(counts),'complete_requirements':len(complete)}))
'''
result = subprocess.run([docker, 'exec', '-i', 'NetworkIS', 'python', '-'], input=program, capture_output=True, text=True, encoding='utf-8', check=True)
probe = json.loads(result.stdout)
assert probe['status'] == 'PASSED'
record = {'status': 'PASSED', 'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'scope': 'Full original-file native Wizard and exact handoff previously verified on this same immutable image; production additionally verifies exact image, source parsing of original bytes and real UI startup. No second production Qwen run or nine-stage robot-model claim.',
          'image_id': identity['image_id'], 'source_sha256': identity['source_sha256'], 'source_parser': probe,
          'native_acceptance': str(NATIVE / 'native-verification.json'), 'ui': ui}
(OUT / 'production-functional-verification.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'status': 'PASSED', 'image_id': record['image_id'], 'source_sha256': record['source_sha256']}))
