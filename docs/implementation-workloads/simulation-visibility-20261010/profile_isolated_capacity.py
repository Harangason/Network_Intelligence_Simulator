"""Profile non-persisting capacity computation on the disposable failed model."""
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
code = '''
import cProfile, io, pstats, json
from backend.nis.agent.tools.runtime import ToolAuthority, execute
from backend.nis.agent.api.tool_contract import Permission
from backend.nis.engineering.capacity.service import CapacityTimingService
def inspect(_):
    result = CapacityTimingService('nis-e2e-large-36a54b9a-9627-4f8a-86bf-95ad2c461ea9').calculate(persist=False)
    return {'status': result.get('status'), 'persist': False}
profile = cProfile.Profile()
result = profile.runcall(execute, ToolAuthority('nis-e2e-large-36a54b9a-9627-4f8a-86bf-95ad2c461ea9', 'read-only-performance-diagnosis'), 'profile_non_persisting_capacity', Permission.READ_MODEL, {}, inspect)
stream = io.StringIO()
pstats.Stats(profile, stream=stream).sort_stats('cumulative').print_stats(55)
print('PROFILE_RESULT='+json.dumps(result.model_dump(mode='json'), ensure_ascii=True), flush=True)
print(stream.getvalue(), flush=True)
'''
result = subprocess.run([docker, 'exec', '-i', 'nis-e2e-app-ba52fd62fb41', 'python', '-'],
    input=code, text=True, encoding='utf-8', capture_output=True, check=True)
(HERE / 'isolated-capacity-profile.log').write_text(result.stdout + result.stderr, encoding='utf-8')
print(result.stdout)
