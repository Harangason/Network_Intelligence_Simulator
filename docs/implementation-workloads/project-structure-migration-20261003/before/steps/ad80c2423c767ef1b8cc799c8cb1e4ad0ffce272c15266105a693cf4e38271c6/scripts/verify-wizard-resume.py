"""Verify a completed wizard after server restart using its persisted request."""
import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser()
parser.add_argument('--report', type=Path, required=True)
args = parser.parse_args()
original = json.loads(args.report.read_text(encoding='utf-8'))
base = 'http://127.0.0.1:13500'
headers = {'X-Project-ID': original['project'], 'Content-Type': 'application/json'}

def request(path, payload=None, stream=False):
    req = Request(base + path, headers=headers,
                  data=None if payload is None else json.dumps(payload).encode())
    with urlopen(req, timeout=180) as response:
        return [json.loads(line) for line in response if line.strip()] if stream else json.load(response)

state = request('/api/engineering/workflow?view=summary')
assert state['statuses'] == original['statuses'], state['statuses']
prompt = state['context']['wizard_request']['prompt']
assert prompt and 'Systemcluster-Graph:' in prompt
before = {job['id'] for job in request('/api/simulations')['jobs']}
events = request('/api/engineering/agent/chat', {
    'prompt': prompt + '\nFortsetzung des bestätigten Wizard-Auftrags: Ziel: data_science_intelligence.'}, stream=True)
assert any(event.get('type') == 'RESULT' and event.get('status') == 'COMPLETED' for event in events)
assert not any(event.get('type') == 'APPROVAL' for event in events)
after = {job['id'] for job in request('/api/simulations')['jobs']}
assert before == after and original['job_id'] in after
result = {'project': original['project'], 'persisted_request': True,
          'same_statuses': True, 'same_jobs': sorted(after), 'duplicate_review': False, 'status': 'PASS'}
args.report.with_name(args.report.stem + '-resume.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result))
