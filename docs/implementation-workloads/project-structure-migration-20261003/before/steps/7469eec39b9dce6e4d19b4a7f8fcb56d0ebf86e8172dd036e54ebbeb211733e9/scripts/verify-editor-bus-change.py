"""HTTP smoke/consistency test on an isolated clone; never migrate the source."""
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE = 'http://127.0.0.1:15050/api/engineering'
SOURCE = 'network-project-20260910042736034-d11591d0'
TARGET = 'editor-bus-acceptance-20260910'


def call(path, payload=None, method=None, project=TARGET):
    request = Request(BASE + path, data=json.dumps(payload).encode() if payload is not None else None,
                      headers={'Content-Type': 'application/json', 'X-Project-ID': project}, method=method)
    try:
        with urlopen(request, timeout=180) as response:
            return json.load(response)
    except HTTPError as error:
        raise RuntimeError(f'{error.code}: {error.read().decode()}') from error


def rows(resource):
    result = []
    while True:
        page = call(f'/{resource}?limit=500&offset={len(result)}')['items']
        result.extend(page)
        if len(page) < 500:
            return result


if __name__ == '__main__':
    source_before = call('/workflow/network-view', project=SOURCE)
    existing = call('/workflow/network-view')
    if not existing['topology']['nodes']:
        bundle = call('/projects/export', project=SOURCE)
        bundle['project_data'] = {}  # Test the model, not copies of historic simulation traces.
        result = call('/projects/import', {'bundle': bundle, 'target_project_id': TARGET})
        print('isolated clone prepared', flush=True)
    state = call('/workflow/network-view')
    node = next(n for n in state['topology']['nodes'] if n['name'] == 'UreaLevel')
    edge = next(e for e in state['topology']['edges'] if node['id'] in (e['source'], e['target']))
    network = edge['physicalNetworkId']
    preview = call('/workflow/bus-technology/preview', {'network_id': network, 'bus': 'can_fd'})
    print('preview:', json.dumps(preview, ensure_ascii=False), flush=True)
    before_hwi, before_messages, before_signals = rows('hardware-interfaces'), rows('messages'), rows('signals')
    affected = {n['id'] for n in preview['networks']}
    assert len(affected) == 2, preview
    request = {'network_id': network, 'bus': 'can_fd', 'plan_token': preview['token'], 'expected_token': state['edit_tokens']['topology'], 'edge': edge}
    # Conflict must leave every canonical record and the saved topology untouched.
    try:
        call('/workflow/bus-technology', {**request, 'plan_token': 'stale'}, 'PUT')
        raise AssertionError('stale plan accepted')
    except RuntimeError as error:
        assert '409' in str(error), str(error)
    assert call('/workflow/network-view')['topology'] == state['topology']
    try:
        call('/workflow/bus-technology', {**request, 'edge': {**edge, 'relationType': 'INVALID_RELATION'}}, 'PUT')
        raise AssertionError('invalid relationship accepted')
    except RuntimeError as error:
        assert '400' in str(error), str(error)
    assert call('/workflow/network-view')['topology'] == state['topology']
    assert rows('hardware-interfaces') == before_hwi and rows('messages') == before_messages
    assert rows('signals') == before_signals
    started = time.monotonic()
    saved = call('/workflow/bus-technology', request, 'PUT')
    elapsed = time.monotonic() - started
    print(f'bus change persisted in {elapsed:.2f}s', flush=True)
    reloaded = call('/workflow/network-view')
    assert saved['topology'] == reloaded['topology']
    for e in reloaded['topology']['edges']:
        if e['physicalNetworkId'] in affected:
            assert e['bus'] == 'can_fd'
    after_hwi, after_messages, after_signals = rows('hardware-interfaces'), rows('messages'), rows('signals')
    for before, after in [(before_hwi, after_hwi), (before_messages, after_messages), (before_signals, after_signals)]:
        assert {r['id'] for r in before} == {r['id'] for r in after}, 'model identity changed'
    hwi_map = {r['id']: r for r in after_hwi}
    migrated_messages = []
    for h in after_hwi:
        if h['network_ref'] in affected:
            assert h['technology'] == 'CAN_FD' and h['bitrate'] != 19200
    for message in after_messages:
        hwi = hwi_map.get(message.get('hardware_interface_id'))
        if hwi and hwi['network_ref'] in affected:
            assert message['configuration']['technology_binding']['technology_id'] == 'can_fd'
            migrated_messages.append(message['id'])
    for signal in after_signals:
        if signal['message_id'] in migrated_messages:
            assert all(b['technology_binding_ref'] == 'can_fd' for b in signal['protocol_bindings'])
    routes = rows('routing')
    changed = [r for r in routes if r.get('modified_by') == 'network-editor-bus-change']
    assert changed and all(r['approval_state'] == 'PENDING' for r in changed)
    assert all(r['validation']['valid'] for r in changed), [(r['route_code'], r['validation']['errors']) for r in changed if not r['validation']['valid']]
    approved = call('/routing/approve-selected', {'route_ids': [r['id'] for r in changed], 'actor': 'editor-acceptance'})
    assert all(r['approval_state'] == 'APPROVED' for r in approved['items'])
    source_after = call('/workflow/network-view', project=SOURCE)
    assert source_before == source_after, 'source project changed during isolated test'
    report = {'project': TARGET, 'preview': preview, 'elapsed_seconds': round(elapsed, 3), 'stale_plan_rejected': True, 'transaction_rollback_verified': True,
              'ids_preserved': True, 'canonical_bindings_consistent': True, 'reapproved_routes': len(changed), 'source_unchanged': True}
    Path('docs/editor-bus-change-acceptance.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)
