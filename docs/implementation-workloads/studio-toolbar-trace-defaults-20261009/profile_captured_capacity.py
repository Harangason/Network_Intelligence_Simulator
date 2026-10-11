"""Profile the real calculation using captured inputs, with no database access."""
import cProfile
import json
import os
import pstats
import sys
import time
from pathlib import Path
from unittest.mock import patch

folder = Path(__file__).resolve().parent
root = folder.parents[2]
sys.path.insert(0, str(root))
os.environ['NUMERIC_ACCELERATOR'] = 'cpu'
from backend.nis.engineering.capacity import service

state = json.loads((folder / 'large-workflow-captured.json').read_text())
state['topology'] = json.loads((folder / 'large-topology-captured.json').read_text())['topology']
state['parameters'] = json.loads((folder / 'large-parameters-captured.json').read_text())['parameters']
names = {'Message': 'messages', 'Signal': 'signals', 'Interface': 'interfaces',
         'HardwareNode': 'hardware-nodes', 'HardwareNetworkInterface': 'hardware-interfaces',
         'routes': 'routing'}
rows = {key: json.loads((folder / ('large-' + value + '-objects.json')).read_text()) for key, value in names.items()}
print(json.dumps({'captured_objects': {key: len(value) for key, value in rows.items()}}), flush=True)

class CapturedWorkflow:
    def get(self):
        return state

    def create_analysis_snapshot(self, *args, **kwargs):
        return {'id': 'offline-profile', 'source_versions': state['versions']}

def pages(function, kind=None):
    return rows[kind or 'routes']

calculator = object.__new__(service.CapacityTimingService)
calculator.workflow = CapturedWorkflow()
profile = cProfile.Profile()
start = time.perf_counter()
with patch.object(service, 'all_pages', pages):
    result = profile.runcall(calculator.calculate)
elapsed = time.perf_counter() - start
profile.dump_stats(str(folder / 'capacity-before.prof'))
with (folder / 'capacity-before-profile.txt').open('w') as stream:
    pstats.Stats(profile, stream=stream).sort_stats('cumulative').print_stats(40)
summary = {'elapsed_seconds': elapsed, 'status': result['status'], 'overview': result['results']['overview']}
(folder / 'capacity-before-result.json').write_text(json.dumps(result), encoding='utf-8')
print(json.dumps(summary), flush=True)
print((folder / 'capacity-before-profile.txt').read_text())
