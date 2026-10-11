"""Append the actual consumer follow-up; preserve the original source review."""
from pathlib import Path
import hashlib
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'docs/implementation-workloads/technology-full-parameter-audit-20261001'
sys.path.insert(0, str(ROOT))
os.environ['NIS_DISABLE_GENERATED_TECHNOLOGIES'] = '1'
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY

def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

first = ROOT / 'work/browser-repair-focused.txt'
second = ROOT / 'work/browser-repair-corrected.txt'
assert '10 passed' in first.read_text(encoding='utf-8-sig')
assert '2 passed' in second.read_text(encoding='utf-8-sig')
assert '107 passed' in (ROOT / 'work/browser-repair-backend-check.txt').read_text(encoding='utf-8-sig')
profile = DEFAULT_TECHNOLOGY_REGISTRY.profile('i2c')
local_mode = next(row for row in profile['local_timing_schema'] if row['key'] == 'i2c_mode')
assert local_mode['default'] == 'STANDARD' and local_mode['default_status'] == 'PROPOSED'
path = FOLDER / 'individual/i2c.json'
record = json.loads(path.read_text(encoding='utf-8'))
field = next(row for row in record['parameter_reviews'] if row['key'] == 'local_timing_evidence.i2c_mode')
field['consumer_after'] = local_mode
field['consumer_followup'] = {
    'scope': 'Actual device editor now displays sourced STANDARD proposal, preserves unchanged confirmed FAST facts, and invalidates confirmation on change. STANDARD with 400k is rejected; explicit FAST with 400k is persisted. Device addresses, controller identity and timing bounds remain unconfirmed without installation evidence.',
    'source_revision': local_mode['source_revision'],
    'evidence': [ref(ROOT / 'work/browser-repair-backend-check.txt'), ref(second)],
    'production_delivered': False,
}
path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
path = FOLDER / 'consumer-findings.md'
text = path.read_text(encoding='utf-8')
marker = '\nDie Einzelprüfungen und die Quellenkorrekturen sind dokumentiert.'
assert marker in text
text = text.replace(marker,
    '\n- Die gezielte echte Browsernachprüfung bestand zehn Fälle, einschließlich aller 125 Formularprofile, I²C-/Modbus-Nachweisblock, Katalog-Ausfall/Wiederholung, großer neunphasiger Simulation mit Neustart und Änderungsworkflow. Zwei veraltete positive Prüfvorgaben wurden anschließend gegen ihre ursprüngliche native Semantik berichtigt und bestanden: STANDARD bei 400 kbit/s wird ausdrücklich abgewiesen, FAST bei 400 kbit/s gespeichert; CAN-FD ohne Controllerkonfiguration erhält keine erfundene Phasenrate. Die Gerätebestätigung bleibt beim unveränderten Speichern erhalten und wird nach einer Änderung zurückgenommen. Belege: work/browser-repair-focused.txt, work/browser-repair-corrected.txt und die dort verknüpften tatsächlichen Browser-Traces. Dies ist noch kein vollständiger Release-PASS.\n' + marker)
path.write_text(text, encoding='utf-8')
print(json.dumps({'scope': 'Focused repairs verified; complete release gate still pending', 'browser_passed': 12, 'backend_passed': 107}))
