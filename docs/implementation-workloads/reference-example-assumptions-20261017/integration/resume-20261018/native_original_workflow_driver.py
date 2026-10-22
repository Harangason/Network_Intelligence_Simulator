"""Operate the normal NIS review boundaries in an explicitly isolated project.

No model definitions, fixture profiles, SQL, replacement routes or automatic
approvals. Every mutating invocation requires a separately inspected, hash-bound
operator review. One invocation performs one ordinary UI/API action, then stops.
This is API-native evidence, not a claim of a nine-stage browser test.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from http.cookiejar import CookieJar
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPCookieProcessor, Request
from uuid import uuid4


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--state', type=Path, required=True)
parser.add_argument('--action', required=True, choices=[
    'inspect', 'accept-reference', 'start', 'continue', 'review-apply', 'approve-preflight'])
parser.add_argument('--checkpoint', required=True)
parser.add_argument('--review', type=Path)
args = parser.parse_args()
assert re.fullmatch('[a-z0-9-]+', args.checkpoint)
state = json.loads(args.state.read_text(encoding='utf-8'))
BASE, PROJECT = state['base_url'], state['project_id']
endpoint = urlsplit(BASE)
assert endpoint.hostname == '127.0.0.1' and endpoint.port not in {None, 13500, 15050}
assert PROJECT and PROJECT != 'default'
assert sha(Path(state['source']).read_bytes()) == state['original_sha256']
assert state.get('document_review_status') == 'APPROVED_LITERAL_SOURCE_FINDINGS'
assert sha(Path(state['document_response']).read_bytes()) == state['reviewed_document_response_sha256']
OUT = args.state.resolve().parent / 'workflow' / args.checkpoint
OUT.mkdir(parents=True, exist_ok=False)
opener = build_opener(HTTPCookieProcessor(CookieJar()))
evidence = []
mutations = []


def request(name, path, payload=None, headers=None, stream=False):
    began = time.monotonic()
    raw = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
    if raw is not None:
        (OUT / (name + '-request.json')).write_bytes(raw)
        mutations.append({'path': path, 'request_sha256': sha(raw)})
    req = Request(BASE + path, data=raw, headers={
        'X-Project-ID': PROJECT, 'Content-Type': 'application/json', **(headers or {})})
    try:
        with opener.open(req, timeout=180) as response:
            if stream:
                result = []
                with (OUT / (name + '-events.ndjson')).open('w', encoding='utf-8') as log:
                    for line in response:
                        if not line.strip():
                            continue
                        event = json.loads(line)
                        log.write(json.dumps(event, ensure_ascii=False) + '\n')
                        log.flush()
                        result.append(event)
                        if event.get('type') not in {'HEARTBEAT', 'TOKEN'}:
                            print(json.dumps({key: event[key] for key in ('type', 'status', 'text') if key in event}, ensure_ascii=False), flush=True)
            else:
                result = json.load(response)
            dump(OUT / (name + '.json'), result)
            evidence.append({'name': name, 'path': path, 'method': req.get_method(),
                             'status': response.status, 'seconds': time.monotonic() - began,
                             'request_sha256': sha(raw) if raw is not None else None,
                             'response_file_sha256': sha((OUT / (name + '.json')).read_bytes())})
            return result
    except HTTPError as error:
        (OUT / (name + '-http-error.txt')).write_bytes(error.read())
        raise


def inspect(prefix):
    result = {}
    for key, path in {
        'workflow': '/api/engineering/workflow',
        'conversation': '/api/engineering/agent/conversation',
        'reference': '/api/engineering/agent/document-reference-design',
        'bundle': '/api/engineering/projects/export',
        'jobs': '/api/simulations',
    }.items():
        result[key] = request(prefix + '-' + key, path)
    assert result['bundle']['project_id'].removeprefix('network-project-') == PROJECT
    return result


def require_review():
    assert args.review, 'A separately inspected hash-bound review is required.'
    review = json.loads(args.review.read_text(encoding='utf-8'))
    assert review['project_id'] == PROJECT
    assert review['image_id'] == state['image_id']
    assert review['source_sha256'] == state['source_sha256']
    assert review['original_sha256'] == state['original_sha256']
    assert review['action'] == args.action and review['decision'] == 'APPROVE'
    assert review.get('findings') == [], 'Unresolved findings cannot be approved by this operator.'
    assert review.get('scope'), 'The review must state its actual scope.'
    files = review['reviewed_files']
    assert files and all(sha(Path(row['path']).read_bytes()) == row['sha256'] for row in files)
    dump(OUT / 'operator-review.json', review)
    return review


status = 'INCOMPLETE'
try:
    build = request('build-info', '/api/build-info')
    assert build['source_sha256'] == state['source_sha256']
    assert request('ready', '/api/ready')['status'] == 'ready'
    before = inspect('before')
    review = require_review() if args.action != 'inspect' else None
    if args.action != 'inspect':
        session = request('review-session', '/api/engineering/agent/review-session')
        intent = {'X-Review-CSRF': session['csrf_token'], 'X-Human-Review': 'confirmed'}
    if args.action == 'accept-reference':
        record = before['reference']['data']
        assert record['project_id'].removeprefix('network-project-') == PROJECT
        assert record['status'] == 'REVIEW_REQUIRED' and record['canonical_writes'] is False
        assert record['source_sha256'] == state['original_sha256']
        assert record['proposal']['unresolved'] == []
        assert all(review[key] == record[key] for key in ('design_id', 'revision', 'request_sha256'))
        accepted = request('accept-reference', '/api/engineering/agent/document-reference-design/accept',
                           {key: record[key] for key in ('design_id', 'revision', 'request_sha256')}, intent)
        assert accepted['success'] and accepted['data']['status'] == 'ACCEPTED'
        assert accepted['data']['canonical_writes'] is False
    elif args.action in {'start', 'continue'}:
        assert review['run_id']
        command = {'action': args.action.upper(), 'run_id': review['run_id'], 'operation_id': str(uuid4())}
        if args.action == 'start':
            record = before['reference']['data']
            assert record['project_id'].removeprefix('network-project-') == PROJECT
            assert record['status'] == 'ACCEPTED' and record['canonical_writes'] is False
            assert record['source_sha256'] == state['original_sha256']
            assert all(review[key] == record[key] for key in ('design_id', 'revision', 'request_sha256'))
            assert not any(len(rows) for rows in before['bundle']['source_data'].values())
            # Reproduce the entire inspected product projection from the current
            # actual server record. A free-form prompt/context is not accepted.
            assert re.fullmatch('[A-Za-z0-9._-]{8,120}', review['run_id'])
            project_name = review['project_name']
            assert isinstance(project_name, str) and 1 <= len(project_name) <= 200
            assert not any(ord(char) < 32 for char in project_name)
            projection_path = Path(review['projection_file'])
            helper = Path(__file__).with_name('native_original_workflow_prompt.mjs')
            assert all(any(Path(row['path']).resolve() == required.resolve()
                           for row in review['reviewed_files']) for required in (projection_path, helper))
            accepted_path = OUT / 'actual-current-accepted-record.json'
            dump(accepted_path, record)
            root = Path(__file__).resolve().parents[5]
            projected = json.loads(subprocess.check_output([
                r'C:/Program Files/nodejs/node.exe', '--experimental-strip-types', str(helper),
                str(root), str(accepted_path), review['run_id'], PROJECT, project_name,
            ], text=True, encoding='utf-8', cwd=root))
            assert projected == json.loads(projection_path.read_text(encoding='utf-8'))
            dump(OUT / 'reproduced-product-projection.json', projected)
            prompt = projected['prompt']
            command.update(target='data_science_intelligence', wizard_context=projected['wizard_context'])
            assert command['wizard_context']['run_id'] == review['run_id']
            assert command['wizard_context']['project_id'] == PROJECT
            assert set(command['wizard_context']['scope_ids']) == {
                'engineering_model', 'routing', 'network_editor', 'parameters', 'capacity_timing',
                'validation', 'simulation', 'results_analysis', 'data_science_intelligence'}
            # Every context value is the exact reproduced pure-product projection;
            # no caller-supplied extra context fields or appended prompt survive.
        else:
            assert review['request_revision']
            command['request_revision'] = review['request_revision']
            prompt = ''  # The server restores the immutable confirmed request.
        request('wizard-command', '/api/engineering/agent/chat', {'prompt': prompt, 'wizard_command': command}, intent, True)
    elif args.action == 'review-apply':
        proposal_id = review['proposal_id']
        assert re.fullmatch('[A-Za-z0-9_-]+', proposal_id)
        route = '/api/engineering/agent/proposals/' + proposal_id
        proposal = request('proposal', route)['data']
        assert proposal['status'] == 'VALIDATED' and proposal['revision'] == review['revision']
        # Compare the whole actual proposal, not only a status or its displayed label.
        reviewed = json.loads(Path(review['proposal_file']).read_text(encoding='utf-8'))
        if 'data' in reviewed:
            reviewed = reviewed['data']
        assert reviewed == proposal
        assert any(Path(row['path']).resolve() == Path(review['proposal_file']).resolve() for row in review['reviewed_files'])
        approved = request('approve-proposal', route + '/review', {'decision': 'approve', 'revision': proposal['revision']}, intent)
        assert approved['success'] and approved['data']['status'] == 'APPROVED'
        applied = request('apply-proposal', route + '/apply?view=status', {'revision': approved['data']['revision']}, intent)
        assert applied['success'] and applied['data']['status'] == 'APPLIED'
    elif args.action == 'approve-preflight':
        preflight = request('preflight', '/api/engineering/preflight')
        assert preflight['id'] == review['snapshot_id']
        assert preflight['results']['preflight_status'] == 'READY_WITH_WARNINGS'
        reviewed = json.loads(Path(review['preflight_file']).read_text(encoding='utf-8'))
        assert reviewed == preflight
        assert any(Path(row['path']).resolve() == Path(review['preflight_file']).resolve() for row in review['reviewed_files'])
        result = request('approve-preflight', '/api/engineering/preflight/warnings/approve',
                         {'snapshot_id': preflight['id'], 'actor': 'native-original-source-review'}, intent)
        assert result['preflight']['ready_for_simulation']
    after = inspect('after') if args.action != 'inspect' else before
    if args.action == 'accept-reference':
        assert after['bundle']['source_data'] == before['bundle']['source_data']
    status = 'COMPLETED_SINGLE_PRODUCT_ACTION'
finally:
    dump(OUT / 'manifest.json', {
        'at_utc': datetime.now(timezone.utc).isoformat(), 'action': args.action,
        'status': status, 'project_id': PROJECT, 'base_url': BASE,
        'image_id': state['image_id'], 'source_sha256': state['source_sha256'],
        'original_sha256': state['original_sha256'], 'operator_sha256': sha(Path(__file__).read_bytes()),
        'scope': __doc__, 'http_evidence': evidence, 'mutations_sent': mutations,
        'simulation_pass': False, 'full_release_pass': False, 'productive_delivery': False})
    print(json.dumps({'project_id': PROJECT, 'action': args.action, 'status': status}), flush=True)
