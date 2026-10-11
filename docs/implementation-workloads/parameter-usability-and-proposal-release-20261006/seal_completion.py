"""Seal this repair only after release, delivery and durable product evidence exist."""
import argparse
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).parent
ROOT = OUT.parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--receipt', type=Path, required=True)
args = parser.parse_args()

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

receipt = read(args.receipt)
assert receipt['status'] == 'PASS'
assert all(c['exit_code'] == 0 for c in receipt['checks'])
deliveries = [json.loads(line) for line in (OUT/'deployment.log').read_text(encoding='utf-8-sig').splitlines()
              if line.startswith('{"status": "DEPLOYED"')]
assert len(deliveries) == 1
delivery = deliveries[0]
product = read(OUT/'production-applied.json')
assert receipt['image_id'] == delivery['image_id']
assert receipt['release']['source_sha256'] == delivery['source_sha256'] == product['build']['source_sha256']
assert product['ready']['status'] == 'ready'
assert product['proposal_status'] == 'APPLIED'
assert product['canonical_id_count'] == len(read(OUT/'proposal-before.json')['data']['changes'])
assert product['counts'] == {'functions': 71, 'hardware_interfaces': 343,
                            'hardware_nodes': 251, 'interfaces': 335,
                            'messages': 323, 'signals': 698}
assert product['parameter_storage']['filename'] == 'user_defined_values.json'
assert product['parameter_storage']['source'] == 'PROJECT_USER_DEFINED_VALUES'
parameters = read(OUT/'parameters-applied.json')['parameters']
user_document = read(OUT/'user-values-applied.json')
assert user_document['value_origin'] == 'USER_DEFINED_VALUE'
for technology, rates in {
    'lin': {'lin_bitrate_bps': 19200},
    'can_fd': {'arbitration_bitrate': 500000, 'data_bitrate': 2000000},
    'ethernet': {'bitrate': 1000000000},
}.items():
    group = parameters['simulation_parameter_assumptions'][technology]
    persisted = user_document['parameters']['simulation_parameter_assumptions'][technology]
    for key, value in rates.items():
        assert group['values'][key] == persisted['values'][key] == value
        assert group['provenance'][key]['hardware_evidence'] is False
    for key, value in group['values'].items():
        if key.endswith(('_source', '_revision', '_node_id', '_ref')):
            assert value != f'simulation:{technology}:{key}'
before_parameters = read(OUT/'parameters-before.json')['parameters']
for technology, group in before_parameters['technology_parameters'].items():
    for key, value in group['values'].items():
        assert parameters['technology_parameters'][technology]['values'].get(key) == value
ui = read(OUT/'production-ui.json')
assert ui['save_verified'] and ui['review_apply_verified'] and ui['reload_verified']
assert ui['common_parameters_first'] and ui['editable_details_collapsed']
assert ui['project'] == product['project']
assert ui['wizard_model_complete'] and ui['routing_review_count'] == 523
assert (OUT/'production-parameters.png').stat().st_size > 1000

release_refs = [ref(args.receipt), ref(args.receipt.parent/'browser-e2e.log')]
product_refs = [ref(OUT/'production-applied.json'), ref(OUT/'parameters-applied.json'),
                ref(OUT/'proposal-applied.json'), ref(OUT/'workflow-applied.json'),
                ref(OUT/'user-values-applied.json'), ref(OUT/'production-ui.json'),
                ref(OUT/'production-parameters.png')]
deployment_refs = [ref(OUT/'deployment.log')]
work = read(OUT/'workload.json')
work['outcomes'] = {name: {'status': 'PASSED', 'evidence': product_refs + release_refs}
                    for name in work['required_outcomes']}
work['validations'] = {
    'targeted_regression': {'status': 'PASSED', 'evidence': [ref(OUT/'final-targeted-backend.log'), ref(OUT/'targeted-frontend.log')]},
    'full_release_gate': {'status': 'PASSED', 'evidence': release_refs},
    'production_verification': {'status': 'PASSED', 'evidence': product_refs + deployment_refs},
}
work['delivery'] = {
    'decision': 'YES',
    'authorization': 'User AGENTS.md standing authorization for verified production delivery',
    'target': 'Canonical NetworkIS production stack on port 13500',
    'tested_version': receipt['image_id'],
    'running_version': delivery['image_id'],
    'checks': {name: {'status': 'PASSED', 'evidence': refs} for name, refs in {
        'release': release_refs, 'deployment': deployment_refs,
        'health': [ref(OUT/'ready-applied.json'), ref(OUT/'build-applied.json')],
        'functional': product_refs,
    }.items()},
}
work.update(completion_status='COMPLETED', remaining_findings=[])
work['completion_scope'] = 'Requested software repair and durable original model apply. User project remains at the next routing human-review gate; hardware qualification is separate.'
work['project_workflow_remaining'] = ['523 validated routing entries awaiting human review',
                                      '300 provenance-aware connection findings; simulation assumptions are not hardware evidence']
(OUT/'workload.json').write_text(json.dumps(work, indent=2), encoding='utf-8')
print(json.dumps({'status': 'SEALED', 'image': delivery['image_id'], 'canonical_ids': product['canonical_id_count']}))
