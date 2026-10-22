"""Read-only actual driver/worker/event observation; never starts inference."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from urllib.request import urlopen

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('case', choices=['vehicle', 'robot'])
args = parser.parse_args()
root = Path.cwd()
phase = root / f'docs/implementation-workloads/reference-example-assumptions-20261017/integration/native-source-binding-{args.case}'
out = Path(__file__).resolve().parent
command = "@(Get-CimInstance Win32_Process | Where-Object {($_.ParentProcessId -eq 47644 -and $_.Name -eq 'llama-server.exe') -or ($_.Name -like 'python*' -and $_.CommandLine -like '*native_original_document_driver.py*')} | Select-Object ProcessId,ParentProcessId,Name,CommandLine,KernelModeTime,UserModeTime) | ConvertTo-Json -Compress"
rows = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command', command], text=True).strip() or '[]')
rows = [rows] if isinstance(rows, dict) else rows
workers = []
for row in rows:
    if row['Name'] != 'llama-server.exe':
        continue
    port = re.search(r'--port\s+(\d+)', row['CommandLine']).group(1)
    try:
        with urlopen('http://127.0.0.1:' + port + '/slots', timeout=5) as response:
            slots = json.load(response)
    except Exception as error:
        slots = {'read_error': str(error)}
    workers.append({'process': row, 'port': port, 'slots': slots})
events = []
event_file = phase / 'plan-reference/events.ndjson'
if event_file.exists():
    for line in event_file.read_text(encoding='utf8').splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass  # A concurrent append may leave the final line incomplete.
latest = {}
for event in events:
    metadata = event.get('metadata') or {}
    if metadata.get('source'):
        latest[metadata['source']] = event
observation = {'at_utc': datetime.now(timezone.utc).isoformat(), 'case': args.case,
    'state': json.loads((phase / 'state.json').read_text(encoding='utf8')),
    'drivers': [row for row in rows if row['Name'] != 'llama-server.exe'],
    'workers': workers, 'event_count': len(events), 'latest_by_source': latest,
    'terminal_events': [event for event in events if event.get('type') == 'RESULT']}
with (out / f'native-{args.case}-worker-observations.ndjson').open('a', encoding='utf8') as stream:
    stream.write(json.dumps(observation, ensure_ascii=False) + '\n')
(out / f'native-{args.case}-worker-latest.json').write_text(json.dumps(observation, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
print(json.dumps({'at_utc': observation['at_utc'], 'state': observation['state']['status'],
    'drivers': [row['ProcessId'] for row in observation['drivers']],
    'workers': [{'pid': row['process']['ProcessId'], 'slots': [
        {key: slot.get(key) for key in ('is_processing', 'id_task', 'n_ctx', 'n_prompt_tokens',
            'n_prompt_tokens_processed', 'n_prompt_tokens_cache', 'next_token')}
        for slot in row['slots']] if isinstance(row['slots'], list) else row['slots']} for row in workers],
    'latest': {source: {key: event.get('metadata', {}).get(key) for key in (
        'completed_calls', 'planning_stage', 'attempt', 'inventory_target', 'scope_index', 'scope_count',
        'draft_inventory_by_kind', 'context_rebased', 'received_characters',
        'validated_calls', 'rejected_calls', 'validation_status', 'validation_error')
        if key in event.get('metadata', {})} for source, event in latest.items()},
    'terminal_events': observation['terminal_events']}, ensure_ascii=False))
