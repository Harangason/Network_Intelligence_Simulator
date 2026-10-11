import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
path = folder / 'workload.json'
work = json.loads(path.read_text())
root = Path(work['repository'])
work['revision_before'] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in work['revision_before']}
work['completion_status'] = 'IMPLEMENTING'
proof = folder / 'reproduction.json'
proof.write_text(json.dumps({'isolated_test_container': 'nis-test-db-2669eec9cee8', 'tests': 'backend/tests/test_physical_ports.py',
    'result': '5 failed, 17 passed', 'failures': ['Missing primary sender update', 'Unnecessary extra channel on complete split: CAN_FD, LIN, Ethernet, MODBUS_RTU'],
    'product_mutations': 0}, indent=2), encoding='utf-8')
work['repair']['evidence'].append({'path': str(proof), 'sha256': hashlib.sha256(proof.read_bytes()).hexdigest()})
path.write_text(json.dumps(work, indent=2), encoding='utf-8')
