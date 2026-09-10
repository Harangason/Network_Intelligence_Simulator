"""Apply the reviewed Ethernet naming policy with optimistic concurrency and a backup."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import urllib.request
from backend.engineering.naming import ethernet_names
from backend.engineering.network_naming import rename_network

PROJECT = 'network-project-20260910042736034-d11591d0'
def api(path, payload=None):
    request = urllib.request.Request('http://127.0.0.1:15050/api/engineering' + path,
        headers={'X-Project-ID': PROJECT, 'Content-Type': 'application/json'},
        data=json.dumps(payload).encode() if payload is not None else None,
        method='PUT' if payload is not None else 'GET')
    return json.load(urllib.request.urlopen(request, timeout=90))

def run():
    before = api('/workflow')
    named = ethernet_names(before['parameters']['networks'], topology=before['topology'])
    old_names = {row['id']: row.get('name') for row in before['parameters']['networks']}
    changed = {key: row for key, row in named.items() if row.get('name') != old_names[key]}
    channels = {p['hardwareInterfaceId']: api('/hardware-interfaces/' + p['hardwareInterfaceId'])
        for n in before['topology']['nodes'] for p in n['ports'] if p.get('physicalNetworkId') in changed and p.get('hardwareInterfaceId')}
    expected = deepcopy(before)
    for key, row in changed.items():
        parameters, topology = rename_network(expected, key, row['name'], channels=channels, name_source='generated')
        next(n for n in parameters['networks'] if n['id'] == key).update(name_context=row['name_context'])
        expected.update(parameters=parameters, topology=topology)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = Path(f'backend/runtime/ethernet-names-{stamp}-before.json')
    backup.write_text(json.dumps({'state': before, 'channels': channels}, ensure_ascii=False, indent=2), encoding='utf-8')
    after = api('/workflow/ethernet-names', {'expected_token': before['edit_tokens']['topology'], 'expected_parameters_token': before['edit_tokens']['parameters']})
    assert after['parameters'] == expected['parameters']
    assert after['topology'] == expected['topology']
    for key in ('versions', 'statuses', 'routing'):
        assert after.get(key) == before.get(key), key
    for n in after['topology']['nodes']:
        for p in n['ports']:
            if p.get('hardwareInterfaceId') in channels and p.get('nameSource') == 'network':
                canonical = api('/hardware-interfaces/' + p['hardwareInterfaceId'])
                assert canonical['name'] == p['name']
                assert canonical['network_ref'] == channels[p['hardwareInterfaceId']]['network_ref']
    assert ethernet_names(after['parameters']['networks'], topology=after['topology']) == {n['id']: n for n in after['parameters']['networks']}
    result = {'project': PROJECT, 'backup': str(backup), 'names': [{'id': key, 'before': old_names[key], 'after': row['name']} for key, row in changed.items()],
              'canonicalNamesVerified': True, 'identitiesGeometryRoutingVersionsPreserved': True, 'secondPlanUnchanged': True}
    Path('backend/runtime/ethernet-names-normalized.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    run()
