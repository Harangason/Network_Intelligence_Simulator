"""Unified launcher for the Communication Simulator CLI and web application."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SIMULATOR_ROOT = ROOT / "backend" / "simulator"


def _run_cli(arguments: list[str]) -> int:
    sys.path.insert(0, str(SIMULATOR_ROOT))
    sys.argv = [str(SIMULATOR_ROOT / "generate_realistic_communication_tool.py"), *arguments]
    from generate_realistic_communication_tool import main

    main()
    return 0


def _run_backend() -> int:
    from backend.app.__main__ import main

    main()
    return 0


def _run_web() -> int:
    npm = "npm.cmd" if os.name == "nt" else "npm"
    frontend = ROOT / "frontend"
    if not (frontend / "node_modules").is_dir():
        raise SystemExit(
            "Frontend-Abhängigkeiten fehlen. Bitte zuerst im Ordner frontend `npm install` ausführen."
        )

    backend_process = subprocess.Popen(
        [sys.executable, "-m", "backend.app"],
        cwd=ROOT,
    )
    frontend_process = subprocess.Popen(
        [npm, "run", "dev"],
        cwd=frontend,
    )
    print("Backend: http://127.0.0.1:5050")
    print("Frontend: http://127.0.0.1:3001")
    print("Beenden mit Strg+C")
    try:
        while backend_process.poll() is None and frontend_process.poll() is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in (frontend_process, backend_process):
            if process.poll() is None:
                process.terminate()
        for process in (frontend_process, backend_process):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    return backend_process.returncode or frontend_process.returncode or 0


def main() -> int:
    arguments = sys.argv[1:]
    command = arguments[0].lower() if arguments else "cli"
    if command == "web":
        return _run_web()
    if command == "backend":
        return _run_backend()
    if command == "cli":
        arguments = arguments[1:]
    return _run_cli(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
