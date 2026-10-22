"""Verify actual proposed full source coverage before normal UI adoption."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

OUT = Path(__file__).parent.resolve()
baseline = json.loads((OUT.parents[1] / 'industrial-robotics-wizard-20261016/source-baseline.json').read_text(encoding='utf-8'))
data = Path(baseline['file']).read_bytes()
assert hashlib.sha256(data).hexdigest() == baseline['source_sha256']
source = data.decode('utf-8')
facts = json.loads((OUT / 'native-proposal-facts.json').read_text(encoding='utf-8'))
obligations = json.loads((OUT / 'source-component-units.json').read_text(encoding='utf-8'))
runtime = json.loads((OUT / 'native-runtime-preparation.json').read_text(encoding='utf-8'))
rows = {row['source_ref']: row['text'].strip() for row in obligations['rows']}
missing_units = []
for unit in obligations['units']:
    if not unit['required']:
        continue
    policy = unit.get('policy')
    for piece in [rows[ref] for ref in unit.get('source_rows', [])] or [unit['text']]:
        if not any(piece in fact['quote']
                   and (not unit.get('source_quote') or fact['name'] == unit['text'][:120])
                   and ' / '.join(unit.get('source_context', [])) in fact['context']
                   and (not policy or all(fact[key] == policy[key] for key in ('kind', 'role', 'quantity')))
                   for fact in facts):
            missing_units.append({'source_ref': unit['source_ref'], 'text': piece, 'policy': policy})
requirements = [fact for fact in facts if fact['kind'] == 'REQUIREMENT']
functions = [fact for fact in facts if fact['kind'] == 'FUNCTION']
missing_requirements = [identifier for profile in baseline['profiles'] for identifier, text in profile['requirements']
                        if not any(identifier in fact['quote'] and text in fact['quote'] for fact in requirements)]
missing_functions = [profile['id'] for profile in baseline['profiles']
                     if not any(profile['functions'] in fact['quote'] for fact in functions)]
checks = {'all_quotes_literal': all(fact['quote'] and fact['quote'] in source for fact in facts),
          'all_110_complete_requirement_texts': not missing_requirements,
          'all_ten_complete_function_paragraphs': not missing_functions,
          'every_required_source_unit_with_context_policy_and_atomic_name': not missing_units}
record = {'status': 'PASSED' if all(checks.values()) else 'FAILED', 'at_utc': datetime.now(timezone.utc).isoformat(),
          'scope': 'Actual expanded native proposal before adoption; no handoff, model or simulation claim.',
          'image_id': runtime['image_id'], 'application_source_sha256': runtime['source_sha256'],
          'original_file_sha256': baseline['source_sha256'], 'original_file_chars': len(source),
          'checks': checks, 'required_units': sum(bool(unit['required']) for unit in obligations['units']),
          'complete_requirement_count': baseline['requirement_count'] - len(missing_requirements),
          'actual_fact_count': len(facts), 'missing_requirements': missing_requirements,
          'missing_function_profiles': missing_functions, 'missing_source_units': missing_units}
(OUT / 'native-proposal-completeness.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(record, ensure_ascii=True))
raise SystemExit(0 if record['status'] == 'PASSED' else 1)
