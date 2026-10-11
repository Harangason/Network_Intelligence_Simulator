"""Pause only authorized EIP workers and restore only pauses owned by this run."""
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
parser = argparse.ArgumentParser()
parser.add_argument('action', choices=['pause', 'resume'])
args = parser.parse_args()
path = HERE / 'authorized-worker-pause.json'
if args.action == 'pause':
    if path.exists():
        previous = json.loads(path.read_text(encoding='utf-8'))
        assert previous['status'] == 'RESTORED', 'Existing pause record must be restored before reuse.'
        archive = HERE / ('worker-pause-history-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.json')
        assert not archive.exists()
        path.rename(archive)
    names = ['eip_scaling-worker-1', 'eip_scaling-worker-2', 'eip_scaling-analysis-worker-1',
             'eip_scaling-simulation-worker-1', 'eip_scaling-agent-worker-1']
    rows = json.loads(subprocess.check_output([docker, 'inspect', *names], text=True))
    report = {'authorization': 'User explicitly approved EIP-Worker vorübergehend pausieren for the next NIS release check; resume after the run, including on failure.',
        'created_at': datetime.now(timezone.utc).isoformat(), 'status': 'PAUSING',
        'workers': [{'id': row['Id'], 'name': row['Name'], 'was_paused': row['State']['Paused'],
                     'was_running': row['State']['Running'], 'paused_by_this_run': False} for row in rows]}
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    for worker in report['workers']:
        if worker['was_running'] and not worker['was_paused']:
            subprocess.run([docker, 'pause', worker['id']], check=True, capture_output=True)
            worker['paused_by_this_run'] = True
            path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    report['status'] = 'PAUSED'
else:
    report = json.loads(path.read_text(encoding='utf-8'))
    for worker in report['workers']:
        if worker['paused_by_this_run']:
            probe = subprocess.run([docker, 'inspect', worker['id']], capture_output=True, text=True)
            if probe.returncode == 0 and json.loads(probe.stdout)[0]['State']['Paused']:
                subprocess.run([docker, 'unpause', worker['id']], check=True, capture_output=True)
            worker['restored'] = True
            path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    report.update(status='RESTORED', restored_at=datetime.now(timezone.utc).isoformat())
path.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({'status': report['status'], 'worker_count': sum(row['paused_by_this_run'] for row in report['workers'])}))
