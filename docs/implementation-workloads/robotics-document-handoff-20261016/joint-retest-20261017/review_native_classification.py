"""Independent source-role expectations for the actual rendered native facts."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
OUT = Path(__file__).parent.resolve()
baseline = json.loads((OUT.parents[1] / 'industrial-robotics-wizard-20261016/source-baseline.json').read_text(encoding='utf-8'))
data = Path(baseline['file']).read_bytes()
assert hashlib.sha256(data).hexdigest() == baseline['source_sha256']
source = data.decode('utf-8')
facts = json.loads((OUT / 'native-proposal-facts.json').read_text(encoding='utf-8'))
technologies = json.loads((OUT / 'native-proposal-technologies.json').read_text(encoding='utf-8'))
logical_names = {'Fleet Manager', 'Map', 'Traffic Service', 'Order Interface', 'MES', 'WMS-Anbindung',
                 'Rezept- und Batchsystem', 'Historian', 'Alarmmanagement', 'Materialfluss',
                 'Qualitätsmanagement', 'Werkerassistenz', 'Traceability', 'Energieplattform',
                 'Datenbank', 'Lagerverwaltung', 'Safety Zones', 'ML-/Regelalgorithmen'}
roles = {
    'ACTUATOR': {'Gelenkaktuatoren', 'Endeffektor', 'Greifarm', 'Aktoren'},
    'SENSOR': {'Encoder', 'Kraft-/Momentensensorik', 'Scanner', 'LiDAR', 'Kameras', 'IMU', 'Messtaster', 'Waagen'},
    'CONTROLLER': {'Sicherheitssteuerung', 'Motion Controller', 'PLC', 'Safety PLC', 'HMI', 'Echtzeitcontroller',
                   'BMS', 'CNC', 'Materialflussrechner', 'DCS', 'unabhängiges SIS', 'Operator HMI', 'Edge-Rechner', 'Review-HMI'},
    'OTHER': {'Teach Pendant', 'Ein oder mehrere Industrieroboter', 'Schutzzaun', 'Werkzeugtechnik', 'Vision', 'Fördertechnik',
              'Mobile Basis', 'Ultraschall', 'Funk', 'AMRs', 'AGVs', 'Charging', 'Achsantriebe', 'Spindel', 'Werkzeugmagazin',
              'Kühlung', 'Schmierung', 'Schutzraum', 'Mehrere Maschinenmodule', 'Servoachsen', 'Regalbediengeräte', 'Shuttles',
              'Brandschutzkopplung', 'Feldinstrumente', 'Engineering Station', 'PLC-/Robotikzellen', 'Andon', 'Optik',
              'Beleuchtung', 'Trigger', 'Reject-Mechanik'},
}
expected_role = {name: role for role, names in roles.items() for name in names}
findings = []
for fact in facts:
    if fact['kind'] in {'CATEGORY', 'INSTANCE'}:
        expected = 'CONTROLLER' if fact['name'] == 'Hauptrechner' else expected_role.get(fact['name'])
        if expected is None or fact['role'] != expected:
            findings.append({'finding': 'UNEXPECTED_HARDWARE_ROLE_OR_SUBJECT', 'expected_role': expected, 'fact': fact})
        if fact['name'] in logical_names or 'Die Sicherheits- und Betriebsargumentation' in fact['quote'] or re.search(r'\bTC[-_]', fact['quote']):
            findings.append({'finding': 'LOGICAL_ASSURANCE_OR_TEST_AS_HARDWARE', 'fact': fact})
    elif fact['role'] != 'OTHER' or fact['quantity'] is not None:
        findings.append({'finding': 'LOGICAL_FACT_HAS_PHYSICAL_ROLE_OR_QUANTITY', 'fact': fact})
    if fact['quote'] not in source:
        findings.append({'finding': 'NONLITERAL_OR_WRAPPER_CLAIM', 'fact': fact})
for name in logical_names:
    matched = [fact for fact in facts if fact['name'] == name]
    if not matched or any(fact['kind'] != 'FUNCTION' for fact in matched):
        findings.append({'finding': 'LOGICAL_SERVICE_MISSING_OR_WRONG_KIND', 'name': name})
counts = Counter(fact['kind'] for fact in facts)
for kind, expected in [('CATEGORY', 68), ('FUNCTION', 97), ('INSTANCE', 1)]:
    if counts[kind] != expected:
        findings.append({'finding': 'WRONG_DISTINCT_SOURCE_SUBJECT_COUNT', 'kind': kind, 'expected': expected, 'actual': counts[kind]})
assurance = re.findall(r'^Die Sicherheits- und Betriebsargumentation[^\r\n]+', source, re.M)
assert len(assurance) == 10
for quote in assurance:
    if not any(fact['kind'] == 'REQUIREMENT' and quote in fact['quote'] for fact in facts):
        findings.append({'finding': 'MISSING_COMPLETE_ASSURANCE_REQUIREMENT', 'quote': quote})
for technology in technologies:
    if technology['quote'] not in source or re.search(r'\bTC[-_]', technology['quote']):
        findings.append({'finding': 'TEST_ONLY_OR_NONLITERAL_TECHNOLOGY_CITATION', 'technology': technology})
wifi = [item for item in technologies if item['label'].split('·')[0].strip() == 'wifi']
if not wifi or not all('WLAN' in item['quote'] and 'TC-' not in item['quote'] for item in wifi):
    findings.append({'finding': 'WIFI_WITHOUT_ACTUAL_INTERFACE_EVIDENCE'})
record = {'status': 'FAILED' if findings else 'PASSED',
          'scope': 'Independent role/subject expectations transcribed from all architecture clauses and explicit logical services; actual rendered native facts. Full requirement/function-source coverage and exact handoff are checked separately.',
          'source_sha256': baseline['source_sha256'], 'actual_fact_counts': dict(counts), 'assurance_paragraphs': len(assurance),
          'findings': findings, 'image_id': json.loads((OUT / 'native-runtime-preparation.json').read_text(encoding='utf-8'))['image_id']}
(OUT / 'native-classification-review.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(record, ensure_ascii=True))
raise SystemExit(bool(findings))
