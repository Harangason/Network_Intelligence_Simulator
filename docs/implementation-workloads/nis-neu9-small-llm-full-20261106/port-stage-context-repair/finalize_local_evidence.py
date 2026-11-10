"""Freeze the verified stage-focus change; no original/model acceptance."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import difflib
import hashlib
import importlib.util
import json
import sys
import xml.etree.ElementTree as ET

d = Path(__file__).resolve().parent
g = d.parent
r = g.parents[2]
def read(p): return json.loads(p.read_text(encoding='utf8'))
def save(p, v): p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
def ref(p): return {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
assert not (d/'source-scope-proof.json').exists()
w = read(d/'workload.json')
reports = []
for name, session in [('green-stage-context.xml', 96603), ('regression-context-contracts.xml', 97725)]:
    suites = list(ET.parse(d/name).getroot().iter('testsuite'))
    totals = {k: sum(int(s.get(k, 0)) for s in suites) for k in ('tests', 'failures', 'errors', 'skipped')}
    assert totals['failures'] == totals['errors'] == totals['skipped'] == 0
    reports.append({'session': session, **totals, 'evidence': ref(d/name)})
assert read(d/'product-request-parity.json')['product_request_equals_control']
assert read(d/'neu9-product-focus/result.json')['counts'] == {f'counter-{i}': 1 for i in range(200, 204)}
assert read(d/'native-product-offline-parallel/result.json')['status'] == 'PASS'
assert read(d/'native-product-offline-parallel/result.json')['source_sha256'] == ref(r/'backend/nis/agent/orchestration/local_reasoner.py')['sha256']
a = ast.parse((d/'before/local_reasoner.py').read_text(encoding='utf8'))
b = ast.parse((r/'backend/nis/agent/orchestration/local_reasoner.py').read_text(encoding='utf8'))
for tree in (a, b):
    tree.body = [n for n in tree.body if not (isinstance(n, ast.FunctionDef) and n.name == '_reference_context_messages')]
assert ast.dump(a) == ast.dump(b)
save(d/'regression-aggregate.json', {'runs': reports, 'native_sessions': [92529, 26199],
    'scope': 'Stage focus only; generic authored inventory plus unchanged neu9 source is a diagnostic, not complete semantic acceptance.',
    'original_acceptance': False, 'production_delivered': False})
after = []
diff = []
for name in w['repair']['affected_files']:
    old = d/'before'/Path(name).name
    current = r/name
    saved = d/'after'/name
    saved.parent.mkdir(parents=True, exist_ok=True)
    saved.write_bytes(current.read_bytes())
    after.append(ref(saved))
    diff.extend(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True), current.read_text(encoding='utf8').splitlines(True), fromfile='before/'+name, tofile='after/'+name))
(d/'final-change.diff').write_text(''.join(diff), encoding='utf8')
evidence = [ref(d/p) for p in ('regression-aggregate.json', 'application-scope-proof.json',
    'native-control-scope-proof.json', 'product-request-parity.json', 'neu9-product-focus/result.json',
    'native-product-offline-parallel/result.json', 'red-stage-focus.xml', 'regression-context-contracts.xml')]
w.update(status='LOCALLY_VERIFIED_PENDING_FULL_ORIGINAL_AND_DELIVERY', files_changed=w['repair']['affected_files'], after=after, diff=[ref(d/'final-change.diff')])
w['outcomes'] = {k: {'status': 'PASSED', 'evidence': evidence} for k in w['required_outcomes']}
w['validations'] = {k: {'status': 'PASSED', 'evidence': evidence} for k in w['validation_requirements']}
w['completion_status'] = 'LOCAL_REPAIR_ONLY_FULL_ORIGINAL_AND_DELIVERY_PENDING'
save(d/'workload.json', w)
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m; spec.loader.exec_module(m)
    return m
source = module('stage_focus_build', r/'scripts/write-build-info.py').build_manifest()
verification = module('stage_focus_release', r/'scripts/run-release-gate.py').verification_manifest()
freeze = {'at': datetime.now(timezone.utc).isoformat(), 'source': source, 'verification': verification,
    'files': {name: ref(r/name)['sha256'] for name in w['repair']['affected_files']},
    'evidence': evidence, 'production_delivered': False}
save(d/'source-scope-proof.json', freeze)
rootwork = read(g/'workload.json')
save(d/'previous-freeze.json', {k: rootwork.get(k) for k in ('frozen_source', 'frozen_verification_sha256', 'frozen_files')})
rootwork['frozen_source'] = source
rootwork['frozen_verification_sha256'] = verification
rootwork['frozen_files'].update(freeze['files'])
for name, digest in rootwork['frozen_files'].items(): assert ref(r/name)['sha256'] == digest, name
assert len(rootwork['required_outcomes']) == len(rootwork['validation_requirements']) == 7
assert ref(Path(rootwork['source']['path']))['sha256'] == rootwork['source']['sha256']
rootwork['current_status'] = 'PORT_STAGE_LOCAL_NATIVE_CHECKS_PASSED_PREPARING_FRESH_ORIGINAL'
rootwork['final_local_repair_evidence'] = ref(d/'source-scope-proof.json')
save(g/'workload.json', rootwork)
print(json.dumps({'source': source, 'verification': verification, 'runs': reports}))
