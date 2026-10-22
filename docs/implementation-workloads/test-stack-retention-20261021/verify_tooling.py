"""Read-only live probe of preparation reuse and retained-stack rejection."""
import importlib.util
import json
from pathlib import Path
import sys
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_cleanup as audit

spec = importlib.util.spec_from_file_location('cleanup_delivery', audit.ROOT / 'scripts/release-and-deploy.py')
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
before = audit.containers()
live = next(row for row in before if row['name'] == 'nis-e2e-app-6d6fe881f4bd')
inspected = json.loads(audit.call('inspect', live['id']))[0]
env = dict(value.split('=', 1) for value in inspected['Config']['Env'] if '=' in value)
paths = list(delivery.receipt_paths())
receipt_path = next(path for path in paths if path.parent.name == '6d6fe881f4bd')
receipt = json.loads(receipt_path.read_text())
params = dict(prepare=True, keep=False, ai_url=env['LOCAL_AI_BASE_URL'])
with delivery.gate_lock(audit.ROOT):
    selected = delivery.prepared_stack(audit.DOCKER, paths, receipt['initial_source_sha256'],
                                       receipt['initial_commit_id'], **params)
    assert selected[0] == receipt_path
    try:
        delivery.prepared_stack(audit.DOCKER, paths, '0' * 64, receipt['initial_commit_id'], **params)
    except RuntimeError as error:
        assert 'retained test stack' in str(error)
    else:
        raise AssertionError('Changed source must not create a second retained stack')
after = audit.containers()
assert before == after, 'Read-only probe changed the container inventory'
health = {}
for route in ('/api/ready', '/api/build-info'):
    with urlopen('http://127.0.0.1:13500' + route, timeout=10) as response:
        assert response.status == 200
        health[route] = json.load(response)
audit.write('live-tooling-verification.json', {
    'status': 'PASSED', 'scope': 'Read-only host-tool behavior and production HTTP health; no app release gate, build, restart, AI inference or product data mutation.',
    'exact_prepared_stack_reused': str(selected[0]), 'different_source_blocked_before_build': True,
    'container_inventory_unchanged': True, 'production_health': health,
    'production_image': next(row['image'] for row in after if row['name'] == 'NetworkIS'),
})
print(json.dumps({'status': 'PASSED', 'checks': ['live exact-stack reuse', 'different-source rejection',
                                              'unchanged containers', 'production readiness and build-info']}))
