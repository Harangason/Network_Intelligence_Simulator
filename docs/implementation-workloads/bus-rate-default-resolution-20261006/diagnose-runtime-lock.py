"""Filesystem-only replay of the failed crash/retention setup; no database."""
import json
from pathlib import Path
import tempfile
import time
import sys
import subprocess

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from backend.tests import test_runtime_storage as tests
from scripts.test_runtime_storage import cleanup_runtime_dirs, LOCK, MARKER

records = []
launched = []
original_popen = subprocess.Popen
def tracked_popen(*args, **kwargs):
    process = original_popen(*args, **kwargs)
    if args and args[0][0] in (sys.executable, sys._base_executable):
        launched.append(process.pid)
    return process
tests.subprocess.Popen = tracked_popen
def observed(parent, *, now=None):
    result = cleanup_runtime_dirs(parent, now=now)
    records.append({'now': now, 'result': result, 'files': {
        str(path.relative_to(parent)): path.stat().st_mtime
        for path in parent.rglob('*') if path.exists()
    }})
    if len(records) == 1 and index == 0:
        parent_pid = launched[-1]
        command = f'Get-CimInstance Win32_Process | Where-Object {{ $_.ProcessId -eq {parent_pid} -or $_.ParentProcessId -eq {parent_pid} }} | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress'
        records[-1]['running_process_tree'] = subprocess.check_output(['powershell', '-NoProfile', '-Command', command], text=True).strip()
    if len(records) == 2 and result['active']:
        parent_pid = launched[-1]
        command = f'Get-CimInstance Win32_Process | Where-Object {{ $_.ParentProcessId -eq {parent_pid} }} | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress'
        process_info = subprocess.check_output(['powershell', '-NoProfile', '-Command', command], text=True)
        records[-1]['terminated_launcher_pid'] = parent_pid
        records[-1]['surviving_child'] = process_info.strip()
        records[-1]['sys_executable'] = sys.executable
        records[-1]['base_executable'] = sys._base_executable
    return result

tests.cleanup_runtime_dirs = observed
for index in range(100):
    with tempfile.TemporaryDirectory(prefix='nis-lock-replay-') as directory:
        records = []
        try:
            tests.test_active_process_protected_then_crash_releases_lock(Path(directory))
        except AssertionError:
            output = Path(__file__).with_name('runtime-lock-reproduction.json')
            output.write_text(json.dumps({'iteration': index, 'records': records}, indent=2))
            print(output.read_text(), flush=True)
            raise
summary = {'iterations': 100, 'status': 'PASSED', 'base_executable': sys._base_executable}
Path(__file__).with_name('runtime-lock-fixed-replay.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary))
