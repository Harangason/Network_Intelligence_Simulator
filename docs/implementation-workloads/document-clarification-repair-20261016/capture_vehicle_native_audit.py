"""Capture actual production READ_MODEL tool evidence, not a SQL test or inference."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
PROJECT = '20261016122109077-dc3a1aeb'
IMAGE = 'sha256:8da9bfdb94047460fc1e34d276b02da75299e7fee496d1f33491b4d261f7ecc1'
SOURCE = '6d043e08d96ac98272a549ca9928eef1f77385d6dc07fd3e513588bf16e32694'
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']


def docker_read(*arguments, stdin=None):
    return subprocess.run([docker, *arguments], input=stdin, capture_output=True,
                          text=True, encoding='utf-8', check=True).stdout.strip()


container = json.loads(docker_read('inspect', 'NetworkIS'))[0]
assert container['Image'] == IMAGE and container['State']['Running']
environment = dict(item.split('=', 1) for item in container['Config']['Env'] if '=' in item)
program = '''import json
from backend.nis.agent.api.tool_contract import Permission
from backend.nis.agent.tools.runtime import ToolAuthority, execute
from backend.nis.agent.tools.services import TOOLS, register_tools
register_tools()
authority = ToolAuthority('20261016122109077-dc3a1aeb', 'vehicle-native-evidence-read', frozenset({Permission.READ_MODEL}))
results = {}
for name, arguments in [('inspect_agent_audit', {'limit': 100}), ('inspect_project', {})]:
    definition = TOOLS[name]
    assert definition.permission == Permission.READ_MODEL
    data = definition.input_model.model_validate(arguments).model_dump(mode='json')
    result = execute(authority, name, definition.permission, data, definition.handler)
    assert result.success
    results[name] = result.model_dump(mode='json')
print(json.dumps(results))
'''
tools = json.loads(docker_read('exec', '-i', 'NetworkIS', 'python', '-', stdin=program))
events = [event for event in tools['inspect_agent_audit']['data']
          if event['tool_name'] == 'interpret_project_document']
assert len(events) == 1 and events[0]['details']['success'] is True
assert events[0]['details']['result']['status'] == 'REVIEW_REQUIRED'
assert not events[0]['details']['affected_objects']
project = tools['inspect_project']['data']
assert all(status == 'EMPTY' for status in project['statuses'].values())
assert docker_read('inspect', 'NetworkIS', '--format', '{{.Image}}') == IMAGE
record = {
    'status': 'PASSED', 'at_utc': datetime.now(timezone.utc).isoformat(),
    'project_id': PROJECT, 'image_id': IMAGE, 'source_sha256': SOURCE,
    'scope': 'Actual production operational READ_MODEL tools after the normal UI native intake. Not a SQL test, model-generation test, or HTTP inference-call count.',
    'uses_product_database': True,
    'canonical_model_writes': False,
    'audit_note': 'Registered read tools may append their ordinary tool audit entries; no model mutation permission was granted.',
    'read_tools': list(tools), 'interpretation_events': events,
    'workflow_statuses': project['statuses'],
    'engineering_model_check': project['artifact_checks']['engineering_model'],
    'configured_local_model': {key: environment.get(key) for key in
                               ('LOCAL_AI_BASE_URL', 'LOCAL_AI_MODEL')},
}
(OUT / 'vehicle-production-native-audit.json').write_text(
    json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'status': record['status'], 'project_id': PROJECT,
                  'native_registered_tool_invocations': len(events),
                  'workflow_statuses': project['statuses']}))
