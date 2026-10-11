"""Continue the existing authorized product wizard; preserve every review gate."""
import json
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

OUT = Path(__file__).parent
PROJECT = '20261006112021387-b7939de0'
BASE = 'http://localhost:13500/api/engineering'
HEADERS = {'X-Project-ID': PROJECT, 'Content-Type': 'application/json'}
with urlopen(Request(BASE+'/workflow?view=summary', headers=HEADERS), timeout=60) as response:
    workflow = json.load(response)
execution = workflow['context']['agent_execution']
assert execution['run_id'] == '8e3e1963-5092-4670-bf50-5cb66ea524de'
assert workflow['artifact_checks']['engineering_model']['complete']
with urlopen(Request(BASE+'/agent/proposals/4dfcaab5-6f2f-409a-ae3e-f8b82b617b03?view=status', headers=HEADERS), timeout=60) as response:
    proposal = json.load(response)['data']
assert proposal['status'] == 'APPLIED' and len(proposal['canonical_ids']) == 2114
payload = {
    'prompt': 'Fortsetzung des bestätigten Wizard-Auftrags nach der übernommenen Modellfreigabe. Ziel: data_science_intelligence.',
    'wizard_command': {
        'action': 'CONTINUE', 'run_id': execution['run_id'],
        'operation_id': str(uuid4()), 'target': 'data_science_intelligence',
        'request_revision': execution['request_revision'],
    },
}
(OUT/'resume-request.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
events = []
with urlopen(Request(BASE+'/agent/chat', data=json.dumps(payload).encode(), headers=HEADERS), timeout=180) as response:
    for raw in response:
        line = raw.decode('utf-8').strip()
        if line.startswith('data:'):
            event = json.loads(line[5:].strip())
            events.append(event)
            if event.get('type') in {'APPROVAL','ERROR'}:
                p = event.get('proposal') or {}
                print(json.dumps({'type': event['type'], 'message': event.get('message'),
                                  'proposal_id': p.get('proposal_id'), 'proposal_type': p.get('proposal_type'),
                                  'changes': len(p.get('changes',[]))}), flush=True)
(OUT/'resume-events.json').write_text(json.dumps(events, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'events':len(events),'types':[e.get('type') for e in events]}))
