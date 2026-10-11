"""Profile read-only canonical reads in the failed disposable wizard project."""
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
from backend.nis.agent.tools import model
from backend.nis.engineering.network.physical_ports import physical_transmit_changes
def inspect(_):
    snapshot = model.model()
    revision = model.model_revision()
    changes = physical_transmit_changes(snapshot['topology'], snapshot['routing'], snapshot['messages'], logical_interfaces=snapshot['interfaces'])
    return {'revision': revision, 'binding_changes': len(changes)}
profile = cProfile.Profile()
result = profile.runcall(execute, ToolAuthority('nis-e2e-large-36a54b9a-9627-4f8a-86bf-95ad2c461ea9', 'read-only-performance-diagnosis'), 'profile_read_only_model', Permission.READ_MODEL, {}, inspect)
stream = io.StringIO()
pstats.Stats(profile, stream=stream).sort_stats('cumulative').print_stats(45)
print('PROFILE_RESULT='+json.dumps(result.model_dump(mode='json'), ensure_ascii=True), flush=True)
print(stream.getvalue(), flush=True)
'''
result = subprocess.run([docker, 'exec', '-i', 'nis-e2e-app-ba52fd62fb41', 'python', '-'],
    input=code, text=True, encoding='utf-8', capture_output=True, check=True)
(HERE / 'isolated-model-read-profile.log').write_text(result.stdout + result.stderr, encoding='utf-8')
print(result.stdout)
