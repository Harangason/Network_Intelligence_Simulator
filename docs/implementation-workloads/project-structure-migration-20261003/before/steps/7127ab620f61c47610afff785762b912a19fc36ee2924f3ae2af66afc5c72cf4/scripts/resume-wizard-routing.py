"""Resume a blocked routing generation; never review or apply its routes."""
import argparse
import json
from urllib.request import Request, urlopen
parser = argparse.ArgumentParser()
parser.add_argument('--project', required=True)
args = parser.parse_args()
base = 'http://127.0.0.1:13500'
headers = {'X-Project-ID': args.project, 'Content-Type': 'application/json'}
with urlopen(Request(base + '/api/engineering/workflow?view=summary', headers=headers), timeout=60) as response:
    state = json.load(response)
execution = state['context']['agent_execution']
assert execution['step'] == 'routing' and execution['state'] == 'BLOCKED', execution
prompt = state['context']['agent_wizard_status']['agent_prompt']
prompt += '\nFortsetzung des bestätigten Wizard-Auftrags: Ziel: data_science_intelligence.'
with urlopen(Request(base + '/api/engineering/agent/chat', headers=headers,
    data=json.dumps({'prompt': prompt}).encode()), timeout=180) as response:
    events = [json.loads(line) for line in response if line.strip()]
report = [{'type': event['type'], 'status': event.get('status'), 'text': event.get('text'),
    'proposal': {key: event['proposal'].get(key) for key in ['proposal_id', 'status', 'proposal_type']}
        if event.get('proposal') else None}
    for event in events if event.get('type') in {'RESULT', 'APPROVAL'}]
print(json.dumps(report, ensure_ascii=False))
assert any(item['status'] == 'READY_FOR_REVIEW' for item in report), report
