"""Pure staged parser counterprobe; no product modules, SQL or model writes."""
import importlib.util
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

out = Path(__file__).resolve().parent
sys.path.insert(0, str(out.parents[2]))
staged = out.parent / 'robotics-document-handoff-20261016/staged'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


load('backend.nis.agent.context.limits', staged / 'backend/nis/agent/context/limits.py')
parser = load('reviewed_staged_intake', staged / 'backend/nis/agent/orchestration/project_intake.py')
examples = {
    'safety_requirement': '# Safety\nREQ-SAFE-01: Das System MUSS Sensorausfälle erkennen.\n',
    'test_case_nonhardware': '# Testfälle\nTC-01: Motorcontroller muss Fehler melden.\n',
    'normal_requirement': '# Anforderungen\nREQ-SAFE-01: Das System MUSS Sensorausfälle erkennen.\n',
}
report = {'scope': 'staged pure parser only', 'at': datetime.now(timezone.utc).isoformat(),
          'staged_parser_sha256': hashlib.sha256((staged / 'backend/nis/agent/orchestration/project_intake.py').read_bytes()).hexdigest(),
          'examples': {}}
for label, source in examples.items():
    units = parser.document_component_sources(parser.document_source_references(source))
    report['examples'][label] = units
plain_profiles = '1. Anlage Nord\n1.1 Architektur\nController: SPS\n2. Anlage Süd\n2.1 Architektur\nController: SPS\n'
profile_units = parser.document_component_sources(parser.document_source_references(plain_profiles))
profile_facts = [{'name': 'SPS', 'kind': unit['policy']['kind'], 'role': unit['policy']['role'],
                  'quantity': unit['policy']['quantity'], 'source_quote': unit['text'],
                  'source_context': unit.get('source_context', [])}
                 for unit in profile_units if unit['text'] == 'Controller: SPS']
composed_profiles = parser.compose_document_proposal([{'components': profile_facts, 'technologies': []}])
report['plain_numbered_profiles'] = {'source': plain_profiles, 'source_units': profile_units,
    'facts_before_composition': len(profile_facts), 'facts_after_composition': len(composed_profiles['components']),
    'status': 'PASSED' if len(profile_facts) == len(composed_profiles['components']) == 2 else 'FAILED'}
original_bytes = Path('C:/Users/marti/PycharmProjects/Benchmark_Modelle/Fahrzeug komplett.txt').read_bytes()
original = original_bytes.decode('utf-8')
units = parser.document_component_sources(parser.document_source_references(original))
def ids(text):
    normalized = re.sub(r'[\u2010-\u2015\u2212\ufe63\uff0d]', '-', unicodedata.normalize('NFKC', text))
    return set(re.findall(r'\bREQ[-_][\w-]+', normalized))
expected = ids(original)
retained = ids('\n'.join(unit['text'] for unit in units if (unit.get('policy') or {}).get('kind') == 'REQUIREMENT'))
assert len(expected) == 168
report['original_vehicle_policy'] = {
    'scope': 'deterministic staged component-source policy only; no Qwen, Wizard or simulation',
    'source_sha256': hashlib.sha256(original_bytes).hexdigest(), 'source_chars': len(original),
    'literal_requirement_ids': len(expected), 'retained_requirement_ids': len(retained),
    'missing_requirement_ids': sorted(expected - retained),
}
assert expected <= retained, report['original_vehicle_policy']
(out / 'peer-staged-counterprobe.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=True))
assert report['plain_numbered_profiles']['status'] == 'PASSED', 'Two distinct numbered source profiles were merged.'
