"""Record only a fresh passing isolated run and explicitly supplied source scopes."""
from pathlib import Path
import hashlib,importlib,json,sys,xml.etree.ElementTree as ET
root=Path.cwd();sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
spec=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'));tech=spec['technology'];n=importlib.import_module('backend.communication.technologies.'+tech)
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual'/f'{tech}-tests.xml'
for file in(f'backend/communication/technologies/{tech}.py',f'backend/tests/test_{tech}_parameter_review.py','backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py',*spec.get('additional_verified_paths',[])):
 assert xml.stat().st_mtime_ns>=(root/file).stat().st_mtime_ns,('stale',file)
p=ET.parse(xml);s=p.findall('.//testsuite');assert s and all(int(v.get(k,'0'))==0 for v in s for k in('failures','errors','skipped'))
cases=p.findall('.//testcase');native=sum(c.get('classname','').endswith(f'test_{tech}_parameter_review')for c in cases)
assert native>=len(registry.parameter_fields(tech))+10 and len({c.get('classname')for c in cases})==10
reviewed=[];scopes=spec['source_read_scopes']
assert set(scopes)==set(n.SOURCES)
for entry in json.loads((root/spec['source_manifest']).read_text(encoding='utf-8')):
 if entry['url']not in scopes:continue
 assert hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()==entry['sha256']
 reviewed.append({**entry,'read_scope':scopes[entry['url']]})
assert len(reviewed)==len(scopes)
(folder/'source-reviews').mkdir(exist_ok=True)
(folder/'source-reviews'/f'{tech}.json').write_text(json.dumps(reviewed,indent=2)+'\n')
before={v['key']for v in next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']==tech)['form_parameters']};after={v['key']for v in registry.parameter_fields(tech)}
meanings={v['key']:v['description']for v in n.DECLARATIONS};meanings.update(spec['additional_field_meanings'])
decisions=dict(technology=tech,native=meanings,removed={k:n.REMOVED[k]for k in before-after},sources=list(n.SOURCES),revisions=list(n.SOURCES.values()),scope=spec['scope']+[f'{len(cases)} isolated tests PASS, {native} native andnine shared suites.'],
 validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} {tech} native andnine shared suites',complete_release_gate='NOT_RUN'),not_certified=spec['not_certified'])
(root/'work'/f'{tech}-review-decisions.json').write_text(json.dumps(decisions,indent=2)+'\n');print(dict(tests=len(cases),native=native,fields=len(meanings),removed=len(before-after)))
