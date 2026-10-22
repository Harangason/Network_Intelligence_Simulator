"""Review captured native DOM facts; never generate or modify NIS inputs."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
source_path = Path('C:/Users/marti/PycharmProjects/Benchmark_Modelle/Fahrzeug komplett.txt')
raw = source_path.read_bytes()
source_hash = hashlib.sha256(raw).hexdigest()
assert source_hash == '86865975c689643d9b07ea73e21d68fa6f4a3a8770402ffb537dba2d7ecdf4d7'
source = raw.decode('utf-8')
amendment = (OUT.parent / 'user-amendment.txt').read_text(encoding='utf-8').strip()
facts = json.loads((OUT / 'native-proposal-facts.json').read_text(encoding='utf-8'))
runtime = json.loads((OUT / 'native-runtime-preparation.json').read_text(encoding='utf-8'))
quotes = '\n'.join(item['quote'] for item in facts)
hyphens = str.maketrans({ch: '-' for ch in '\u2010\u2011\u2012\u2013\u2014\u2212'})
ids = lambda text: set(re.findall(r'\bREQ-[A-Z]+-\d+\b', text.translate(hyphens)))
original_ids = ids(source)
requirement_lines = [line.strip() for line in source.splitlines()
                     if re.match(r'^REQ-[A-Z]+-\d+:', line.strip().translate(hyphens))]
assert len(original_ids) == len(requirement_lines) == 168
findings = []
obligations = json.loads((OUT / 'source-component-units.json').read_text(encoding='utf-8'))
assert obligations['source_sha256'] == source_hash
rows = {row['source_ref']: row['text'].strip() for row in obligations['rows']}
missing_units = []
for unit in obligations['units']:
    if not unit['required']:
        continue
    policy = unit.get('policy')
    for piece in [rows[ref] for ref in unit.get('source_rows', [])] or [unit['text']]:
        if not any(piece in item['quote']
                   and (not unit.get('source_quote') or item['name'] == unit['text'][:120])
                   and ' / '.join(unit.get('source_context', [])) in item['context']
                   and (not policy or all(item[key] == policy[key] for key in ('kind', 'role', 'quantity')))
                   for item in facts):
            missing_units.append({'source_ref': unit['source_ref'], 'text': piece, 'policy': policy})
if missing_units:
    findings.append({'finding': 'REQUIRED_CANONICAL_SOURCE_UNIT_NOT_PRESERVED', 'units': missing_units})
baseline = json.loads((OUT.parent / 'vehicle-production-native-proposal-facts.json').read_text(encoding='utf-8'))
for previous in baseline:
    # Native requirement grouping can vary. Full literal requirement lines and
    # canonical source obligations below remain the invariant, not chunk titles.
    if previous['kind'] == 'REQUIREMENT':
        continue
    expected_kind = 'FUNCTION' if 'mit externen Systemen kommunizieren' in previous['quote'] else previous['kind']
    if not any(item['quote'] == previous['quote'] and item['context'] == previous['context']
               and item['name'] == previous['name'] and item['kind'] == expected_kind for item in facts):
        findings.append({'finding': 'PREVIOUS_COMPLETE_SOURCE_SUBJECT_NOT_PRESERVED', 'expected_kind': expected_kind,
                         'name': previous['name'], 'quote': previous['quote'], 'context': previous['context']})
missing_lines = [line for line in requirement_lines if line not in quotes]
missing_ids = sorted(original_ids - ids(quotes))
if missing_lines or missing_ids:
    findings.append({'finding': 'INCOMPLETE_REQUIREMENT_SOURCE', 'lines': missing_lines, 'ids': missing_ids})
controllers = {f'{name} Domain Controller ({alias})' for name, alias in
               [('Powertrain', 'PDC'), ('Chassis', 'CDC'), ('ADAS', 'ADC'), ('Body', 'BDC'), ('Infotainment', 'IDC')]}
instances = [item for item in facts if item['kind'] == 'INSTANCE']
if {item['name'] for item in instances} != controllers or len(instances) != 5:
    findings.append({'finding': 'WRONG_PHYSICAL_CONTROLLER_INVENTORY', 'actual': instances})
for item in facts:
    if item['quote'] not in source and item['quote'] not in amendment:
        findings.append({'finding': 'NONLITERAL_QUOTE', 'fact': item})
    if item['kind'] == 'INSTANCE':
        if item['quantity'] != 1 or item['role'] != 'CONTROLLER':
            findings.append({'finding': 'WRONG_EXPLICIT_INSTANCE', 'fact': item})
    elif item['quantity'] is not None:
        findings.append({'finding': 'INVENTED_QUANTITY', 'fact': item})
    if item['kind'] in {'FUNCTION', 'REQUIREMENT'} and item['role'] != 'OTHER':
        findings.append({'finding': 'LOGICAL_FACT_HAS_PHYSICAL_ROLE', 'fact': item})
communication = [item for item in facts if 'mit externen Systemen kommunizieren' in item['quote']]
if len(communication) != 1 or communication[0]['kind'] != 'FUNCTION' or communication[0]['role'] != 'OTHER':
    findings.append({'finding': 'COMMUNICATION_ACTION_MISSING_OR_HARDWARE', 'actual': communication})
adc_names = {'Sensorfusion (Radar, Kamera, Lidar, IMU, Ultraschall)',
             'Perception (Objekte, Spuren, Freiraum)', 'Planning (Trajektorien, Manöver)',
             'Vehicle Control (Längs-/Querführung)'}
adc = [item for item in facts if item['name'] in adc_names and '2.3 ADAS Domain Controller (ADC)' in item['context']]
if len(adc) != 4 or {item['name'] for item in adc} != adc_names or any(item['kind'] != 'FUNCTION' for item in adc):
    findings.append({'finding': 'MISSING_OR_COLLAPSED_ADC_FUNCTIONS', 'actual': adc})
for group, role in [('Sensorik (Radar, Kamera, Lidar, Ultraschall, IMU, Raddrehzahl)', 'SENSOR'),
                    ('Aktorik (Bremsaktuator, Lenkaktuator, Antriebsaktuator)', 'ACTUATOR')]:
    selected = [item for item in facts if item['name'] == group]
    if len(selected) != 1 or selected[0]['kind'] != 'CATEGORY' or selected[0]['role'] != role:
        findings.append({'finding': 'DEVICE_GROUP_MISSING_OR_WRONG_ROLE', 'name': group, 'actual': selected})
counts = dict(Counter(item['kind'] for item in facts))
record = {'status': 'FAILED' if findings else 'PASSED', 'at_utc': datetime.now(timezone.utc).isoformat(),
          'scope': 'Actual original-file native Qwen rendered proposal before adoption; not model/simulation acceptance.',
          'project_id': '20261016122109077-dc3a1aeb', 'base_url': runtime['base_url'],
          'image_id': runtime['image_id'], 'source_sha256': runtime['source_sha256'],
          'original_source_sha256': source_hash, 'fact_counts': counts,
          'original_requirement_ids': len(original_ids), 'original_requirement_lines': len(requirement_lines),
          'missing_requirement_ids': missing_ids, 'missing_complete_requirement_lines': missing_lines,
          'required_source_units': sum(bool(unit['required']) for unit in obligations['units']),
          'missing_source_units': missing_units,
          'communication_action': communication, 'adc_functions': adc, 'findings': findings,
          'canonical_model_changes': False,
          'comparison_note': 'REQ identity normalizes Unicode hyphens only; all full source requirement lines are separately compared literally.'}
(OUT / 'native-semantic-review.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'status': record['status'], 'counts': counts, 'complete_requirements': len(requirement_lines)-len(missing_lines), 'findings': findings}, ensure_ascii=True))
raise SystemExit(bool(findings))
