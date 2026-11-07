"""Restore only the reviewed production launcher at its reviewed job boundary.

Operational fail-safe, not an app change or an inference scheduler. This helper
never stops anything, never starts a model, and never addresses another stack.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen

OUT = Path(__file__).resolve().parent
DOCKER = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
PLAN = json.loads((OUT / 'reviewed-plan.json').read_text(encoding='utf8'))
BINDING_PATH = OUT / 'native-process-binding.json'
BINDING = json.loads(BINDING_PATH.read_text(encoding='utf8')) if BINDING_PATH.exists() else None


def bound_native_processes_alive():
    expected = BINDING['processes']
    assert expected and all(isinstance(row['ProcessId'], int) for row in expected)
    predicate = ' OR '.join('ProcessId=' + str(row['ProcessId']) for row in expected)
    command = ("@(Get-CimInstance Win32_Process -Filter '" + predicate +
        "' | Select-Object ProcessId,@{n='CreatedUtc';e={$_.CreationDate.ToUniversalTime().ToString('o')}},CommandLine) | ConvertTo-Json -Compress")
    rows = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command', command],
        text=True, timeout=15).strip() or '[]')
    rows = [rows] if isinstance(rows, dict) else rows
    return sorted(rows, key=lambda row: row['ProcessId']) == sorted(expected, key=lambda row: row['ProcessId'])


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf8')


def actual():
    value = json.loads(subprocess.check_output([DOCKER, 'inspect', 'NetworkIS'], timeout=15))[0]
    if (value['Id'] != PLAN['exact_container_id'] or
            value['Image'] != PLAN['exact_image_id']):
        return value, None
    status = subprocess.check_output([DOCKER, 'exec', 'NetworkIS', 'python', '-c',
        "from pathlib import Path; print(next(x for x in Path('/proc/1/status').read_text().splitlines() if x.startswith('State:')))"],
        text=True, timeout=15).strip()
    return value, status


def restore(reason):
    value, state = actual()
    if state and state.split(':', 1)[1].strip().startswith('T'):
        subprocess.run([DOCKER, 'kill', '--signal=SIGCONT', value['Id']],
                       check=True, capture_output=True, timeout=15)
        _, after = actual()
        assert after and not after.split(':', 1)[1].strip().startswith('T'), after
        write('guard-restored.json', {'at_utc': datetime.now(timezone.utc).isoformat(),
            'reason': reason, 'container_id': value['Id'], 'image_id': value['Image'],
            'signal': 'SIGCONT', 'before_state': state, 'after_state': after})


try:
    while True:
        value, state = actual()
        if state is None or not state.split(':', 1)[1].strip().startswith('T'):
            write('guard-ended.json', {'at_utc': datetime.now(timezone.utc).isoformat(),
                'reason': 'Reviewed launcher already resumed or container identity changed.',
                'no_signal_sent': True})
            break
        now = datetime.now(timezone.utc)
        try:
            if BINDING is not None:
                assert BINDING['container_id'] == PLAN['exact_container_id']
                assert BINDING['image_id'] == PLAN['exact_image_id']
                assert bound_native_processes_alive(), 'Exact bound native driver ended or identity changed.'
                remaining = None
            else:
                lease = json.loads((OUT / 'lease.json').read_text(encoding='utf8'))
                remaining = (datetime.fromisoformat(lease['expires_at_utc']) - now).total_seconds()
                assert lease['container_id'] == PLAN['exact_container_id']
                assert lease['image_id'] == PLAN['exact_image_id']
                assert 0 < remaining <= 180
            with urlopen('http://127.0.0.1:13500/api/ready', timeout=5) as response:
                ready = json.load(response)
            assert ready.get('status') == 'ready'
        except (AssertionError, ValueError, OSError, KeyError) as error:
            restore('Bound driver ended, lease invalid, or readiness failed: ' + str(error))
            break
        write('guard-current.json', {'at_utc': now.isoformat(), 'status': 'ARMED',
            'container_id': value['Id'], 'image_id': value['Image'],
            'lease_seconds_remaining': remaining,
            'boundary': 'exact native PID/creation/command identity' if BINDING else 'short observation lease',
            'native_session': BINDING.get('native_session') if BINDING else None, 'ready': ready})
        time.sleep(15)
except BaseException:
    restore('Guard interrupted or failed.')
    raise
