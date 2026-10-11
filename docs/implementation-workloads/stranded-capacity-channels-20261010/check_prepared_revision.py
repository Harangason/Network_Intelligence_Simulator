"""Check the pending proposal/model revision without changing engineering objects."""
import json, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
proposal_id = json.loads((HERE / 'prepared-reconciliation-proposal.json').read_text(encoding='utf-8'))['data']['proposal_id']
code = '''
import json
from backend.nis.agent.tools.runtime import ToolAuthority, execute
from backend.nis.agent.api.tool_contract import Permission
from backend.nis.agent.tools import model, proposal_service
result = execute(ToolAuthority('20261009072206008-4bb505f1', 'codex-authorized-maintenance'),
    'inspect_pending_reconciliation_revision', Permission.READ_MODEL, {},
    lambda _: {'revision': model.model_revision(), 'proposal_status': proposal_service.get('bed69265-d691-4e33-9f18-bf80246f4da5')['status']})
print('NIS_READ='+json.dumps(result.model_dump(mode='json'), ensure_ascii=True), flush=True)
'''
code = code.replace('bed69265-d691-4e33-9f18-bf80246f4da5', proposal_id)
result = subprocess.run([docker, 'exec', '-i', 'NetworkIS', 'python', '-'], input=code,
    text=True, encoding='utf-8', capture_output=True)
(HERE / 'revision-read.log').write_text(result.stdout + result.stderr, encoding='utf-8')
assert result.returncode == 0, 'See revision-read.log'
payload = json.loads(next(line.removeprefix('NIS_READ=') for line in result.stdout.splitlines() if line.startswith('NIS_READ=')))
(HERE / 'revision-before-release.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
assert payload['success'], payload.get('findings')
expected = json.loads((HERE / 'reconciliation-preview.json').read_text(encoding='utf-8'))['base_model_revision']
assert payload['data']['revision'] == expected, 'PLAN_STALE: rebuild before applying.'
print(json.dumps(payload['data']))
