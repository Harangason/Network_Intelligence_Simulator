"""User-authorized temporary pause; preserve exact worker IDs for restoration."""
import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('action', choices=['pause', 'add-worker', 'resume'])
args = parser.parse_args()
root = Path(__file__).resolve().parent
record = root / 'eip-pause-state.json'
docker = json.loads(Path('config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']

def inspect(identity):
    raw = json.loads(subprocess.check_output([docker, 'inspect', identity], text=True))[0]
    labels = raw.get('Config', {}).get('Labels', {})
    return {'id': raw['Id'], 'name': raw['Name'].lstrip('/'),
            'running': raw['State']['Running'], 'paused': raw['State']['Paused'],
            'compose_project': labels.get('com.docker.compose.project'),
            'compose_service': labels.get('com.docker.compose.service')}

def save(data):
    record.write_text(json.dumps(data, indent=2), encoding='utf-8')

if args.action == 'pause':
    if record.exists():
        previous = json.loads(record.read_text(encoding='utf-8'))
        assert not previous.get('paused_ids'), 'Restore the previous pause first.'
    names = ['eip_scaling-agent-worker-1', 'eip_scaling-worker-2']
    before = [inspect(name) for name in names]
    assert all(item['compose_project'] == 'eip_scaling' for item in before)
    assert before[0]['compose_service'] == 'agent-worker'
    assert before[1]['compose_service'] == 'worker'
    data = {'authorization': 'Explicit human approval in this chat on 2026-10-09',
            'started_at': datetime.now(timezone.utc).isoformat(), 'before': before, 'paused_ids': []}
    save(data)
    try:
        for item in before:
            if item['running'] and not item['paused']:
                subprocess.run([docker, 'pause', item['id']], check=True, capture_output=True)
                data['paused_ids'].append(item['id'])
                save(data)
        data['after_pause'] = [inspect(item['id']) for item in before]
        save(data)
    except BaseException:
        for identity in data['paused_ids'][:]:
            subprocess.run([docker, 'unpause', identity], check=True, capture_output=True)
            data['paused_ids'].remove(identity)
            save(data)
        raise
    print(json.dumps(data))
elif args.action == 'add-worker':
    data = json.loads(record.read_text(encoding='utf-8'))
    item = inspect('eip_scaling-worker-1')
    assert item['compose_project'] == 'eip_scaling' and item['compose_service'] == 'worker'
    if item['id'] not in {before['id'] for before in data['before']}:
        data['before'].append(item)
        save(data)
    if item['running'] and not item['paused']:
        subprocess.run([docker, 'pause', item['id']], check=True, capture_output=True)
        data['paused_ids'].append(item['id'])
        save(data)
    data['after_pause'] = [inspect(before['id']) for before in data['before']]
    save(data)
    print(json.dumps(data))
else:
    data = json.loads(record.read_text(encoding='utf-8'))
    for before in data['before']:
        identity = before['id']
        current = inspect(identity)
        assert current['compose_project'] == 'eip_scaling'
        if current['paused'] and not before['paused']:
            subprocess.run([docker, 'unpause', identity], check=True, capture_output=True)
        if identity in data['paused_ids']:
            data['paused_ids'].remove(identity)
        save(data)
    data['restored_at'] = datetime.now(timezone.utc).isoformat()
    data['after_resume'] = [inspect(item['id']) for item in data['before']]
    assert all(after['paused'] == before['paused'] for before, after in zip(data['before'], data['after_resume']))
    save(data)
    print(json.dumps(data))
