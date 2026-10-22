"""Audit the qualification repair before its coordinated canonical copy."""
from pathlib import Path
import hashlib
import json
import sys
from xml.etree import ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
stage = OUT / 'qualification-stage'
native = registry.validate_parameters('lin', {})
probe = {'scope': 'Read-only canonical metadata before the staged role correction; no inference/model/SQL execution.',
    'lin_roles': {name: registry.parameter_roles('lin')[name] for name in
                  ['lin_capacity_confirmed', 'lin_schedule_confirmed', 'lin_device_source', 'lin_commander_node_id', 'lin_bitrate_bps']},
    'native_findings': native['findings'],
    'canonical_sources': {relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() for relative in
                          ['backend/nis/communication/catalog.py', 'backend/nis/agent/orchestration/project_intake.py']}}
(stage / 'native-role-before.json').write_text(json.dumps(probe, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
latest = 'targeted-v3.xml' if (stage / 'targeted-v3.xml').is_file() else 'targeted-v2.xml'
suite = ET.parse(stage / latest).getroot().find('testsuite')
assert suite.attrib['failures'] == '0' and suite.attrib['errors'] == '0'
report = {'status': 'PASSED_STAGED_QUALIFICATION_COMPONENT_TESTS', 'tests': int(suite.attrib['tests']),
    'seconds': float(suite.attrib['time']), 'scope': 'Actual shared Node bridge and isolated database; canonical application unchanged.',
    'canonical_integration': 'PENDING', 'native_original_file_model_simulation': 'PENDING', 'production_delivery': 'PENDING'}
(stage / 'component-review.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
work = json.loads((stage / 'workload.json').read_text(encoding='utf-8'))
for filename in ['native-role-before.json', 'targeted.xml', 'targeted-v2.xml', latest]:
    path = stage / filename
    work['repair']['evidence'].append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
(stage / 'workload.json').write_text(json.dumps(work, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report))
