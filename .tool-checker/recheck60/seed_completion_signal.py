import json
from pathlib import Path
from uuid import uuid4
import industry60_fixtures as fixtures

ROOT = Path(__file__).resolve().parents[2]
receipt = json.loads((ROOT / 'backend/test-output/industry60-completion/d8a5a6840084/receipt.json').read_text())
assert receipt['status'] == 'PREPARED' and receipt['base_url'] == 'http://127.0.0.1:56335'
fixtures.BASE = receipt['base_url']
api = fixtures.api
p = 'nis-e2e-industry60-s27-' + uuid4().hex[:8]
h = api(p, 'hardware-nodes', {'name': 'MotorController', 'device_type': 'ECU'})
f = api(p, 'functions', {'name': 'SpeedMonitoring', 'hardware_node_id': h['id']})
i = api(p, 'interfaces', {'name': 'SpeedOutput', 'function_id': f['id'], 'interface_type': 'CAN_FD'})
m = api(p, 'messages', {'name': 'SpeedStatus', 'interface_id': i['id'], 'message_id_hex': '0x100', 'cycle_ms': 10, 'dlc': 1, 'direction': 'tx'})
s = api(p, 'signals', {'name': 'MotorRPM', 'message_id': m['id'], 'start_bit': 0, 'length_bits': 4,
    'byte_order': 'little_endian', 'data_type': 'unsigned', 'factor': 50, 'offset_value': 0,
    'min_value': 0, 'max_value': 5000, 'unit': 'rpm', 'semantic': {'semantic_type': 'PHYSICAL_SCALAR'},
    'configuration': {'resolution': 50}})
folder = ROOT / '.tool-checker/evidence/industry60-completion/S27'
folder.mkdir(parents=True, exist_ok=True)
(folder / 'fixture.json').write_text(json.dumps({'project': p, 'image': receipt['image_id'], 'hardware': h,
    'function': f, 'interface': i, 'message': m, 'signal': s,
    'origin': 'Explicit deliberately invalid 4-bit source fixture, no channel/hardware capacity assumed'}, indent=2), encoding='utf8')
print(json.dumps({'project': p, 'signal': s['id']}), flush=True)
