"""Runtime sizing and local accelerator discovery for desktop deployments."""

from __future__ import annotations

import csv
import ctypes
import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from io import StringIO
from urllib.error import URLError
from urllib.request import urlopen


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


@dataclass(frozen=True)
class RuntimeSettings:
    logical_cores: int
    api_threads: int
    simulation_workers: int
    simulation_executor: str
    ai_provider: str
    local_ai_base_url: str
    local_ai_model: str


def runtime_settings() -> RuntimeSettings:
    logical_cores = max(1, os.cpu_count() or 1)
    default_workers = min(12, max(2, logical_cores // 2))
    default_threads = min(32, max(8, logical_cores // 2))
    executor = os.environ.get("SIMULATION_EXECUTOR", "process").strip().lower()
    if executor not in {"process", "thread"}:
        executor = "process"
    return RuntimeSettings(
        logical_cores=logical_cores,
        api_threads=_bounded_int("WAITRESS_THREADS", default_threads, 4, 64),
        simulation_workers=_bounded_int(
            "SIMULATION_WORKERS", default_workers, 1, max(1, logical_cores)
        ),
        simulation_executor=executor,
        ai_provider=os.environ.get("AI_PROVIDER", "hybrid-demand").strip().lower()
        or "hybrid-demand",
        local_ai_base_url=os.environ.get(
            "LOCAL_AI_BASE_URL", "http://127.0.0.1:11434/v1"
        ).rstrip("/"),
        local_ai_model=os.environ.get("LOCAL_AI_MODEL", "qwen3.8:27b").strip()
        or "qwen3.8:27b",
    )


def _total_memory_bytes() -> int | None:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total_physical", ctypes.c_ulonglong),
                ("available_physical", ctypes.c_ulonglong),
                ("total_page_file", ctypes.c_ulonglong),
                ("available_page_file", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("available_virtual", ctypes.c_ulonglong),
                ("available_extended_virtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.total_physical)
        return None
    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        return None


def _gpu_status() -> dict[str, object]:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return {"available": False, "cuda_available": False}
    try:
        completed = subprocess.run(
            [
                executable,
                "--query-gpu=name,memory.total,memory.used,utilization.gpu,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
        row = next(csv.reader(StringIO(completed.stdout.strip())))
        name, total, used, utilization, driver = [item.strip() for item in row]
        return {
            "available": True,
            "cuda_available": True,
            "name": name,
            "memory_total_mib": int(total),
            "memory_used_mib": int(used),
            "utilization_percent": int(utilization),
            "driver_version": driver,
        }
    except (OSError, subprocess.SubprocessError, StopIteration, ValueError):
        return {"available": False, "cuda_available": False}


def _ollama_status(settings: RuntimeSettings) -> dict[str, object]:
    api_root = settings.local_ai_base_url.removesuffix("/v1")
    try:
        with urlopen(f"{api_root}/api/tags", timeout=0.8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = sorted(
            str(item.get("name") or item.get("model"))
            for item in payload.get("models", [])
            if isinstance(item, dict) and (item.get("name") or item.get("model"))
        )
        requested = settings.local_ai_model.lower()
        installed = any(
            model.lower() == requested
            or model.lower().removesuffix(":latest") == requested.removesuffix(":latest")
            for model in models
        )
        return {
            "reachable": True,
            "model_installed": installed,
            "models": models,
        }
    except (OSError, URLError, UnicodeError, json.JSONDecodeError):
        return {"reachable": False, "model_installed": False, "models": []}


def runtime_status() -> dict[str, object]:
    settings = runtime_settings()
    memory = _total_memory_bytes()
    return {
        "settings": asdict(settings),
        "server": {
            "implementation": os.environ.get("SIMULATOR_SERVER", "werkzeug"),
            "threads": settings.api_threads,
        },
        "cpu": {
            "logical_cores": settings.logical_cores,
            "simulation_workers": settings.simulation_workers,
            "executor": settings.simulation_executor,
        },
        "memory": {
            "total_bytes": memory,
            "total_gib": round(memory / (1024**3), 2) if memory else None,
        },
        "gpu": _gpu_status(),
        "ai": {
            "provider": settings.ai_provider,
            "local_base_url": settings.local_ai_base_url,
            "local_model": settings.local_ai_model,
            "ollama": _ollama_status(settings),
        },
    }
