"""Finite cleanup for this owned release process, including an interrupted chat."""
import ctypes, json, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
receipt_path = ROOT / 'backend/test-output/release-gates/delivery-f87cc6f48f53/ba52fd62fb41/receipt.json'
pause_path = HERE / 'authorized-worker-pause.json'
original = json.loads(pause_path.read_text(encoding='utf-8'))
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
assert receipt['gate_pid'] == 13888 and receipt['status'] == 'RUNNING'
assert original['status'] == 'PAUSED'
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
kernel.OpenProcess.restype = ctypes.c_void_p
kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
kernel.WaitForSingleObject.restype = ctypes.c_ulong
kernel.CloseHandle.argtypes = [ctypes.c_void_p]
handle = kernel.OpenProcess(0x100000, False, receipt['gate_pid'])
assert handle, 'Cannot verify the owned gate process; do not infer it has stopped.'
reason = None
try:
    for _ in range(4 * 60 * 6):
        state = json.loads(receipt_path.read_text(encoding='utf-8'))
        if state['status'] in ('PASS', 'FAIL'):
            reason = 'RELEASE_GATE_' + state['status']
            break
        if kernel.WaitForSingleObject(handle, 0) == 0:
            reason = 'OWNED_GATE_PROCESS_EXITED'
            break
        time.sleep(10)
    else:
        reason = 'FOUR_HOUR_CLEANUP_BOUNDARY'
finally:
    kernel.CloseHandle(handle)
current = json.loads(pause_path.read_text(encoding='utf-8'))
report = {'gate_pid': receipt['gate_pid'], 'reason': reason,
    'finished_at': datetime.now(timezone.utc).isoformat(), 'original_pause_created_at': original['created_at']}
if current['created_at'] == original['created_at'] and current['status'] == 'PAUSED':
    result = subprocess.run([sys.executable, str(HERE / 'release_worker_pause.py'), 'resume'], capture_output=True, text=True)
    report.update(exit_code=result.returncode, output=result.stdout, errors=result.stderr)
else:
    report['status'] = 'ALREADY_RESTORED_OR_REPLACED_BY_ANOTHER_RUN'
(HERE / 'worker-cleanup-supervisor.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
