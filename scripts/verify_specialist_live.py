"""Actual local inference, synthetic evidence, no project/database writes."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.engineering.agent_tools import specialist

audit = []
specialist.record = lambda *args: audit.append(args)
specialist.current_project_id = lambda: 'isolated-specialist-verification'
result = specialist.review_candidates('Vergleiche zwei Kommunikationsreparaturen anhand ihrer belegten Funktionspartner.', [
    {'id': 'preserve-partners', 'before': 'Funktion A sendet Zustand an Funktion B',
     'after': 'Funktion A auf ECU 1 sendet denselben Zustand an Funktion B auf ECU 2',
     'technical_validation': 'passed', 'hardware_limits': 'confirmed', 'scope_change': False},
    {'id': 'wrong-recipient', 'before': 'Funktion A sendet Zustand an Funktion B',
     'after': 'Funktion A sendet stattdessen alle lokalen Sensorsignale an Funktion C',
     'technical_validation': 'failed: LOCAL_IO_RECIPIENT_MISMATCH', 'hardware_limits': 'unknown', 'scope_change': True},
])
assert result['status'] == 'REVIEWED'
decisions = {item['id']: item for item in result['decisions']}
assert not decisions['wrong-recipient']['recommended'], result
assert decisions['preserve-partners']['recommended'], result
Path('backend/runtime/specialist-live.json').write_text(json.dumps({'passed': True, 'review': result}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'passed': True, 'model': result['model'], 'decisions': result['decisions']}, ensure_ascii=False))
