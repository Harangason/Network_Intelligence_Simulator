import json
from collections import Counter
from pathlib import Path
from backend.nis.agent.tools import validation

OUT = Path(__file__).parent
parameters = json.loads((OUT/'before-live/parameters.json').read_text())['parameters']
changes = json.loads((OUT/'before-live/proposal.json').read_text())['data']['changes']
validation.objects = lambda kind: []
state = {'parameters': parameters}
checks = validation.review_simulation_capacity(state, changes)
findings = validation.review_parameter_findings(state, changes)
(OUT/'diagnosis-current.json').write_text(json.dumps({'simulation_capacity': checks, 'findings': findings}, indent=2), encoding='utf-8')
print('scenario', dict(Counter(row['status'] for row in checks)))
print('findings', dict(Counter(row['code'] for row in findings)))
print('invalid examples', [(row['technology'], row['reason'][:350]) for row in checks if row['status']=='INVALID'][:4])
print('rate flagged', Counter(row['technology'] for row in findings if any('bitrate' in key for key in row.get('parameter_fields', []))))
