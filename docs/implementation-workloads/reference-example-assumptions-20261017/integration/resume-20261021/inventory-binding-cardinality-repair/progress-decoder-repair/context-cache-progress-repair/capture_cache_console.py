"""Read the existing mainprovider console buffer; no input/signals/settings."""
import ctypes as c
from ctypes import wintypes as w
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

class Coord(c.Structure):
    _fields_ = [('X', w.SHORT), ('Y', w.SHORT)]

class Rect(c.Structure):
    _fields_ = [('Left', w.SHORT), ('Top', w.SHORT), ('Right', w.SHORT), ('Bottom', w.SHORT)]

class Info(c.Structure):
    _fields_ = [('size', Coord), ('cursor', Coord), ('attributes', w.WORD), ('window', Rect), ('max_size', Coord)]

k = c.WinDLL('kernel32', use_last_error=True)
k.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p, w.DWORD, w.DWORD, w.HANDLE]
k.CreateFileW.restype = w.HANDLE
k.GetConsoleScreenBufferInfo.argtypes = [w.HANDLE, c.POINTER(Info)]
k.ReadConsoleOutputCharacterW.argtypes = [w.HANDLE, w.LPWSTR, w.DWORD, Coord, c.POINTER(w.DWORD)]
k.CloseHandle.argtypes = [w.HANDLE]
k.FreeConsole()
assert k.AttachConsole(47644), c.get_last_error()
handle = k.CreateFileW('CONOUT$', 0x80000000, 3, None, 3, 0, None)
try:
    assert handle != c.c_void_p(-1).value
    info = Info()
    assert k.GetConsoleScreenBufferInfo(handle, c.byref(info)), c.get_last_error()
    start = max(0, info.cursor.Y - 500)
    size = info.size.X * (info.cursor.Y - start + 1)
    buffer = c.create_unicode_buffer(size + 1)
    read = w.DWORD()
    assert k.ReadConsoleOutputCharacterW(handle, buffer, size, Coord(0, start), c.byref(read)), c.get_last_error()
    raw = buffer[:read.value]
    lines = [raw[index:index + info.size.X].rstrip() for index in range(0, len(raw), info.size.X)]
finally:
    k.CloseHandle(handle)
    k.FreeConsole()
out = Path(__file__).resolve().parent / 'native-cache'
path = out / 'main-console-after.txt'
assert not path.exists()
path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
evidence = {'at_utc': datetime.now(timezone.utc).isoformat(), 'main_pid': 47644, 'read_only': True,
            'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'lines': len(lines)}
(out / 'console-capture.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
print(json.dumps(evidence))
for index, line in enumerate(lines):
    if 'cached' in line or 'prompt eval time' in line or 'full prompt re-processing' in line:
        print(str(index + 1) + ': ' + line)
