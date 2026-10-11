import hashlib, json, sys
from pathlib import Path
from urllib.request import Request, urlopen

out = Path(__file__).parent
project = '20261007041943709-40764014'
proposal = 'aa7c0504-1cf4-4d09-b2e8-6ce28f8a2b49'
def read(path):
    request = Request('http://127.0.0.1:13500'+path, headers={'X-Project-ID':project})
    with urlopen(request, timeout=60) as response:
        return json.load(response)
state = read('/api/engineering/workflow?view=summary')
parameters = read('/api/engineering/workflow/parameters')['parameters']
review = read('/api/engineering/agent/proposals/'+proposal+'?view=status')['data']
result = {
    'project':project, 'proposal':proposal,
    'run_id':(state.get('context', {}).get('agent_wizard_status') or {}).get('run_id'),
    'parameter_sha256':hashlib.sha256(json.dumps(parameters,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
    'parameter_count':len(parameters),
    'saved_scenario_technologies':sorted((parameters.get('simulation_parameter_assumptions') or {}).keys()),
    'proposal_status':review['status'], 'canonical_count':len(review.get('canonical_ids') or []),
    'build':read('/api/build-info'), 'health':read('/api/ready'),
}
phase = sys.argv[1]
if phase != 'before':
    before = json.loads((out/'live-before.json').read_text(encoding='utf-8'))
    for key in ('project','proposal','run_id','parameter_sha256','saved_scenario_technologies','canonical_count'):
        assert result[key] == before[key], (key, before[key], result[key])
    findings = read('/api/engineering/workflow/parameters/review?proposal='+proposal)['findings']
    device = [row for row in findings if row.get('code') == 'CAPACITY_DEVICE_EVIDENCE_MISSING']
    assert device and all(row['severity'] == 'INFO' and row['simulation_parameters_usable'] for row in device)
    result['device_hints'] = len(device)
    result['device_hint_severities'] = sorted({row['severity'] for row in device})
(out/('live-'+phase+'.json')).write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({key:value for key,value in result.items() if key not in {'build','health'}},ensure_ascii=False))
