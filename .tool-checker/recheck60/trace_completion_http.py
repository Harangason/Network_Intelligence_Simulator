"""Bounded, isolated HTTP fixtures for S31/S34/S35; never simulation evidence."""
import json
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
receipt = json.loads((ROOT / 'backend/test-output/industry60-completion/0b317d9b014d/receipt.json').read_text())
assert receipt['status'] == 'PREPARED' and receipt['containers']['app'].startswith('nis-e2e-app-')
base = receipt['base_url']
assert base == 'http://127.0.0.1:60295'
project = 'nis-e2e-industry60-trace-completion'
folder = ROOT / '.tool-checker/evidence/industry60-completion/trace'
folder.mkdir(parents=True, exist_ok=True)

def import_bytes(label, filename, content):
    request = urllib.request.Request(base + '/api/trace-import?filename=' + filename,
        data=content, headers={'X-Project-ID': project, 'Content-Type': 'application/octet-stream'})
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            status, body = response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        status, body = error.code, error.read().decode()
    evidence = {'project': project, 'image': receipt['image_id'], 'status': status, 'response': json.loads(body)}
    (folder / (label + '.json')).write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf8')
    return evidence

assert import_bytes('unknown-format', 'unknown.bin', b'not a trace')['status'] == 422
assert import_bytes('invalid-metadata', 'invalid.jsonl', b'{"time_s":0,"technology":{}}')['status'] == 422
missing = import_bytes('missing-timebase', 'unknown-clock.jsonl', b'{"time_s":1,"message":"unknown clock"}')
assert missing['status'] == 200
assert missing['response']['sync_status'] == 'unknown'

events = []
for index, time in enumerate((12.4, 12.5, 12.6)):
    events.append({'event_id': 'five-channel-' + str(index), 'time_s': time, 'time_basis': 'relative',
        'sequence': index, 'source': 'SensorController', 'destination': 'MotorController',
        'network_id': 'trace-fixture-can', 'technology': 'CAN_FD', 'message_id': 'MotorStatus',
        'route_id': 'fixture-route', 'status': 'FAULT' if index == 1 else 'OK',
        'faults': ['SYNTHETIC_MARKER'] if index == 1 else [],
        'signals': {'Temperature': {'value': 342 + index, 'physical_value': 34.2 + index, 'unit': 'degC', 'quality': 'VALID'},
                    'MotorRPM': {'value': 1200 + index, 'unit': 'rpm', 'quality': 'VALID'},
                    'MotorCurrent': {'value': 2.5 + index, 'unit': 'A', 'quality': 'VALID'},
                    'OperatingState': {'value': 'RUN' if index else 'IDLE', 'quality': 'VALID'},
                    'HealthState': {'value': 'WARNING' if index == 1 else 'OK', 'quality': 'VALID'}}})
content = '\n'.join(json.dumps(event) for event in events).encode()
(folder / 'five-channel-source.jsonl').write_bytes(content)
result = import_bytes('five-channel-import', 'five-channel.jsonl', content)
assert result['status'] == 200 and result['response']['total_events'] == 3
print(json.dumps({'project': project, 'session': result['response']['session_id'], 'base': base}), flush=True)
