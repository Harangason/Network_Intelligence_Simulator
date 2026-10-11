"""Compare patched capacity math with/without reuse in a diagnostic process only.

The tested app process and image files remain unchanged. The two host modules
are imported from memory in a separate Python process; persist=False is mandatory.
"""
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
sources = {name: (ROOT / path).read_text(encoding='utf-8') for name, path in {
    'backend.nis.communication.registry': 'backend/nis/communication/registry.py',
    'backend.nis.engineering.capacity.service': 'backend/nis/engineering/capacity/service.py',
}.items()}
code = 'sources = ' + repr(sources) + '\n' + '''
import importlib.abc, importlib.util, sys, time, json, hashlib
class SourceLoader(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in sources:
            return importlib.util.spec_from_loader(fullname, self)
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        module.__file__ = '/app/' + module.__name__.replace('.', '/') + '.py'
        exec(compile(sources[module.__name__], module.__file__, 'exec'), module.__dict__)
sys.meta_path.insert(0, SourceLoader())
from backend.nis.agent.tools.runtime import ToolAuthority, execute
from backend.nis.agent.api.tool_contract import Permission
from backend.nis.agent.tools import model
from backend.nis.engineering.capacity.service import CapacityTimingService
from backend.nis.engineering.capacity import service as capacity_module
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
def inspect(_):
    captured_timestamp = capacity_module._now()
    capacity_module._now = lambda: captured_timestamp
    service = CapacityTimingService('nis-e2e-large-36a54b9a-9627-4f8a-86bf-95ad2c461ea9')
    revision = model.model_revision()
    times, calls, digests = {}, {}, {}
    original = registry._validate_parameters
    counter = 0
    def observed(technology, values):
        nonlocal counter
        counter += 1
        return original(technology, values)
    registry._validate_parameters = observed
    results = []
    for name, method in [('uncached', service._calculate), ('scoped_cache', service.calculate)]:
        counter = 0
        started = time.perf_counter()
        result = method(persist=False)
        times[name] = time.perf_counter() - started
        calls[name] = counter
        digests[name] = hashlib.sha256(json.dumps(result, sort_keys=True, default=str).encode()).hexdigest()
        results.append(result)
    def differences(left, right, path=''):
        if type(left) is not type(right):
            return [{'path': path, 'left': str(left)[:200], 'right': str(right)[:200]}]
        if isinstance(left, dict):
            return [row for key in left.keys() | right.keys()
                    for row in differences(left.get(key), right.get(key), path + '.' + str(key))]
        if isinstance(left, list):
            if len(left) != len(right):
                return [{'path': path, 'left_length': len(left), 'right_length': len(right)}]
            return [row for index, (a, b) in enumerate(zip(left, right))
                    for row in differences(a, b, path + '[' + str(index) + ']')]
        return [] if left == right else [{'path': path, 'left': left, 'right': right}]
    changes = differences(results[0], results[1])
    print('COMPARISON_DIFFERENCES='+json.dumps({'changes': changes, 'seconds': times, 'calls': calls}, default=str), flush=True)
    assert not changes, 'Calculation outputs changed.'
    assert revision == model.model_revision(), 'Canonical source changed during comparison.'
    assert calls['scoped_cache'] < calls['uncached']
    return {'status': 'EXACT_RESULTS_PRESERVED', 'persist': False, 'model_revision': revision,
            'captured_calculation_timestamp': captured_timestamp,
            'seconds': times, 'native_validation_calls': calls, 'result_sha256': digests,
            'scope': 'Separate diagnostic Python process; no modification of tested image or app process.'}
result = execute(ToolAuthority('nis-e2e-large-36a54b9a-9627-4f8a-86bf-95ad2c461ea9', 'read-only-performance-diagnosis'),
    'compare_non_persisting_capacity', Permission.READ_MODEL, {}, inspect)
print('CAPACITY_COMPARISON='+json.dumps(result.model_dump(mode='json'), ensure_ascii=True), flush=True)
'''
for name in ('capacity-comparison.log', 'capacity-comparison.json'):
    path = HERE / name
    if path.exists():
        number = 1
        prior = HERE / ('attempt-' + str(number) + '-' + name)
        while prior.exists():
            number += 1
            prior = HERE / ('attempt-' + str(number) + '-' + name)
        path.rename(prior)
result = subprocess.run([docker, 'exec', '-i', 'nis-e2e-app-ba52fd62fb41', 'python', '-'],
    input=code, text=True, encoding='utf-8', capture_output=True, check=True)
(HERE / 'capacity-comparison.log').write_text(result.stdout + result.stderr, encoding='utf-8')
payload = json.loads(next(line.removeprefix('CAPACITY_COMPARISON=') for line in result.stdout.splitlines() if line.startswith('CAPACITY_COMPARISON=')))
(HERE / 'capacity-comparison.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
assert payload['success'], payload.get('findings')
print(json.dumps(payload['data'], indent=2))
