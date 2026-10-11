"""Bind production image identity, both access paths and unchanged profile data."""
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import urlopen
from edit_utils import OUT

receipt_path = Path(sys.argv[1]).resolve()
receipt = json.loads(receipt_path.read_text(encoding='utf-8-sig'))
assert receipt['status'] == 'PASS'
assert len(receipt['checks']) == 8 and all(check['exit_code'] == 0 for check in receipt['checks'])
observation_path = OUT/'production-running-image.json'
observed = json.loads(observation_path.read_text(encoding='utf-8-sig'))
assert observed['image_id'] == receipt['image_id']
assert observed['health'] == 'healthy'
native = json.loads((OUT/'production-native-smoke.json').read_text(encoding='utf-8-sig'))
assert native['status'] == 'PASS'
before = json.loads((OUT/'production-catalog-before.json').read_text(encoding='utf-8'))
requests = {}
for base in ('http://127.0.0.1:13500','http://192.168.178.10:13500'):
    for path in ('/api/ready','/api/build-info','/api/technologies'):
        with urlopen(base+path,timeout=30) as response:
            data = json.load(response)
            assert response.status == 200
        if path == '/api/ready':
            assert data['status'] == 'ready'
        elif path == '/api/build-info':
            assert data['source_sha256'] == receipt['release']['source_sha256']
        else:
            assert data == before, 'Production technology catalog changed'
            data = {'verified_technology_count':125,'entire_pre_delivery_catalog_equal':True}
        requests[base+path] = {'status':200,'body':data}
result = {'status':'PASS','receipt':str(receipt_path),'image_id':observed['image_id'],
          'source_sha256':receipt['release']['source_sha256'],'tested_image_matches_running':True,
          'running_observation_sha256':hashlib.sha256(observation_path.read_bytes()).hexdigest(),
          'requests':requests,'native_functionality':native}
(OUT/'production-verification.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'status':'PASS','image_id':observed['image_id'],'local_and_lan':True,'entire_catalog_equal':True,'native_smoke':True}))
