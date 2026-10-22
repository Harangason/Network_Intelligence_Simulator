"""Read actual registered audit/project tools in the owned native stack."""
from pathlib import Path
import datetime
import json
import subprocess
from urllib.parse import urlsplit

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
runtime = json.loads((OUT / 'native-runtime-preparation.json').read_text(encoding='utf-8'))
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']
app_name = runtime['containers']['app']
assert app_name.startswith('nis-e2e-app-')
app = json.loads(subprocess.check_output([docker, 'inspect', app_name], text=True, encoding='utf-8'))[0]
assert app['Image'] == runtime['image_id'] and app['Config']['Labels']['networkis.test'] == 'disposable'
environment = dict(item.split('=', 1) for item in app['Config']['Env'] if '=' in item)
database = urlsplit(environment['DATABASE_URL'])
assert database.hostname == 'test-db' and database.path == '/nis_test_e2e'
program = '''import json
from backend.nis.agent.api.tool_contract import Permission
from backend.nis.agent.tools.runtime import ToolAuthority, execute
from backend.nis.agent.tools.services import TOOLS, register_tools
register_tools()
authority = ToolAuthority('20261016084924562-131ed051', 'native-document-verification', frozenset({Permission.READ_MODEL}))
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
result = subprocess.run([docker, 'exec', '-i', app_name, 'python', '-'], input=program,
                        capture_output=True, text=True, encoding='utf-8', check=True)
tools = json.loads(result.stdout)
events = [event for event in tools['inspect_agent_audit']['data'] if event['tool_name'] == 'interpret_project_document']
assert len(events) == 1 and events[0]['details']['success'] is True
assert events[0]['details']['result']['status'] == 'REVIEW_REQUIRED'
assert not events[0]['details']['affected_objects']
project = tools['inspect_project']['data']
assert all(status == 'EMPTY' for status in project['statuses'].values())
record = {'status': 'PASSED', 'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'scope': 'Actual registered read-only tool calls against the owned native stack; one successful native document tool invocation, not an HTTP inference-call count.',
          'image_id': app['Image'], 'source_sha256': runtime['source_sha256'], 'uses_product_database': False,
          'interpretation_events': events, 'workflow_statuses': project['statuses'],
          'engineering_model_check': project['artifact_checks']['engineering_model'], 'read_tools': list(tools)}
(OUT / 'native-tool-audit.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'status': record['status'], 'native_tool_invocations': len(events), 'workflow_statuses': project['statuses']}))
