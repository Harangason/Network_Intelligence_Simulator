"""Apply authorized missing project defaults only after exact-image delivery."""
import hashlib
import json
from collections import Counter
from pathlib import Path
import subprocess
from urllib.request import Request, urlopen

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
RECEIPT = Path((OUT / 'final-receipt.txt').read_text(encoding='utf-8').strip())
PROJECT = '20261005103106027-d3a78a2c'
DOCKER = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'

def request(path, body=None):
    headers = {'X-Project-ID': PROJECT}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers['Content-Type'] = 'application/json'
    with urlopen(Request('http://127.0.0.1:13500' + path, data=data, headers=headers), timeout=300) as response:
        return json.load(response)

def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

receipt = json.loads(RECEIPT.read_text(encoding='utf-8'))
assert receipt['status'] == 'PASS'
assert all(check['exit_code'] == 0 for check in receipt['checks'])
running = subprocess.check_output([DOCKER, 'inspect', 'NetworkIS', '--format', '{{.Image}}'], text=True).strip()
ready = request('/api/ready')
build = request('/api/build-info')
assert running == receipt['image_id']
assert ready['status'] == 'ready'
assert build['source_sha256'] == receipt['release']['source_sha256']
before = request('/api/engineering/workflow/parameters')
catalog_before = request('/api/technologies')
write('production-parameters-before-default-save.json', before)
request('/api/engineering/workflow/parameters/defaults', {
    'expected_token': before['edit_token'], 'technologies': ['lin', 'can_fd', 'ethernet'],
})
after = request('/api/engineering/workflow/parameters')
review = request('/api/engineering/workflow/parameters/review')
stored = request('/api/engineering/workflow/parameters/user-defined-values')
catalog_after = request('/api/technologies')
assert catalog_before == catalog_after, 'Project default save modified the central technology catalog'
write('production-parameters-after.json', after)
write('production-review.json', review)
write('production-user-defined-values.json', stored)
old_parameters = before['parameters']
new_parameters = after['parameters']
for key, value in old_parameters.items():
    if key != 'simulation_parameter_assumptions':
        assert new_parameters[key] == value, f'Existing project value changed: {key}'
for technology, group in old_parameters.get('simulation_parameter_assumptions', {}).items():
    new_group = new_parameters['simulation_parameter_assumptions'][technology]
    for key, value in group.get('values', {}).items():
        assert new_group['values'][key] == value, f'Existing assumption changed: {technology}.{key}'
    for key, value in group.get('provenance', {}).items():
        assert new_group['provenance'][key] == value, f'Existing provenance changed: {technology}.{key}'
assumptions = new_parameters['simulation_parameter_assumptions']
assert assumptions['ethernet']['values']['bitrate'] == 1000000000
assert assumptions['ethernet']['provenance']['bitrate']['hardware_evidence'] is False
assert new_parameters['technology_parameters']['can_fd']['values']['can_fd_brs'] is False
assert new_parameters['networks'] == old_parameters['networks']
assert after['parameter_storage']['source'] == 'PROJECT_USER_DEFINED_VALUES'
assert after['parameter_storage']['filename'] == 'user_defined_values.json'
assert stored['parameters']['simulation_parameter_assumptions'] == new_parameters['simulation_parameter_assumptions']
assert stored['parameters']['technology_parameters'] == new_parameters['technology_parameters']
assert review['source'] == 'CURRENT_CANONICAL_MODEL'
assert review['project_id'] == after['project_id']
assert review['edit_token'] == after['edit_token']
plans = review['bus_rate_plans']
assert plans, 'Project capacity proposals are missing'
assert all(plan['hardware_evidence'] is False for plan in plans)
assert all(plan['functional_timing_accepted'] is False for plan in plans)
summary = {
    'status': 'PASSED', 'receipt': str(RECEIPT), 'running_image': running,
    'source_sha256': build['source_sha256'], 'ready': ready,
    'project_id': after['project_id'], 'parameter_storage': after['parameter_storage'],
    'existing_values_preserved': True, 'existing_assumptions_preserved': True,
    'central_catalog_unchanged': True, 'central_catalog_sha256': digest(catalog_after),
    'network_values_preserved': True, 'explicit_can_brs_false_preserved': True,
    'ethernet_missing_rate_saved': 1000000000,
    'parameters_before_sha256': digest(old_parameters), 'parameters_after_sha256': digest(new_parameters),
    'rate_plan_count': len(plans),
    'rate_plan_statuses': dict(Counter(plan['status'] for plan in plans)),
    'rate_plan_technologies': dict(Counter(plan['technology'] for plan in plans)),
    'finding_count': len(review['findings']),
}
write('production-verification.json', summary)
print(json.dumps(summary, ensure_ascii=False, indent=2))
