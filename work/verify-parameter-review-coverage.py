"""Read-only cross-check between the audited inventory and the live registry."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['NIS_DISABLE_GENERATED_TECHNOLOGIES'] = '1'
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry

folder = ROOT / 'docs/implementation-workloads/technology-full-parameter-audit-20261001'
inventory = json.loads((folder / 'consumer-schema-inventory.json').read_text(encoding='utf-8'))
old = {row['technology']: row for row in inventory['profiles']}
rows = []
for profile in registry.profiles():
    identity = profile['id']
    fields = registry.parameter_fields(identity)
    record_path = folder / 'individual' / (identity + '.json')
    record = json.loads(record_path.read_text(encoding='utf-8'))
    assert record['technology'] == identity
    assert record['status'] == 'SOURCE_AND_LOCAL_RULES_REVIEWED'
    # Earlier records encode revision identifiers in the cited document URL
    # and per-field after metadata; the later top-level list is optional.
    assert record['sources']
    reviewed = {field['key'] for field in record['parameter_reviews']}
    current = {field['key'] for field in fields}
    current.update('local_timing_evidence.' + field['key'] for field in profile.get('local_timing_schema', []))
    missing = sorted(current - reviewed)
    expected = old[identity]
    assert expected['fields'] == len(fields), identity
    assert expected['constraints'] == len(profile.get('parameter_constraints') or []), identity
    assert expected['capacity'] == profile['capacity_evidence']['status'], identity
    rows.append({'technology': identity, 'current_fields_reviewed': len(current),
                 'missing_field_reviews': missing,
                 'record_sha256': hashlib.sha256(record_path.read_bytes()).hexdigest(),
                 'editor_fields': len(fields), 'constraints': expected['constraints'],
                 'capacity': expected['capacity']})
assert len(rows) == len(old) == 125
assert sum(row['editor_fields'] for row in rows) == inventory['total_fields']
assert sum(row['constraints'] for row in rows) == inventory['total_constraints']
missing_rows = [row for row in rows if row['missing_field_reviews']]
result = {'status': 'FAILED' if missing_rows else 'PASSED', 'profiles': len(rows), 'editor_fields': inventory['total_fields'],
          'constraints': inventory['total_constraints'], 'capacity': dict(Counter(row['capacity'] for row in rows)),
          'scope': 'Current profile field coverage, source references and inventory alignment; no claim of real hardware qualification.',
          'rows': rows}
path = ROOT / 'work/parameter-review-coverage.json'
path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({key: value for key, value in result.items() if key != 'rows'}))
print(json.dumps([{'technology': row['technology'], 'missing': row['missing_field_reviews']} for row in missing_rows]))
raise SystemExit(1 if missing_rows else 0)
