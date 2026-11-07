"""Read-only Windows host metrics for the Docker-hosted NetworkIS UI."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import shutil
import subprocess
import threading
import time
from ctypes import wintypes
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


MEBIBYTE = 1024 * 1024
_sample_lock = threading.Lock()
_ROOT = Path(__file__).resolve().parent
_HOST_FILES = ('host_metrics_bridge.py', 'backend/nis/agent/orchestration/reference_token_budget.py',
               'backend/nis/agent/orchestration/host_tokenizer.py')
# Report exactly the startup files. A disk edit cannot make an old process
# claim the new implementation; the local release verification hashes these.
HOST_IMPLEMENTATION = {name: hashlib.sha256((_ROOT / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                       for name in _HOST_FILES}


class MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _filetime_value(value: wintypes.FILETIME) -> int:
    return (value.dwHighDateTime << 32) | value.dwLowDateTime


def _system_times() -> tuple[int, int]:
    idle = wintypes.FILETIME()
    kernel = wintypes.FILETIME()
    user = wintypes.FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(
        ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
    ):
        raise ctypes.WinError()
    return _filetime_value(idle), _filetime_value(kernel) + _filetime_value(user)


def cpu_percent(interval_seconds: float = 0.2) -> float:
    before_idle, before_total = _system_times()
    time.sleep(interval_seconds)
    after_idle, after_total = _system_times()
    elapsed = max(1, after_total - before_total)
    idle = max(0, after_idle - before_idle)
    return round(max(0.0, min(100.0, 100.0 * (1.0 - idle / elapsed))), 1)


def memory_sample() -> dict[str, float | int]:
    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ctypes.WinError()
    used = status.ullTotalPhys - status.ullAvailPhys
    return {
        "memory_percent": round(100.0 * used / max(1, status.ullTotalPhys), 1),
        "memory_used_mb": round(used / MEBIBYTE),
        "memory_total_mb": round(status.ullTotalPhys / MEBIBYTE),
    }


def gpu_sample() -> dict[str, float | int] | None:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return None
    try:
        completed = subprocess.run(
            [
                executable,
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        first_line = completed.stdout.splitlines()[0]
        utilization, memory_used, memory_total = (
            float(value.strip()) for value in first_line.split(",")
        )
        return {
            "utilization_percent": round(utilization, 1),
            "memory_used_mb": round(memory_used),
            "memory_total_mb": round(memory_total),
        }
    except (IndexError, OSError, subprocess.SubprocessError, ValueError):
        return None


def performance_sample() -> dict[str, object]:
    with _sample_lock:
        memory = memory_sample()
        return {
            "schema_version": 1,
            "source": "windows-host",
            "sampled_at": datetime.now(UTC).isoformat(),
            "cpu_percent": cpu_percent(),
            **memory,
            "gpu": gpu_sample(),
        }


class MetricsHandler(BaseHTTPRequestHandler):
    server_version = "NetworkISHostMetrics/1.0"

    def do_POST(self) -> None:  # noqa: N802
        if self.path != '/tokenize-chat':
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 4 * 1024 * 1024 or self.headers.get('Transfer-Encoding'):
                self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                return
            self.connection.settimeout(15)
            from backend.nis.agent.orchestration.host_tokenizer import count_chat
            payload = count_chat(json.loads(self.rfile.read(size)))
            if (payload['contract_source_sha256'] != HOST_IMPLEMENTATION[_HOST_FILES[1]]
                    or payload['host_source_sha256'] != HOST_IMPLEMENTATION[_HOST_FILES[2]]):
                raise ValueError('Host source changed since service startup')
            status = HTTPStatus.OK
        except Exception:  # Unavailable evidence must never become admission.
            payload, status = {'error': 'TOKENIZER_EVIDENCE_UNAVAILABLE'}, HTTPStatus.SERVICE_UNAVAILABLE
        body = json.dumps(payload, separators=(',', ':')).encode('utf8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path.rstrip("/") not in {"/health", "/metrics"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            payload = {"ok": True, "implementation": HOST_IMPLEMENTATION} if self.path.startswith("/health") else performance_sample()
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as error:  # pragma: no cover - defensive service boundary
            body = json.dumps({"error": str(error)}).encode("utf-8")
            self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=13502)
    parser.add_argument("--identity", action="store_true", help="Print host asset identity without starting a service")
    args = parser.parse_args()
    if args.identity:
        print(json.dumps(HOST_IMPLEMENTATION, sort_keys=True))
        return
    server = ThreadingHTTPServer(("127.0.0.1", args.port), MetricsHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
