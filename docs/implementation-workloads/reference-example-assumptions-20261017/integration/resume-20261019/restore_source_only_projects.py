"""Resume isolated original projects through the normal import API after reboot.

Only reimports the exact previously reviewed source-only request if the transient
test database lost its Wizard metadata. No model, route, profile, or SQL repair.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen

OUT = Path(__file__).resolve().parent
BASE = OUT.parent
ROOT = BASE.parents[2]
URL = 'http://127.0.0.1:63243'
IMAGE = 'sha256:194b475a5bad953cb92ae0ad4714b386cefdcbe0f668e26add27271e5f5d9def'
SOURCE = '2925100a1d49a9cf5f45eec60133ae1b3bd7d5ddee7f7631c1f31b2252d403a6'
D = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
AUDIT = []


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def request(name, path, project=None, raw=None, base=URL):
    headers = {'Content-Type': 'application/json'}
    if project:
        headers['X-Project-ID'] = project
    req = Request(base + path, data=raw, headers=headers)
    try:
        with urlopen(req, timeout=180) as response:
            body, status = response.read(), response.status
    except HTTPError as error:
        (OUT / (name + '-http-error.txt')).write_bytes(error.read())
        raise
    (OUT / (name + '.json')).write_bytes(body)
    AUDIT.append({'name': name, 'method': req.get_method(), 'url': base + path,
                  'project': project, 'status': status, 'response_sha256': sha(body),
                  'request_sha256': sha(raw) if raw is not None else None})
    return json.loads(body)


def empty(bundle, project):
    assert bundle['project_id'].removeprefix('network-project-') == project
    assert all(isinstance(rows, list) and not rows for rows in bundle['source_data'].values())
    assert all(isinstance(rows, list) and not rows for rows in bundle['project_data'].values())
    assert bundle['workflow']['parameters'] == {} and bundle['workflow']['topology'] == {}
    assert all(s == 'EMPTY' for s in bundle['workflow']['statuses'].values())


result = {'at_utc': datetime.now(timezone.utc).isoformat(), 'projects': [],
          'production_changed': False, 'new_inference_started': False}
try:
    app = json.loads(subprocess.check_output([D, 'inspect', 'nis-e2e-app-1b9d44329bc8']))[0]
    assert app['Image'] == IMAGE and app['State']['Running']
    assert app['HostConfig']['PortBindings']['13500/tcp'] == [{'HostIp': '127.0.0.1', 'HostPort': '63243'}]
    assert request('restored-build-info', '/api/build-info')['source_sha256'] == SOURCE
    assert request('restored-ready', '/api/ready')['status'] == 'ready'
    for case in ('vehicle', 'robot'):
        folder = BASE / ('native-staged-' + case)
        state_path = folder / 'state.json'
        state = json.loads(state_path.read_text(encoding='utf-8'))
        project = state['project_id']
        assert state['image_id'] == IMAGE and state['source_sha256'] == SOURCE
        assert state['base_url'] == URL
        assert sha(Path(state['source']).read_bytes()) == state['original_sha256']
        assert sha(Path(state['document_response']).read_bytes()) == state['reviewed_document_response_sha256']
        assert not (folder / 'plan-reference').exists(), 'Do not overwrite an existing run'
        bundle = request(case + '-before-restore', '/api/engineering/projects/export', project)
        empty(bundle, project)
        assert request(case + '-jobs-before-restore', '/api/simulations', project)['jobs'] == []
        assert request(case + '-reference-before-restore', '/api/engineering/agent/document-reference-design', project)['data'] is None
        raw = (folder / 'normal-import-result-request.json').read_bytes()
        previous = json.loads((folder / 'source-only-transfer.json').read_text(encoding='utf-8'))
        original_import = next(row for row in previous['http_evidence'] if row['name'] == 'normal-import-result')
        assert sha(raw) == original_import['request_sha256']
        payload = json.loads(raw)
        assert set(payload) == {'bundle'}
        empty(payload['bundle'], project)
        assert str(payload['bundle']['workflow']['context']['project_name']).upper().startswith('TEST')
        restored = not bool(bundle['workflow']['context'].get('engineering_wizard_settings'))
        if restored:
            allowed = {'active_project', 'active_workflow_step', 'selected_network', 'selected_object',
                       'selected_route', 'selected_signal', 'selected_simulation'}
            assert set(bundle['workflow']['context']) <= allowed
            (OUT / (case + '-exact-import-request.json')).write_bytes(raw)
            request(case + '-normal-import', '/api/engineering/projects/import', project, raw=raw)
        after = request(case + '-after-restore', '/api/engineering/projects/export', project)
        empty(after, project)
        assert after['workflow'] == payload['bundle']['workflow']
        assert request(case + '-jobs-after-restore', '/api/simulations', project)['jobs'] == []
        state['status'] = 'SOURCE_ONLY_TRANSFERRED_WAITING_NATIVE_REFERENCE'
        state['resume'] = {'at_utc': result['at_utc'], 'user_authorized': True,
                           'source_only_reimport_after_reboot': restored, 'evidence': str(OUT / 'source-only-recovery.json')}
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        result['projects'].append({'case': case, 'project_id': project, 'reimported': restored,
                                   'source_data_empty': True, 'workflow_exactly_preserved': True})
    models = request('resumed-local-models', '/api/tags', base='http://127.0.0.1:11434')
    assert any(model['name'] == 'qwen3.8:27b' for model in models['models'])
    request('resumed-loaded-models', '/api/ps', base='http://127.0.0.1:11434')
    request('resumed-production-ready', '/api/ready', base='http://127.0.0.1:13500')
    result['status'] = 'SOURCE_ONLY_RECOVERY_VERIFIED'
except Exception as error:
    result['status'] = 'FAILED'
    result['error'] = f'{type(error).__name__}: {error}'
    raise
finally:
    result['http_evidence'] = AUDIT
    (OUT / 'source-only-recovery.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'http_evidence'}, ensure_ascii=False), flush=True)
