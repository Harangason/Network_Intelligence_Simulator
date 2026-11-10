"""Compare every schema value to the preserved pre-order implementation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
from backend.nis.agent.orchestration import local_reasoner as current
from backend.tests.test_reference_port_intent_allocation import prepared_schema
from backend.tests.test_reference_planning_throughput import existing_batch_fixture

spec = importlib.util.spec_from_file_location('before_order', HERE/'before-order-local_reasoner.py')
before = importlib.util.module_from_spec(spec)
spec.loader.exec_module(before)
prepared, _ = prepared_schema()
inventory, known, fact, _, _, _ = existing_batch_fixture()
cases = [
    ('port_groups', prepared, {'ports'}, {'port_groups': True, 'device_ids': ('owner-a','owner-b')}),
    ('port_intents', prepared, {'ports'}, {'port_intent': True, 'device_ids': ('owner-a','owner-b')}),
    ('port_parameters', prepared, {'ports'}, {'port_ids': ('port-1',)}),
    ('functions', prepared, {'functions','functional_dependencies'}, {'function_ids': ('fact-1',)}),
    ('inventory', inventory, {'devices'}, {'derivation_fact_ids': [fact], 'existing_devices': known}),
    ('measurements', prepared, {'measurements'}, {}),
    ('commands', prepared, {'commands'}, {}),
    ('communication', prepared, {'communication'}, {}),
]
rows=[]
for name, data, fields, options in cases:
    old = before._reference_schema_for_stage(data, fields, **options)
    new = current._reference_schema_for_stage(data, fields, **options)
    assert old == new, name
    canonical = json.dumps(new, sort_keys=True, ensure_ascii=False, separators=(',',':'))
    rows.append({'stage': name, 'all_values_identical': True,
                 'canonical_sha256': hashlib.sha256(canonical.encode()).hexdigest(),
                 'before_order': list(old['properties']), 'after_order': list(new['properties'])})
report={'status':'PASS','schemas':rows,
        'before_sha256':hashlib.sha256((HERE/'before-order-local_reasoner.py').read_bytes()).hexdigest(),
        'after_sha256':hashlib.sha256((ROOT/'backend/nis/agent/orchestration/local_reasoner.py').read_bytes()).hexdigest()}
(HERE/'schema-order-equivalence.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'PASS','semantically_identical_stage_schemas':len(rows)}))
