"""Read-only verification of the exact delivered structure migration image."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY

receipt_path = Path(sys.argv[1]).resolve()
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
assert receipt['status'] == 'PASS'

def normalize_capture_encoding(value):
    """Undo the proven PowerShell UTF-8 capture misdecoding; keep live data exact."""
    if isinstance(value, dict):
        return {key: normalize_capture_encoding(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_capture_encoding(item) for item in value]
    if isinstance(value, str):
        for encoding in ['latin1', 'cp1252']:
            try:
                return value.encode(encoding).decode('utf-8')
            except UnicodeError:
                pass
    return value

before_path = ROOT / 'docs/implementation-workloads/structure-completion-20261003/production-catalog-before.json'
before_catalog = normalize_capture_encoding(json.loads(before_path.read_text(encoding='utf-8')))
running_path = ROOT / 'docs/implementation-workloads/structure-completion-20261003/production-running-image.json'
running = json.loads(running_path.read_text(encoding='utf-8-sig'))
image = running['image']
assert image == receipt['image_id']
assert running['status'] == 'running' and running['health'] == 'healthy'
proof = {'receipt':str(receipt_path),'image_id':image,'tested_image_matches_running':True,
         'running_observation':{'path':str(running_path),'sha256':hashlib.sha256(running_path.read_bytes()).hexdigest()},'requests':{}}
for base in ['http://127.0.0.1:13500', 'http://192.168.178.10:13500']:
    for path in ['/api/ready', '/api/build-info', '/api/technologies']:
        with urlopen(base + path, timeout=30) as response:
            body = json.load(response)
            assert response.status == 200
        if path == '/api/ready': assert body['status'] == 'ready'
        if path == '/api/build-info': assert body['source_sha256'] == receipt['initial_source_sha256']
        if path == '/api/technologies':
            assert body == before_catalog, 'Delivered catalog differs from the previous production catalog'
            actual = {p['id']:p for domain in body['domains'] for p in domain['technologies']}
            expected = {p['id']:p for p in DEFAULT_TECHNOLOGY_REGISTRY.profiles()}
            assert set(actual) == set(expected)
            for key, profile in actual.items():
                for field in ['canonical_id','aliases','implementation_status','rate_model','max_payload_bytes','parameter_proposals','capacity_evidence']:
                    assert profile.get(field) == expected[key].get(field), (key,field)
            body = {'verified_technology_count':len(actual),'identity_rates_payload_capacity_equal':True,
                    'complete_previous_production_catalog_equal':True,
                    'before_capture_encoding_normalization':'lossless latin1/cp1252 to UTF-8 for misdecoded strings only',
                    'before_catalog_path':str(before_path),'before_catalog_sha256':hashlib.sha256(before_path.read_bytes()).hexdigest()}
        proof['requests'][base + path] = {'status':200,'body':body}
proof['status'] = 'PASSED'
out = ROOT / 'docs/implementation-workloads/structure-completion-20261003/production-verification.json'
out.write_text(json.dumps(proof,indent=2),encoding='utf-8')
print(json.dumps({'status':'PASSED','image_id':image,'technology_count':len(expected),'local_and_lan_verified':True}))
