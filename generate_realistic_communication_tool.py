"""Unified launcher for the Communication Simulator CLI and web application."""

from __future__ import annotations

import os
import json
import signal
import socket
import subprocess
import sys
import time
import uuid
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent
SIMULATOR_ROOT = ROOT / "backend" / "simulator"
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 5050
FRONTEND_HOST = "127.0.0.1"
FRONTEND_PORT = 3500


def _wait_for_url(
    url: str,
    process: subprocess.Popen[object],
    timeout_s: float = 20.0,
    expected_instance_id: str | None = None,
) -> bool:
    """Wait for a local service, but stop promptly if its process exits."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urlopen(url, timeout=0.8) as response:
                if not 200 <= response.status < 500:
                    continue
                if expected_instance_id is None:
                    return True
                payload = json.loads(response.read().decode("utf-8"))
                if payload.get("instance_id") == expected_instance_id:
                    return True
        except (OSError, URLError, UnicodeError, json.JSONDecodeError):
            pass
        time.sleep(0.2)
    return False


def _ensure_port_available(host: str, port: int, service: str) -> None:
    """Fail before spawning children if a fixed application port is occupied."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind((host, port))
    except OSError as error:
        raise SystemExit(
            f"{service} kann nicht starten: Port {host}:{port} wird bereits von "
            "einem anderen Prozess verwendet. Beende den anderen Dienst und starte "
            "den Simulator erneut. Es wird bewusst kein Ersatzport gewählt."
        ) from error
    finally:
        probe.close()


def _popen_options() -> dict[str, object]:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _terminate_process_tree(process: subprocess.Popen[object]) -> None:
    """Stop the complete npm/Python child tree so ports are not left behind."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _run_cli(arguments: list[str]) -> int:
    sys.path.insert(0, str(SIMULATOR_ROOT))
    sys.argv = [str(SIMULATOR_ROOT / "generate_realistic_communication_tool.py"), *arguments]
    from generate_realistic_communication_tool import main

    main()
    return 0


def _run_backend() -> int:
    from backend.app.__main__ import main

    return main()


def _run_web() -> int:
    npm = "npm.cmd" if os.name == "nt" else "npm"
    frontend = ROOT / "frontend"
    if not (frontend / "node_modules").is_dir():
        raise SystemExit(
            "Frontend-Abhängigkeiten fehlen. Bitte zuerst im Ordner frontend `npm install` ausführen."
        )

    backend_host = os.environ.get("FLASK_HOST", BACKEND_HOST)
    try:
        backend_port = int(os.environ.get("FLASK_PORT", str(BACKEND_PORT)))
    except ValueError as error:
        raise SystemExit("FLASK_PORT muss eine ganze Zahl sein.") from error
    _ensure_port_available(backend_host, backend_port, "Backend")
    _ensure_port_available(FRONTEND_HOST, FRONTEND_PORT, "Frontend")

    instance_id = uuid.uuid4().hex
    backend_environment = os.environ.copy()
    backend_environment["SIMULATOR_INSTANCE_ID"] = instance_id

    backend_process = subprocess.Popen(
        [sys.executable, "-m", "backend.app"],
        cwd=ROOT,
        env=backend_environment,
        **_popen_options(),
    )
    frontend_process: subprocess.Popen[object] | None = None
    launcher_error = False
    try:
        backend_url = f"http://{backend_host}:{backend_port}"
        if not _wait_for_url(
            f"{backend_url}/api/health",
            backend_process,
            expected_instance_id=instance_id,
        ):
            return_code = backend_process.poll()
            raise RuntimeError(
                "Das Simulator-Backend wurde nicht bereit"
                + (f" (Exit-Code {return_code})." if return_code is not None else ".")
            )

        frontend_process = subprocess.Popen(
            [npm, "run", "dev"],
            cwd=frontend,
            **_popen_options(),
        )
        frontend_url = f"http://{FRONTEND_HOST}:{FRONTEND_PORT}"
        if not _wait_for_url(frontend_url, frontend_process):
            return_code = frontend_process.poll()
            raise RuntimeError(
                "Die Simulator-Oberfläche wurde nicht bereit"
                + (f" (Exit-Code {return_code})." if return_code is not None else ".")
            )

        print(f"Backend: {backend_url} (exklusiv)")
        print(f"Frontend: {frontend_url} (exklusiv)")
        print("Beenden mit Strg+C")
        webbrowser.open(frontend_url, new=2)
        while backend_process.poll() is None and frontend_process.poll() is None:
            time.sleep(0.5)
        failed_service = "Backend" if backend_process.poll() is not None else "Frontend"
        failed_process = backend_process if failed_service == "Backend" else frontend_process
        print(
            f"{failed_service} wurde unerwartet beendet "
            f"(Exit-Code {failed_process.returncode}). Der andere Dienst wird ebenfalls beendet.",
            file=sys.stderr,
        )
        launcher_error = True
    except KeyboardInterrupt:
        pass
    except RuntimeError as error:
        print(f"Start fehlgeschlagen: {error}", file=sys.stderr)
        launcher_error = True
    finally:
        if frontend_process is not None:
            _terminate_process_tree(frontend_process)
        _terminate_process_tree(backend_process)
    if launcher_error:
        return 1
    return backend_process.returncode or (frontend_process.returncode if frontend_process else 0) or 0


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
