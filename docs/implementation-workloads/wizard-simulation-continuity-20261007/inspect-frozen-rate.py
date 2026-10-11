import json
from pathlib import Path
from urllib.request import Request, urlopen

out = Path(__file__).parent
project = 'nis-e2e-small-585d9a49-c866-4211-90e4-c0fb0e1f40f1'
def read(path):
    with urlopen(Request('http://127.0.0.1:61671'+path,headers={'X-Project-ID':project}),timeout=20) as response:
        return json.load(response)
parameters = read('/api/engineering/workflow/parameters')['parameters']
snapshots = read('/api/engineering/workflow/snapshots')['simulations']
snapshot = read('/api/engineering/workflow/simulation-snapshots/'+snapshots[0]['id'])
keys = ['technology','seed','bitrate','arbitration_bitrate','data_bitrate','can_fd_data_prescaler']
result = {'saved_parameters': {key:parameters.get(key) for key in keys},
    'saved_can_fd_group':(parameters.get('technology_parameters') or {}).get('can_fd'),
    'saved_can_fd_assumptions':(parameters.get('simulation_parameter_assumptions') or {}).get('can_fd'),
    'frozen_parameters':snapshot['configuration']['parameters'],
    'frozen_networks': snapshot['configuration']['networks']}
(out/'frozen-rate-observation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'saved_parameters':result['saved_parameters'],
    'frozen_parameters':result['frozen_parameters'],
    'frozen_network_rates':[{key:row.get(key) for key in ['id','technology','bitrate','arbitration_bitrate','data_bitrate','can_fd_data_prescaler']} for row in result['frozen_networks']]},indent=2))
