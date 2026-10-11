"""Read progress only from the active gate's own isolated HTTP project."""
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

work = json.loads((Path(__file__).parent / 'workload.json').read_text(encoding='utf-8-sig'))
receipt_path = Path(work['release_recovery']['active_receipt'])
receipt = json.loads(receipt_path.read_text())
report = receipt_path.parent / 'large-http.json'
if report.exists():
    data = json.loads(report.read_text(encoding='utf-8'))
    print(json.dumps({'project': data['project'], 'statuses': data['statuses'],
        'network_scene': data['network_scene'], 'trace_window_count': data['trace_window_count'],
        'http_check_count': len(data['http'])}, ensure_ascii=True))
elif receipt['status'] == 'RUNNING':
    log = receipt_path.parent / 'large-http.log'
    if not log.exists():
        print('Large HTTP acceptance has not started.')
        raise SystemExit(0)
    start = json.loads(log.read_text(encoding='utf-8').splitlines()[0])
    project = start['project']
    base = receipt['base_url']
    assert re.fullmatch(r'astra-e2e-[a-f0-9]{12}', project)
    assert re.fullmatch(r'http://127\.0\.0\.1:\d+', base) and ':13500' not in base
    assert receipt['containers']['app'] == 'nis-e2e-app-' + receipt_path.parent.name
    request = Request(base + '/api/engineering/workflow?view=summary', headers={'X-Project-ID': project})
    with urlopen(request, timeout=20) as response:
        data = json.load(response)
    execution = data.get('context', {}).get('agent_execution', {})
    print(json.dumps({'project': project, 'statuses': data['statuses'], 'execution':
        {key: execution.get(key) for key in ['state', 'step', 'message', 'updated_at']}}, ensure_ascii=True))
else:
    print(json.dumps({'gate_status': receipt['status'], 'error': receipt.get('error')}))
