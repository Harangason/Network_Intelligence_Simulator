"""Deterministic full-source parser/schema probe; never native acceptance."""
from pathlib import Path
import collections
import json
import sys
OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration.project_intake import (
    DocumentInterpretation, compose_document_proposal, document_component_sources,
    document_model_output_schema, document_output_schema, document_source_references,
    resolve_document_references, validate_document_interpretation)
source = (ROOT / 'frontend/e2e/fixtures/document-intake-industrial-robotics.md').read_text(encoding='utf-8')
rows = document_source_references(source)
units = document_component_sources(rows)
assert all(unit['policy'] for unit in units)
facts = []
for start in range(0, len(units), 20):
    facts.extend(resolve_document_references({'components': [{'source_ref': unit['source_ref'], **unit['policy']} for unit in units[start:start + 20]], 'technologies': []}, rows)['components'])
schema = document_model_output_schema(document_output_schema(source, DocumentInterpretation.model_json_schema()), rows)
technologies = resolve_document_references({'components': [], 'technologies': {key: item['enum'][0] for key, item in schema['properties']['technologies']['properties'].items()}}, rows, model_schema=schema)['technologies']
proposal = compose_document_proposal([{'components': facts, 'technologies': technologies}])
accepted = validate_document_interpretation(proposal, source, aggregate=True)
record = {'status': 'PASSED', 'scope': 'Deterministic source parser, output grammar and full-source validation only; no Qwen inference, Wizard interaction or model write.', 'component_counts': dict(collections.Counter(fact['kind'] for fact in accepted['components'])), 'technologies': technologies, 'required_source_units': len(units), 'components': accepted['components']}
(OUT / 'semantic-union-probe.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key: record[key] for key in ['status', 'scope', 'component_counts', 'required_source_units']}))
