"""Record all native network rate proposals and reject placeholder minima."""
import json
from pathlib import Path
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.catalog import simulation_parameter_values

OUT = Path(__file__).resolve().parent
rows = []
for profile in registry.profiles():
    proposals = simulation_parameter_values(profile['id'], profile)
    for key in (profile.get('rate_model') or {}).get('fields', []):
        if key in proposals:
            assert proposals[key]['value'] > 1, (profile['id'], key)
    for field in registry.parameter_fields(profile['id']):
        if field.get('unit') == 'bit/s' and field.get('scope') == 'network':
            rows.append({'technology': profile['id'], 'field': field['key'],
                         'value': field['simulation_default'],
                         'basis': field['simulation_default_provenance']['basis'],
                         'hardware_evidence': field['simulation_default_provenance']['hardware_evidence']})
assert not any(isinstance(row['value'], (int, float)) and row['value'] == 1 for row in rows)
assert all(row['hardware_evidence'] is False for row in rows)
(OUT / 'registered-rate-audit.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'profiles': len(registry.profiles()), 'network_rate_fields': len(rows), 'placeholder_one_bit_rates': 0}))
