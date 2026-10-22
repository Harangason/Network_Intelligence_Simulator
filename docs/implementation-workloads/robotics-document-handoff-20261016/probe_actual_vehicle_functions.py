"""Read-only counterprobe of the shared parser on the exact vehicle source."""
from pathlib import Path
import hashlib
import json
import sys
OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration.project_intake import document_component_sources, document_source_references
path = Path('C:/Users/marti/PycharmProjects/Benchmark_Modelle/Fahrzeug komplett.txt')
data = path.read_bytes()
assert hashlib.sha256(data).hexdigest() == '86865975c689643d9b07ea73e21d68fa6f4a3a8770402ffb537dba2d7ecdf4d7'
units = document_component_sources(document_source_references(data.decode('utf-8')))
adc = [unit for unit in units if any(label.endswith('(ADC)') for label in unit['source_context'])
       and unit['policy'] and unit['policy']['kind'] == 'FUNCTION']
assert len(adc) == 4, adc
assert [unit['text'].split(' (')[0] for unit in adc] == ['Sensorfusion', 'Perception', 'Planning', 'Vehicle Control']
assert len({unit['source_ref'] for unit in adc}) == 4
assert all(unit['required'] and not any(word in unit['text'] for word in ['Plattform:', 'AUTOSAR', 'Schnittstellen:']) for unit in adc)
controllers = [unit for unit in units if unit['policy'] and unit['policy']['kind'] == 'INSTANCE' and unit['policy']['role'] == 'CONTROLLER']
assert len(controllers) == 5
result = {'status': 'PASSED', 'scope': 'Deterministic original vehicle source only; no Qwen, UI, SQL or model writes.', 'parser_sha256': hashlib.sha256((ROOT / 'backend/nis/agent/orchestration/project_intake.py').read_bytes()).hexdigest(), 'controller_count': len(controllers), 'adc_functions': adc}
(OUT / 'actual-vehicle-function-boundaries.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'status': 'PASSED', 'controllers': len(controllers), 'distinct_adc_functions': len(adc)}))
