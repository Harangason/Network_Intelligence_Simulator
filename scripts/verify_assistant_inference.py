"""One real local-model answer through the running chat/MCP service, in a test project."""
import json
from pathlib import Path
import urllib.request
import http.client
import time
from uuid import uuid4

for attempt in range(20):
    try:
        urllib.request.urlopen('http://127.0.0.1:15050/api/ready', timeout=2).close()
        break
    except (OSError, http.client.HTTPException):
        if attempt == 19:
            raise
        time.sleep(1)

project = 'assistant-inference-' + uuid4().hex[:12]
payload = {
    'prompt': 'Erkläre kurz, wozu Hardware, Funktionen und Signale im Simulator dienen. Bitte nur antworten, nichts anlegen.',
    'context': {'active_project_id': project},
}
request = urllib.request.Request('http://127.0.0.1:15050/api/engineering/agent/chat',
    headers={'X-Project-ID': project, 'Content-Type': 'application/json'}, data=json.dumps(payload).encode())
events = []
with urllib.request.urlopen(request, timeout=240) as response:
    for line in response:
        if line.strip():
            event = json.loads(line)
            events.append(event)
            if event.get('type') in {'RESULT', 'ERROR'}:
                print(json.dumps({key: event.get(key) for key in ('type', 'status', 'text')}, ensure_ascii=True), flush=True)
output = Path(__file__).resolve().parents[1] / 'backend/runtime/assistant-local-inference.json'
output.write_text(json.dumps({'project': project, 'events': events}, ensure_ascii=False, indent=2), encoding='utf-8')
assert any(e.get('type') == 'RESULT' and e.get('status') == 'ANSWERED' for e in events), 'No verified answer'
assert not any(e.get('type') == 'ERROR' for e in events)
