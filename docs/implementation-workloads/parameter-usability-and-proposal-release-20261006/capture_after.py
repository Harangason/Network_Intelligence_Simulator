"""Read-only delivery evidence from normal product HTTP APIs; never SQL tests."""
import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

OUT = Path(__file__).parent
PROJECT = '20261006112021387-b7939de0'
PROPOSAL = '4dfcaab5-6f2f-409a-ae3e-f8b82b617b03'
parser = argparse.ArgumentParser()
parser.add_argument('--phase', choices=['deployed', 'applied'], required=True)
args = parser.parse_args()
values = {}
for name, path in {
    'ready': '/api/ready',
    'build': '/api/build-info',
    'parameters': '/api/engineering/workflow/parameters',
    'user-values': '/api/engineering/workflow/parameters/user-defined-values',
    'proposal': f'/api/engineering/agent/proposals/{PROPOSAL}?view=status',
    'workflow': '/api/engineering/workflow?view=summary',
    'parameter-review': f'/api/engineering/workflow/parameters/review?proposal={PROPOSAL}',
}.items():
    with urlopen(Request('http://localhost:13500' + path,
                         headers={'X-Project-ID': PROJECT}), timeout=120) as response:
        values[name] = json.load(response)
    (OUT / f'{name}-{args.phase}.json').write_text(
        json.dumps(values[name], indent=2, ensure_ascii=False), encoding='utf-8')
proposal = values['proposal'].get('data', values['proposal'])
summary = {
    'phase': args.phase,
    'project': PROJECT,
    'proposal': PROPOSAL,
    'ready': values['ready'],
    'build': values['build'],
    'proposal_status': proposal.get('status'),
    'canonical_id_count': len(proposal.get('canonical_ids', [])),
    'counts': values['workflow'].get('artifact_checks', {}).get('engineering_model', {}).get('counts'),
    'parameter_storage': values['parameters'].get('parameter_storage'),
    'review_source': values['parameter-review'].get('source'),
}
(OUT / f'production-{args.phase}.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps(summary))
