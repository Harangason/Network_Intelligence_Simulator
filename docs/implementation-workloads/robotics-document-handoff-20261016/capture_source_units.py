"""Record deterministic source obligations without inference or database access."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('robotics_canonical_intake_probe', ROOT / 'backend/nis/agent/orchestration/project_intake.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
baseline = json.loads((OUT.parent / 'industrial-robotics-wizard-20261016/source-baseline.json').read_text(encoding='utf-8'))
data = Path(baseline['file']).read_bytes()
assert hashlib.sha256(data).hexdigest() == baseline['source_sha256']
rows = module.document_source_references(data.decode('utf-8'))
units = module.document_component_sources(rows)
result = {'source_sha256': baseline['source_sha256'], 'scope': 'Deterministic literal source obligations only; no native inference, model write or database access', 'rows': rows, 'units': units}
(OUT / 'source-component-units.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'source_rows': len(rows), 'source_units': len(units), 'required_units': sum(bool(u['required']) for u in units)}))
