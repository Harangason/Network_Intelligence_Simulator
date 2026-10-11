"""Read-only production evidence; never creates a project or writes its data."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PROJECT = '20261001074307177-35f4bcb9'
DOCKER = r'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
BASE = 'http://127.0.0.1:13500'

def request(path, payload=None, base=BASE):
    headers = {'X-Project-ID': PROJECT, 'Content-Type': 'application/json'}
    req = Request(base + path, headers=headers,
                  data=None if payload is None else json.dumps(payload).encode())
    try:
        with urlopen(req, timeout=60) as response:
            return response.status, json.load(response)
    except HTTPError as response:
        return response.code, json.load(response)

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def docker(*command):
    return subprocess.check_output([DOCKER, *command], text=True, encoding='utf-8').strip()

def facts():
    _, ready = request('/api/ready')
    _, build = request('/api/build-info')
    _, document = request('/api/engineering/workflow/parameters')
    mounts = {name: [{key: item.get(key) for key in ('Type', 'Name', 'Source', 'Destination')}
                     for item in json.loads(docker('inspect', name, '--format', '{{json .Mounts}}'))]
              for name in ('NetworkIS', 'NetworkIS-db')}
    return {'project_id': PROJECT, 'ready': ready, 'build': build, 'data_mounts': mounts,
            'running_image': docker('inspect', 'NetworkIS', '--format', '{{.Image}}'),
            'parameter_sha256': digest(document['parameters']),
            'historical_images': sorted(set(docker('image', 'ls', 'networkis', '--no-trunc',
                                                  '--format', '{{.ID}}').splitlines()))}

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--baseline', action='store_true')
    p.add_argument('--receipt', type=Path)
    args = p.parse_args()
    baseline_path = ROOT / 'work/parameter-production-before.json'
    if args.baseline:
        before = facts()
        baseline_path.write_text(json.dumps(before, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'baseline_saved': True, 'image': before['running_image'],
                          'project_id': PROJECT, 'historical_images': len(before['historical_images'])}))
        return
    assert args.receipt, 'An exact PASS receipt is required.'
    receipt = json.loads(args.receipt.read_text(encoding='utf-8'))
    assert receipt['status'] == 'PASS'
    before = json.loads(baseline_path.read_text(encoding='utf-8'))
    current = facts()
    assert current['ready']['status'] == 'ready'
    assert current['running_image'] == receipt['image_id']
    assert current['build']['source_sha256'] == receipt['release']['source_sha256']
    assert current['build']['commit_id'] == receipt['release']['commit_id']
    assert current['parameter_sha256'] == before['parameter_sha256'], 'Existing project parameters changed.'
    assert current['data_mounts'] == before['data_mounts'], 'Product data mounts changed.'
    assert set(before['historical_images']) <= set(current['historical_images']), 'Historical image disappeared.'
    _, catalog = request('/api/technologies')
    profiles = {profile['id']: profile for domain in catalog['domains'] for profile in domain['technologies']}
    assert len(profiles) == catalog['technology_count'] == 125
    expected_counts = {'MODEL_AVAILABLE': 6, 'MODEL_MISSING': 115, 'NOT_APPLICABLE': 4}
    counts = dict(Counter(profile['capacity_evidence']['status'] for profile in profiles.values()))
    assert counts == expected_counts
    defaults = {field['key']: field.get('default') for field in profiles['i2c']['parameter_schema']}
    assert defaults['bitrate'] == 100_000
    assert not {'duplex', 'mtu_bytes'}.intersection(field['key'] for field in profiles['nmea2000']['parameter_schema'])
    validations = []
    for technology, values, expected in (
        ('can', {'bitrate_bps': 500_000}, 'VALID'),
        ('can_fd', {'nominal_bitrate_bps': 500_000, 'data_bitrate_bps': 2_000_000}, 'VALID'),
        ('can', {'bitrate': 250_000, 'bitrate_bps': 500_000}, 'INVALID'),
        ('lin', {'bitrate': 2_000_000}, 'INVALID'),
        ('i2c', {'bitrate_bps': 100_000}, 'UNVERIFIED'),
        ('nmea2000', {'bitrate_bps': 100_000_000, 'duplex': 'FULL'}, 'INVALID'),
    ):
        code, result = request('/api/technologies/validate-parameters', {'technology': technology, 'parameters': values})
        assert result['status'] == expected, result
        assert code == (422 if expected == 'INVALID' else 200)
        validations.append({'technology': technology, 'inputs': values, 'status': result['status'],
                            'codes': sorted({row['code'] for row in result['findings']})})
    code = "from backend.engineering.agent_tools.project_draft import parse_requirement; import json; d=parse_requirement('ein Aktor zum proportional schließen eines Ventil', industry='custom'); a=[x for x in d['devices'] if x['role']=='ACTUATOR']; assert len(a)==1 and a[0]['known_kind']; print(json.dumps({'actuators':len(a),'name':a[0]['name'],'known_kind':a[0]['known_kind']}))"
    actuator = json.loads(docker('exec', 'NetworkIS', 'python', '-c', code).splitlines()[-1])
    _, lan_ready = request('/api/ready', base='http://192.168.178.10:13500')
    assert lan_ready['status'] == 'ready'
    report = {**current, 'status': 'PASSED', 'receipt': str(args.receipt.resolve()),
              'catalog': {'profiles': 125, 'capacity_models': counts, 'i2c_standard_clock': defaults['bitrate']},
              'read_only_parameter_checks': validations, 'actuator': actuator,
              'existing_project_parameters_preserved': True, 'data_mounts_preserved': True, 'historical_images_preserved': True,
              'lan_ready': lan_ready, 'scope': 'Read-only live API and image checks; pure parser in running image. Actual nine-stage E2E is in the isolated PASS receipt.'}
    output = ROOT / 'work/parameter-production-verification.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'PASSED', 'image': current['running_image'], 'project_id': PROJECT,
                      'catalog_profiles': 125, 'report': str(output)}))

if __name__ == '__main__':
    main()
