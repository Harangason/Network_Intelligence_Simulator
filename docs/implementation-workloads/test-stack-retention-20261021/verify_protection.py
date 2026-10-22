"""Verify the actual production and recorded rollback without changing them."""
import importlib.util
import json
from pathlib import Path
import sys
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_cleanup as audit

plan = json.loads((audit.OUT / 'cleanup-plan.json').read_text())
spec = importlib.util.spec_from_file_location('protection_storage', audit.ROOT / 'scripts/release_storage.py')
storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage)
rollback = next(row for row in plan['protected_images'] if row['id'] == plan['rollback'])
passes = [audit.ref(Path(row['path'])) for row in rollback['receipts']
          if storage.complete_pass(json.loads(Path(row['path']).read_text(encoding='utf-8-sig')))]
assert passes, 'The documented rollback needs a complete existing PASS'
images = json.loads(audit.call('image', 'inspect', *[r['id'] for r in plan['protected_images']]))
actual = {row['Id']: row for row in images}
assert all(actual[row['id']]['RepoTags'] == row['tags'] for row in plan['protected_images'])
cs = audit.containers()
production = next(row for row in cs if row['name'] == 'NetworkIS')
assert production['id'] == plan['production']['id'] and production['image'] == plan['production']['image']
assert production['health'] == 'healthy'
initial = json.loads((audit.OUT / 'inventory-before.json').read_text())
product_db = next(row for row in cs if row['name'] == 'NetworkIS-db')
original_db = next(row for row in initial['containers'] if row['name'] == 'NetworkIS-db')
assert (product_db['id'], product_db['image'], product_db['mounts']) == (original_db['id'], original_db['image'], original_db['mounts'])
health = {}
for route in ('/api/ready', '/api/build-info'):
    with urlopen('http://127.0.0.1:13500' + route, timeout=10) as response:
        assert response.status == 200
        health[route] = json.load(response)
result = {'status': 'PASSED', 'production_container_id': production['id'],
          'production_image': production['image'], 'rollback_image': rollback['id'],
          'rollback_complete_pass_receipts': passes, 'protected_images_and_tags_preserved': len(images),
          'product_database_container_and_storage_unchanged': True, 'http_health': health}
audit.write('protected-identity-and-health.json', result)
print(json.dumps({k: v for k, v in result.items() if k not in {'http_health', 'rollback_complete_pass_receipts'}}))
