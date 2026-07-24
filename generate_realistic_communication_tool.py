"""Unified launcher for the Communication Simulator CLI and web application."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent
SIMULATOR_ROOT = ROOT / "backend" / "simulator"


def _wait_for_url(url: str, process: subprocess.Popen[object], timeout_s: float = 20.0) -> bool:
    """Wait for a local service, but stop promptly if its process exits."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urlopen(url, timeout=0.8) as response:
                if 200 <= response.status < 500:
                    return True
        except (OSError, URLError):
            pass
        time.sleep(0.2)
    return False


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
    # Do not open the browser against a half-started dev server.  This avoids a
    # stale loading view if the first request races Next.js or Flask startup.
    backend_ready = _wait_for_url("http://127.0.0.1:5050/api/health", backend_process)
    frontend_ready = _wait_for_url("http://127.0.0.1:3001", frontend_process)
    if backend_ready and frontend_ready:
        webbrowser.open("http://127.0.0.1:3001", new=2)
    else:
        print("Hinweis: Ein Dienst wurde nicht rechtzeitig bereit. Prüfe die Konsolenausgabe.")
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
    # The visual editor is the primary entry point.  Existing command-line
    # arguments remain backwards compatible and are forwarded to the CLI.
    command = arguments[0].lower() if arguments else "web"
    if command == "web":
        return _run_web()
    if command == "backend":
        return _run_backend()
    if command == "cli":
        arguments = arguments[1:]
    return _run_cli(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
