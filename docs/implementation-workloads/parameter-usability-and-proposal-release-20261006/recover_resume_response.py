"""Recover the same idempotent wizard operation; never dispatch a new command."""
import json
from pathlib import Path
from urllib.request import Request, urlopen

OUT = Path(__file__).parent
payload = json.loads((OUT/'resume-request.json').read_text())
events = []
with urlopen(Request('http://localhost:13500/api/engineering/agent/chat',
                     data=json.dumps(payload).encode(), headers={'X-Project-ID':'20261006112021387-b7939de0',
                     'Content-Type':'application/json'}), timeout=180) as response:
    for raw in response:
        line = raw.decode().strip()
        if line:
            event = json.loads(line[5:].strip() if line.startswith('data:') else line)
            events.append(event)
            p = event.get('proposal') or {}
            print(json.dumps({'type':event.get('type'), 'message':event.get('message'),
                              'proposal_id':p.get('proposal_id'), 'proposal_type':p.get('proposal_type'),
                              'changes':len(p.get('changes',[])), 'receipt':event.get('wizard_receipt')}), flush=True)
(OUT/'resume-events-recovered.json').write_text(json.dumps(events,indent=2,ensure_ascii=False), encoding='utf-8')
