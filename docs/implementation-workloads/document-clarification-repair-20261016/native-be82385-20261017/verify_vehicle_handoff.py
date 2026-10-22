"""Verify actual normal Wizard adoption and NIS-owned source-host review."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

OUT = Path(__file__).resolve().parent
read = lambda name: json.loads((OUT / name).read_text(encoding='utf-8'))
before = read('native-proposal-facts.json')
after = read('native-adopted-facts.json')
final = read('native-final-adopted-facts.json')
review = read('native-semantic-review.json')
equipment = read('native-equipment-after-function-review.json')
audit = read('native-tool-audit.json')
runtime = read('native-runtime-preparation.json')
description_before = (OUT / 'native-description-before.txt').read_text(encoding='utf-8')
description_after = (OUT / 'native-description-after.txt').read_text(encoding='utf-8')
amendment = (OUT.parent / 'user-amendment.txt').read_text(encoding='utf-8').strip()
ui = (OUT / 'native-adopted-ui.txt').read_text(encoding='utf-8')
hosts = {row['label'].removeprefix('Controller für Funktion '): row['selected'] for row in equipment['function_hosts']}
expected_hosts = {}
for fact in before:
    if fact['kind'] != 'FUNCTION':
        continue
    for domain in ['Powertrain', 'Chassis', 'ADAS', 'Body', 'Infotainment']:
        if f'{domain} Domain Controller (' in fact['context']:
            expected_hosts[fact['name']] = f'{domain} Domain'
questions = {row['label']: row['value'] for row in equipment['quantity_questions']}
checks = {
    'independent_source_role_review': review['status'] == 'PASSED',
    'all_80_facts_adopted_unchanged': len(before) == 80 and before == after == final,
    'all_168_complete_requirement_lines_preserved': review['original_requirement_lines'] == 168 and not review['missing_complete_requirement_lines'],
    'all_required_source_units_preserved': review['required_source_units'] == 73 and not review['missing_source_units'],
    'description_and_minimum_user_amendment_unchanged': description_before == description_after == amendment,
    'complete_original_file_stays_attached': 'Fahrzeug komplett.txt' in ui and 'vollständig gelesen (19.088 Zeichen)' in ui,
    'all_22_literal_controller_duties_assigned_by_NIS': len(expected_hosts) == 22 and all(hosts.get(name) == owner for name, owner in expected_hosts.items()),
    'all_4_adc_functions_on_ADC': sum(owner == 'ADAS Domain' for owner in expected_hosts.values()) == 4,
    'unproven_general_function_hosts_stay_open': all(value == 'Zuordnung offen' for name, value in hosts.items() if name not in expected_hosts),
    'all_9_named_sensor_actor_types_have_targeted_questions': all('Anzahl ' + name in questions for name in ['Radar','Kamera','Lidar','Ultraschall','IMU','Raddrehzahl','Bremsaktuator','Lenkaktuator','Antriebsaktuator']),
    'no_unanswered_quantity_invented': len(questions) == 13 and all(value == '' for value in questions.values()),
    'only_source_bound_instances_counted': equipment['inventory_counts'] == {'Gateways: verbindliche Anzahl':0,'Controller: verbindliche Anzahl':5,'Sensoren: verbindliche Anzahl':0,'Aktoren: verbindliche Anzahl':0},
    'unproven_controller_connections_stay_open': bool(equipment['controller_connections']) and all(row['value'] == '' for row in equipment['controller_connections']),
    'minimum_not_complete_inventory_option_is_present': 'Angaben sind ein Mindestumfang' in equipment['text'],
    'model_apply_remains_blocked_for_open_decisions': equipment['apply_disabled'] is True,
    'actual_registered_native_tool_audit': audit['status'] == 'PASSED' and len(audit['interpretation_events']) == 1,
    'no_canonical_model_or_simulation_created': all(value == 'EMPTY' for value in audit['workflow_statuses'].values()),
    'audit_same_exact_candidate': audit['image_id'] == runtime['image_id'] and audit['source_sha256'] == runtime['source_sha256'],
}
record = {'status': 'PASSED' if all(checks.values()) else 'FAILED', 'at_utc':datetime.now(timezone.utc).isoformat(),
          'scope':'Actual complete original vehicle native analysis and normal structured Wizard handoff including NIS-owned literal function-host adoption. No canonical model generation, routing or simulation acceptance claimed.',
          'project_id':'20261016122109077-dc3a1aeb', 'base_url':runtime['base_url'],
          'image_id':runtime['image_id'],'source_sha256':runtime['source_sha256'],
          'checks':checks,'automatic_source_hosts':expected_hosts,
          'user_model_corrections':False,'manual_host_selections':False,
          'normal_actions':['Original file chooser','Native Qwen button','Geprüfte Dokumentangaben übernehmen','Funktionszuordnungen übernehmen'],
          'evidence':{name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in ['native-proposal-facts.json','native-adopted-facts.json','native-final-adopted-facts.json','native-semantic-review.json','native-tool-audit.json','native-equipment-after-function-review.json']}}
(OUT/'native-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':record['status'],'checks':checks},ensure_ascii=True))
raise SystemExit(record['status'] != 'PASSED')
