"""Capture unmodified native HTTP exchanges from the exact candidate reasoner.

Diagnostic only, never an API proposal, model, simulation or release PASS.
The product code, prompt, schemas, native responses and model settings are not
patched. Stop after two completed chat responses; canonical data stays empty.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

sys.path.insert(0, '/app')
from backend.nis.agent.orchestration.local_reasoner import LocalEngineeringReasoner
from backend.nis.agent.orchestration.project_intake import prepare_reference_design
from backend.nis.engineering.projects.project_context import activate_project, reset_project

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--request', type=Path, required=True)
parser.add_argument('--request-sha256', required=True)
parser.add_argument('--project', required=True)
parser.add_argument('--expected-source', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
assert args.project != 'default' and args.project.startswith('20261018')
assert hashlib.sha256(args.request.read_bytes()).hexdigest() == args.request_sha256
args.output.mkdir(parents=True, exist_ok=False)


def get(path):
    request = Request('http://127.0.0.1:13500' + path, headers={'X-Project-ID': args.project})
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def canonical_checkpoint(name):
    value = get('/api/engineering/projects/export')
    (args.output / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False), encoding='utf8')
    assert value['project_id'].removeprefix('network-project-') == args.project
    assert all(not rows for rows in value['source_data'].values())
    assert all(not rows for rows in value['project_data'].values())


assert get('/api/build-info')['source_sha256'] == args.expected_source
assert (get('/api/engineering/agent/project-draft')['data']['reference_generation']['status']) == 'FAILED'
canonical_checkpoint('before-canonical')
token = activate_project(args.project)
try:
    prepared = prepare_reference_design(json.loads(args.request.read_text(encoding='utf8')))
finally:
    reset_project(token)


class CapturedEnough(Exception):
    pass


captured = []


async def capture_response(response):
    if not response.request.url.path.endswith('/chat'):
        return
    await response.aread()
    number = len(captured) + 1
    stem = f'chat-{number:02d}'
    request_bytes = response.request.content
    response_bytes = response.content
    (args.output / (stem + '-request.json')).write_bytes(request_bytes)
    (args.output / (stem + '-response.json')).write_bytes(response_bytes)
    body = response.json()
    row = {'call': number, 'http_status': response.status_code,
        'request_sha256': hashlib.sha256(request_bytes).hexdigest(),
        'response_sha256': hashlib.sha256(response_bytes).hexdigest(),
        'eval_count': body.get('eval_count'), 'prompt_eval_count': body.get('prompt_eval_count'),
        'done_reason': body.get('done_reason'), 'response_unmodified': True}
    captured.append(row)
    (args.output / 'captured-exchanges.json').write_text(json.dumps(captured, indent=2), encoding='utf8')
    print(json.dumps({'diagnostic_capture': row}), flush=True)
    if number >= 2:
        raise CapturedEnough('Two actual native responses captured without modifying them.')


async def run():
    reasoner = LocalEngineeringReasoner()
    reasoner.client.event_hooks['response'].append(capture_response)
    try:
        return await reasoner.plan_reference_design(prepared)
    finally:
        await reasoner.client.aclose()


result = {'scope': __doc__, 'project_id': args.project, 'source_sha256': args.expected_source,
    'api_workflow_replay': False, 'canonical_writes': False, 'native_original_pass': False,
    'simulation_pass': False, 'full_release_pass': False}
token = activate_project(args.project)
try:
    value = asyncio.run(run())
    (args.output / 'diagnostic-product-return-not-approved.json').write_text(json.dumps(value, ensure_ascii=False), encoding='utf8')
    result['status'] = 'DIAGNOSTIC_PRODUCT_METHOD_RETURNED_NOT_ACCEPTED'
except CapturedEnough as error:
    result.update(status='DIAGNOSTIC_CAPTURE_LIMIT_REACHED', detail=str(error))
except Exception as error:
    result.update(status='DIAGNOSTIC_PRODUCT_ERROR_CAPTURED', error=f'{type(error).__name__}: {error}')
finally:
    reset_project(token)
    canonical_checkpoint('after-canonical')
    result['completed_native_exchanges'] = len(captured)
    (args.output / 'diagnostic-result.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result), flush=True)
