"""Read the canonical pure projection owner; never regenerate/copy artifacts."""
from pathlib import Path
import hashlib
import importlib.util
import json

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
owner = ROOT / 'scripts/build/project-vocabulary.py'
spec = importlib.util.spec_from_file_location('readonly_technology_projection_owner', owner)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
artifact = ROOT / 'frontend/src/features/communication/lib/technology-projection.json'
actual = json.loads(artifact.read_text(encoding='utf-8'))
expected = module.technology_projection(ROOT)
assert actual == expected, 'Generated frontend projection differs from its canonical pure owner'
assert not any('role' in key for item in actual['technologies'] for key in item)
report = {'status': 'PASSED_READONLY_PROJECTION_CONSISTENCY', 'technology_count': len(actual['technologies']),
    'source_sha256': actual['source_sha256'], 'artifact_sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(),
    'owner': str(owner), 'owner_sha256': hashlib.sha256(owner.read_bytes()).hexdigest(),
    'projection_fields': list(actual['technologies'][0]),
    'role_source': 'Runtime TechnologyRegistry.parameter_fields / parameter_roles via communication.catalog.parameter_value_role; no roles in this static projection.',
    'regeneration_required': False, 'application_source_changed': False,
    'existing_check': 'backend/tests/test_structure_completion.py::test_frontend_technology_data_is_exact_backend_projection'}
(OUT / 'projection-role-consistency.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
