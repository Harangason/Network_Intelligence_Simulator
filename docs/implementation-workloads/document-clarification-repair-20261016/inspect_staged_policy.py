"""Read-only semantic diagnostic of the prepared patch, not an E2E receipt."""
from pathlib import Path
import importlib.util
import json
import sys

WORK = Path(__file__).parent
ROOT = WORK.parents[2]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('staged_project_intake', WORK / 'staged/backend/nis/agent/orchestration/project_intake.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY

sources = [
    'Sensor- und Aktorfehler erkennen und behandeln.',
    'Das System verarbeitet kontinuierlich Sensordaten und steuert Aktuatoren.',
    '2. Domain-Controller-Design\nPowertrain Domain Controller (PDC)',
    'Chassis Controller (CDC)\nSchnittstellen:\nCDC (Lenk-/Bremsanforderungen)\nDirekte Sensorlinks (GMSL, FPD-Link, GigE)\nEthernet möglich',
    '5. Anforderungen\nDas System muss\n\nEnergieversorgung für alle Subsysteme sicherstellen.\nSystemzustände überwachen und protokollieren.\n6. Hardware\nRaumcontroller',
]
output = []
for source in sources:
    rows = module.document_source_references(source)
    output.append({'source': source, 'units': module.document_component_sources(rows),
                   'unknown': module.document_declared_unknown_transports(rows, DEFAULT_TECHNOLOGY_REGISTRY.profiles())})
vehicle = (WORK.parent / 'vehicle-complete-e2e-20261016/source-original.txt').read_text(encoding='utf-8')
units = module.document_component_sources(module.document_source_references(vehicle))
output.append({'original_vehicle_units': len(units),
               'required_units': sum(bool(unit['required']) for unit in units),
               'unknown': module.document_declared_unknown_transports(module.document_source_references(vehicle), DEFAULT_TECHNOLOGY_REGISTRY.profiles()),
               'categories': [unit['text'] for unit in units if unit['policy'] and unit['policy']['kind'] == 'CATEGORY']})
(WORK / 'staged-policy-diagnostic.json').write_text(json.dumps({'staged_only': True, 'results': output}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'staged_only': True, 'results': output}, ensure_ascii=True))
