"""Read-only input-size diagnosis; no inference, model writes or acceptance."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration.project_intake import prepare_reference_design
from backend.nis.engineering.projects.project_context import activate_project, reset_project
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.engineering.communication.device_communication import FUNCTIONAL_DEVICE_REASONING_RULES
from backend.nis.engineering.structure.spatial_architecture import REASONING_RULES

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--state', required=True, type=Path)
args = parser.parse_args()
state = json.loads(args.state.read_text(encoding='utf-8'))
request_file = args.state.parent / 'plan-reference/request.json'
payload = json.loads(request_file.read_text(encoding='utf-8'))
token = activate_project(state['project_id'])
try:
    prepared = prepare_reference_design(payload)  # Existing pure product catalogs.
finally:
    reset_project(token)
with urlopen(Request(state['base_url'] + '/api/engineering/agent/project-draft',
                     headers={'X-Project-ID': state['project_id']}), timeout=20) as response:
    draft = json.load(response)['data']
assert draft['reference_generation']['request_sha256'] == prepared['request_sha256']
catalog = deepcopy(prepared['catalog'])
# Reconstruct the documented prompt projection in the frozen local reasoner.
# This is only size inspection, never an alternative model-planning path.
catalog['source_function_assignments'] = {key: catalog.get('source_function_assignments', {}).get(identity)
    for key, identity in prepared['fact_id_map'].items() if identity in catalog.get('source_function_assignments', {})}
catalog['source_devices'] = [{key: row[key] for key in ('name', 'device_type') if key in row}
                             for row in catalog.get('source_devices', [])]
catalog.pop('name_aliases', None)
technologies = {}
for item in prepared['source_evidence'].get('technologies') or []:
    if item.get('kind') != 'TRANSPORT':
        continue
    technology = registry.normalize_id(item['name'])
    try:
        definition = registry.profile(technology)
    except (KeyError, ValueError):
        continue
    technologies[technology] = {
        'rate_model': definition['rate_model'],
        'parameters': {key: {name: field[name] for name in ('type', 'required', 'unit', 'min', 'max', 'options', 'enum') if name in field}
                       for key, field in definition['parameter_schema'].items()},
        'parameter_roles': registry.parameter_roles(technology),
        'parameter_aliases': definition.get('parameter_aliases') or {},
    }
catalog['technology_parameters'] = technologies


def size(value):
    return len(json.dumps(value, ensure_ascii=False).encode('utf-8'))


result = {
    'at_utc': datetime.now(timezone.utc).isoformat(), 'scope': __doc__,
    'project_id': state['project_id'], 'image_id': state['image_id'],
    'source_sha256': state['source_sha256'], 'original_sha256': state['original_sha256'],
    'active_request_sha256': prepared['request_sha256'],
    'request_file_sha256': hashlib.sha256(request_file.read_bytes()).hexdigest(),
    'catalog_sha256': prepared['catalog_sha256'],
    'catalog_projected_json_bytes': size(catalog),
    'catalog_fields_json_bytes': {key: size(value) for key, value in catalog.items()},
    'technology_fields_json_bytes': {key: size(value) for key, value in technologies.items()},
    'source_text_utf8_bytes': len(prepared['source_evidence']['source_text'].encode('utf-8')),
    'source_facts_count_by_kind': dict(Counter(row['kind'] for row in prepared['facts'].values())),
    'reference_sources_json_bytes': size(prepared['reference_sources']),
    'functional_rules_utf8_bytes': len(FUNCTIONAL_DEVICE_REASONING_RULES.encode('utf-8')),
    'spatial_rules_utf8_bytes': len(REASONING_RULES.encode('utf-8')),
    'inference_calls_sent': 0, 'canonical_writes': False,
    'semantic_plan_pass': False, 'simulation_pass': False,
}
destination = args.state.parent / 'reference-input-size-analysis.json'
assert not destination.exists()
destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
