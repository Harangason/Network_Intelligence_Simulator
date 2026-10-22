"""Compare real rendered proposal and adopted facts to the unchanged source."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import re

OUT = Path(__file__).parent
baseline = json.loads((OUT.parent / 'industrial-robotics-wizard-20261016/source-baseline.json').read_text(encoding='utf-8'))
source_bytes = Path(baseline['file']).read_bytes()
assert hashlib.sha256(source_bytes).hexdigest() == baseline['source_sha256']
source = source_bytes.decode('utf-8')
before = json.loads((OUT / 'native-proposal-facts.json').read_text(encoding='utf-8'))
after = json.loads((OUT / 'native-adopted-facts.json').read_text(encoding='utf-8'))
equipment = json.loads((OUT / 'native-equipment-fields.json').read_text(encoding='utf-8'))
description_before = (OUT / 'native-description-before.txt').read_text(encoding='utf-8')
description_after = (OUT / 'native-description-after.txt').read_text(encoding='utf-8')
adopted_ui = (OUT / 'native-adopted-ui.txt').read_text(encoding='utf-8')
semantic_review = json.loads((OUT / 'native-classification-review.json').read_text(encoding='utf-8'))
assert before and after
requirements = [fact for fact in after if fact['kind'] == 'REQUIREMENT']
hardware = [fact for fact in after if fact['kind'] in ('CATEGORY', 'INSTANCE')]
functions = [fact for fact in after if fact['kind'] == 'FUNCTION']
expected_inventory = {key: sum(fact['quantity'] or 0 for fact in after if fact['kind'] == 'INSTANCE' and fact['role'] == role)
                      for key, role in {'ecus': 'CONTROLLER', 'gateways': 'GATEWAY', 'sensors': 'SENSOR', 'actuators': 'ACTUATOR'}.items()}
obligations = json.loads((OUT / 'source-component-units.json').read_text(encoding='utf-8'))
assert obligations['source_sha256'] == baseline['source_sha256']
rows = {row['source_ref']: row['text'].strip() for row in obligations['rows']}
missing_units = []
for unit in obligations['units']:
    if not unit['required']:
        continue
    policy = unit.get('policy')
    pieces = [rows[ref] for ref in unit.get('source_rows', [])] or [unit['text']]
    for piece in pieces:
        if not any(piece in fact['quote'] and ' / '.join(unit.get('source_context', [])) in fact['context']
                   and (not policy or all(fact[key] == policy[key] for key in ('kind', 'role', 'quantity')))
                   for fact in after):
            missing_units.append({'source_ref': unit['source_ref'], 'text': piece, 'policy': policy})
missing_requirements = [identifier for profile in baseline['profiles'] for identifier, text in profile['requirements']
                        if not any(identifier in fact['quote'] and text in fact['quote'] for fact in requirements)]
missing_functions = [profile['id'] for profile in baseline['profiles']
                     if not any(profile['functions'] in fact['quote'] for fact in functions)]
bad_hardware = [fact for fact in hardware if re.search(r'\bTC[-_]', fact['quote'])
                or fact['quote'].lstrip().startswith('|') or '4. Funktionsbeschreibung' in fact['context']]
checks = {
    'original_bytes_unchanged': hashlib.sha256(source_bytes).hexdigest() == baseline['source_sha256'],
    'independent_semantic_classification_review': semantic_review['status'] == 'PASSED',
    'all_quotes_literal': all(fact['quote'] and fact['quote'] in source for fact in before),
    'all_facts_adopted_unchanged': before == after,
    'description_not_replaced_by_summary': description_before == description_after,
    'complete_original_file_stays_attached': Path(baseline['file']).name in adopted_ui and 'vollständig gelesen (63.705 Zeichen)' in adopted_ui,
    'all_110_complete_requirements': not missing_requirements,
    'all_ten_function_descriptions': not missing_functions,
    'every_required_source_unit_adopted_with_context_and_known_role': not missing_units,
    'no_test_index_or_function_hardware': not bad_hardware,
    'no_safety_argumentation_hardware': not any(fact['quote'].startswith('Die Sicherheits- und Betriebsargumentation') for fact in hardware),
    'logical_facts_have_no_hardware_role_or_quantity': all(fact['role'] == 'OTHER' and fact['quantity'] is None
                                                        for fact in [*requirements, *functions]),
    'source_bound_sis_is_controller': any(re.search(r'\bSIS\b', fact['quote']) and fact['role'] == 'CONTROLLER' for fact in hardware),
    'unknown_category_quantities_remain_open': bool(equipment['quantity_questions']) and all(row['value'] == '' for row in equipment['quantity_questions']),
    'every_device_category_has_a_quantity_question': len(equipment['quantity_questions']) == sum(fact['kind'] == 'CATEGORY' for fact in after),
    'unproven_controller_connections_remain_open': all(row['value'] == '' for row in equipment['controller_connections']),
    'inventory_counts_only_source_bound_instances': equipment['inventory_counts'] == expected_inventory,
    'unspecified_function_owners_remain_questions': len(equipment['function_hosts']) == len(functions)
        and all(row['value'] == '' for row in equipment['function_hosts']),
    'model_apply_stays_blocked_for_missing_source_decisions': equipment['apply_disabled'] is True,
}
result = {'status': 'PASSED' if all(checks.values()) else 'FAILED', 'scope': 'Native complete original-file analysis and structured Wizard handoff; no robot model generation or nine-stage simulation claim',
          'source_sha256': baseline['source_sha256'], 'source_chars': len(source), 'checks': checks,
          'fact_counts': dict(Counter(fact['kind'] for fact in after)), 'requirement_ids': baseline['requirement_count'],
          'missing_requirements': missing_requirements, 'missing_function_profiles': missing_functions,
          'required_source_units': sum(bool(unit['required']) for unit in obligations['units']), 'missing_source_units': missing_units,
          'expected_inventory_counts': expected_inventory, 'rendered_inventory_counts': equipment['inventory_counts'],
          'function_host_question_count': len(equipment['function_hosts']),
          'bad_hardware': bad_hardware, 'quantity_question_count': len(equipment['quantity_questions'])}
(OUT / 'native-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=True, indent=2))
raise SystemExit(0 if result['status'] == 'PASSED' else 1)
