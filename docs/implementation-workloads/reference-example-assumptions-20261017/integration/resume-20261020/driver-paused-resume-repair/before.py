"""Drive actual NIS document APIs and stop at review boundaries.

No model writes, replacement design, synthetic parameter profiles or SQL.
Intake and reference planning are the same endpoints used by the Wizard.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from http.cookiejar import CookieJar
import json
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPCookieProcessor, Request
from uuid import uuid4

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--state', type=Path, required=True)
parser.add_argument('--stage', choices=['intake', 'plan-reference'], required=True)
args = parser.parse_args()
state = json.loads(args.state.read_text(encoding='utf-8'))
OUT = args.state.resolve().parent
ROOT = Path(__file__).resolve().parents[5]
BASE, PROJECT = state['base_url'], state['project_id']
endpoint = urlsplit(BASE)
assert endpoint.hostname == '127.0.0.1' and endpoint.port not in {None, 13500, 15050}
assert PROJECT and PROJECT != 'default'
original = Path(state['source']).read_bytes()
assert hashlib.sha256(original).hexdigest() == state['original_sha256']
source = original.decode('utf-8')
assert len(source) == state['original_chars']
PHASE = OUT / args.stage
PHASE.mkdir(exist_ok=False)
opener = build_opener(HTTPCookieProcessor(CookieJar()))
evidence = []
canonical_checks = []

def save_state(status, **values):
    state.update(at_utc=datetime.now(timezone.utc).isoformat(), status=status, **values)
    args.state.write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def request(path, payload=None, headers=None, stream=False):
    began = time.monotonic()
    raw = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = Request(BASE + path, data=raw,
                  headers={'X-Project-ID': PROJECT, 'Content-Type': 'application/json', **(headers or {})})
    try:
        with opener.open(req, timeout=90) as response:
            if stream:
                events = []
                with (PHASE / 'events.ndjson').open('w', encoding='utf-8') as log:
                    for line in response:
                        if not line.strip(): continue
                        event = json.loads(line)
                        log.write(json.dumps(event, ensure_ascii=False)+'\n'); log.flush()
                        events.append(event)
                        if event.get('type') == 'PROGRESS':
                            progress = event.get('text', '')
                            save_state('NATIVE_' + args.stage.upper().replace('-', '_') + '_RUNNING', ui_progress=progress)
                            print(json.dumps({'project_id': PROJECT, 'progress': progress}, ensure_ascii=False), flush=True)
                final = [e['result'] for e in events if e.get('type') == 'RESULT']
                assert len(final) == 1, 'Native stream did not yield exactly one final result.'
                value = final[0]
                (PHASE / 'response.json').write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
                assert value['success'], value.get('findings')
                result = value['data']
            else:
                result = json.load(response)
            evidence.append({'path': path, 'status': response.status,
                             'request_sha256': hashlib.sha256(raw).hexdigest() if raw is not None else None,
                             'seconds': time.monotonic()-began})
            return result
    except HTTPError as error:
        (PHASE / 'http-error.txt').write_bytes(error.read())
        raise

def assert_no_model():
    bundle = request('/api/engineering/projects/export')
    assert bundle['project_id'].removeprefix('network-project-') == PROJECT
    counts = {key: len(value) for key, value in bundle['source_data'].items()}
    canonical_checks.append({'at_utc': datetime.now(timezone.utc).isoformat(), 'counts': counts,
                             'verified_empty': not any(counts.values())})
    (PHASE/'canonical-model-observations.json').write_text(json.dumps(canonical_checks, indent=2)+'\n')
    assert not any(counts.values()), counts
    return counts

try:
    build = request('/api/build-info')
    assert build['source_sha256'] == state['source_sha256']
    assert request('/api/ready')['status'] == 'ready'
    initial_counts = assert_no_model()
    session = request('/api/engineering/agent/review-session')
    intent = {'Accept': 'application/x-ndjson', 'X-Human-Review': 'confirmed', 'X-Review-CSRF': session['csrf_token']}
    if args.stage == 'intake':
        payload = {'source': source, 'source_name': Path(state['source']).name, 'source_request_id': uuid4().hex}
        (PHASE / 'request.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        proposal = request('/api/engineering/agent/document-intake', payload, intent, True)
        assert proposal['source_request_id'] == payload['source_request_id']
        assert proposal['source_complete'] and proposal['canonical_writes'] is False
        assert proposal['source_sha256'] == state['original_sha256'] and proposal['source_chars'] == len(source)
        assert proposal['status'] == 'REVIEW_REQUIRED' and proposal['provider'] == 'local_ollama'
        proposal_file = PHASE / 'proposal.json'
        proposal_file.write_text(json.dumps(proposal, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        save_state('NATIVE_DOCUMENT_REVIEW_REQUIRED', document_response=str(proposal_file.resolve()),
                   document_response_sha256=hashlib.sha256(proposal_file.read_bytes()).hexdigest())
    else:
        # The operator must inspect the actual saved document proposal first.
        assert state.get('document_review_status') == 'APPROVED_LITERAL_SOURCE_FINDINGS'
        assert hashlib.sha256(Path(state['document_response']).read_bytes()).hexdigest() == state['document_response_sha256']
        assert state['reviewed_document_response_sha256'] == state['document_response_sha256']
        pending = request('/api/engineering/agent/project-draft')['data']
        assert not pending or (pending.get('reference_generation') or {}).get('status') != 'RUNNING'
        command = [r'C:/Program Files/nodejs/node.exe', '--experimental-strip-types',
                   str(Path(__file__).with_name('native_original_review_adapter.mjs')),
                   str(ROOT), str(Path(state['source'])), state['document_response']]
        reviewed = json.loads(subprocess.check_output(command, text=True, encoding='utf-8', cwd=ROOT))
        (PHASE/'actual-product-review.json').write_text(json.dumps(reviewed, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        references = []
        for index, reference in enumerate(state.get('reference_sources', [])):
            text = Path(reference['path']).read_bytes().decode('utf-8')
            assert hashlib.sha256(text.encode()).hexdigest() == reference['source_sha256']
            references.append({'id': f'reference-{index}', 'name': Path(reference['path']).name,
                'role': reference['role'], 'text': text, 'source_sha256': hashlib.sha256(text.encode()).hexdigest(),
                'allowed_fields': reference['allowed_fields']})
        payload = {'mode': 'EXAMPLE_PROJECT', 'prompt': reviewed['prompt'],
                   'source_request_id': str(uuid4()), 'reference_sources': references}
        (PHASE / 'request.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        record = request('/api/engineering/agent/document-reference-design', payload, intent, True)
        assert record['canonical_writes'] is False and record['status'] == 'REVIEW_REQUIRED'
        assert record['source_sha256'] == state['original_sha256']
        (PHASE/'record.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        save_state('NATIVE_REFERENCE_REVIEW_REQUIRED', reference_record=str((PHASE/'record.json').resolve()))
    assert assert_no_model() == initial_counts
except Exception as error:
    save_state('NATIVE_' + args.stage.upper().replace('-', '_') + '_FAILED', error=f'{type(error).__name__}: {error}')
    raise
finally:
    (PHASE/'http-evidence.json').write_text(json.dumps(evidence, indent=2)+'\n')
    observation = ('VERIFIED_EMPTY_BEFORE_AND_AFTER' if len(canonical_checks) >= 2 and all(c['verified_empty'] for c in canonical_checks)
                   else 'UNEXPECTED_CANONICAL_OBJECTS' if any(not c['verified_empty'] for c in canonical_checks)
                   else 'INCOMPLETE_OBSERVATION')
    state['canonical_model_observation'] = observation
    args.state.write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'project_id': PROJECT, 'status': state['status'],
                      'canonical_model_write_operations_sent_by_driver': False,
                      'canonical_model_observation': observation,
                      'simulation_pass': False, 'productive_delivery': False}), flush=True)
