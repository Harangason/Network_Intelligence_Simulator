"""Unified launcher for the Communication Simulator CLI and web application."""

from __future__ import annotations

import os
import json
import signal
import shutil
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
BACKEND_PORT = 15050
FRONTEND_HOST = "127.0.0.1"
FRONTEND_PORT = 13500
SERVICE_LOG_ROOT = ROOT / "backend" / "runtime" / "service-logs"
DEFAULT_LOCAL_AI_URL = "http://127.0.0.1:11434/v1"
DEFAULT_LOCAL_AI_MODEL = "qwen3.8:27b"


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


def _port_from_environment(name: str, default: int) -> int:
    raw_port = os.environ.get(name, str(default)).strip()
    try:
        port = int(raw_port)
    except ValueError as error:
        raise SystemExit(f"{name} muss eine ganze Zahl sein.") from error
    if not 1 <= port <= 65535:
        raise SystemExit(f"{name} muss zwischen 1 und 65535 liegen.")
    return port


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


def _frontend_dev_command(frontend: Path, port: int = FRONTEND_PORT) -> list[str]:
    """Start Next.js from local dependencies instead of relying on global npm."""
    node = shutil.which("node")
    if node is None:
        raise SystemExit("Node.js wurde nicht gefunden. Bitte Node.js installieren und erneut starten.")

    next_cli = frontend / "node_modules" / "next" / "dist" / "bin" / "next"
    if not next_cli.is_file():
        raise SystemExit(
            "Next.js fehlt in frontend/node_modules. Bitte zuerst im Ordner frontend "
            "`npm install` ausführen."
        )

    return [node, str(next_cli), "dev", "--webpack", "-p", str(port)]


def _ollama_api_root(environment: dict[str, str]) -> str:
    return environment.get("LOCAL_AI_BASE_URL", DEFAULT_LOCAL_AI_URL).rstrip("/").removesuffix("/v1")


def _ollama_models(environment: dict[str, str]) -> list[str] | None:
    try:
        with urlopen(f"{_ollama_api_root(environment)}/api/tags", timeout=1.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return [
            str(item.get("name") or item.get("model"))
            for item in payload.get("models", [])
            if isinstance(item, dict) and (item.get("name") or item.get("model"))
        ]
    except (OSError, URLError, UnicodeError, json.JSONDecodeError):
        return None


def _model_is_installed(requested: str, installed: list[str]) -> bool:
    normalized = requested.lower().removesuffix(":latest")
    return any(item.lower().removesuffix(":latest") == normalized for item in installed)


def _ensure_local_ai(
    environment: dict[str, str],
    log_handle,
) -> subprocess.Popen[object] | None:
    provider = environment.get("AI_PROVIDER", "hybrid-demand").strip().lower()
    if provider not in {"local", "ollama", "hybrid", "hybrid-demand"}:
        return None

    models = _ollama_models(environment)
    owned_process: subprocess.Popen[object] | None = None
    if models is None:
        executable = shutil.which("ollama")
        if executable is None:
            raise RuntimeError(
                "Ollama wurde nicht gefunden. Installiere Ollama und lade "
                f"anschließend `{environment['LOCAL_AI_MODEL']}`."
            )
        owned_process = subprocess.Popen(
            [executable, "serve"],
            cwd=ROOT,
            env=environment,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            **_popen_options(),
        )
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            models = _ollama_models(environment)
            if models is not None:
                break
            if owned_process.poll() is not None:
                break
            time.sleep(0.25)
    if models is None:
        if owned_process is not None:
            _terminate_process_tree(owned_process)
        raise RuntimeError("Der lokale Ollama-Dienst wurde nicht bereit.")

    requested_model = environment["LOCAL_AI_MODEL"]
    if not _model_is_installed(requested_model, models):
        if owned_process is not None:
            _terminate_process_tree(owned_process)
        raise RuntimeError(
            f"Das lokale Modell `{requested_model}` fehlt. Führe "
            f"`ollama pull {requested_model}` aus."
        )
    return owned_process


def _load_runtime_env_file(environment: dict[str, str], path: Path) -> None:
    """Load KEY=VALUE entries while preserving valid explicit process values."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        current = environment.get(key)
        invalid_api_key = key.endswith("_API_KEY") and (
            not current
            or len(current.strip()) < 20
            or current.strip().upper().startswith(("YOUR", "DEIN", "PLACEHOLDER", "CHANGEME"))
        )
        if current is None or invalid_api_key:
            environment[key] = value


def _runtime_environment() -> dict[str, str]:
    environment = os.environ.copy()
    _load_runtime_env_file(environment, ROOT / ".env.local")
    shared_env_file = Path(
        environment.get("NETWORKIS_SHARED_ENV_FILE", str(ROOT.parent / ".env"))
    ).expanduser()
    _load_runtime_env_file(environment, shared_env_file)
    shared_openai_key = environment.get("OPEN_AI_KEY", "").strip()
    if len(shared_openai_key) >= 20:
        # Accept the organization-wide alias and make it authoritative for NetworkIS.
        environment["OPENAI_API_KEY"] = shared_openai_key
    logical_cores = max(1, os.cpu_count() or 1)
    environment.setdefault("AI_PROVIDER", "hybrid-demand")
    environment.setdefault("LOCAL_AI_BASE_URL", DEFAULT_LOCAL_AI_URL)
    environment.setdefault("LOCAL_AI_MODEL", DEFAULT_LOCAL_AI_MODEL)
    environment.setdefault("CLOUD_ESCALATION", "on_failure")
    environment.setdefault("OLLAMA_MODELS", r"I:\engineering-intelligence-platform\models\ollama")
    environment.setdefault("OLLAMA_CONTEXT_LENGTH", "8192")
    environment.setdefault("OLLAMA_KEEP_ALIVE", "10m")
    environment.setdefault("WAITRESS_THREADS", str(min(32, max(8, logical_cores // 2))))
    environment.setdefault("SIMULATION_WORKERS", str(min(12, max(2, logical_cores // 2))))
    environment.setdefault("SIMULATION_EXECUTOR", "process")
    # Each worker gets one numeric-library thread; parallelism is owned by the process pool.
    environment.setdefault("OMP_NUM_THREADS", "1")
    environment.setdefault("OPENBLAS_NUM_THREADS", "1")
    environment.setdefault("MKL_NUM_THREADS", "1")
    environment.setdefault("NUMEXPR_NUM_THREADS", "1")
    return environment


def _run_web() -> int:
    frontend = ROOT / "frontend"
    if not (frontend / "node_modules").is_dir():
        raise SystemExit(
            "Frontend-Abhängigkeiten fehlen. Bitte zuerst im Ordner frontend `npm install` ausführen."
        )
    frontend_port = _port_from_environment("FRONTEND_PORT", FRONTEND_PORT)
    frontend_command = _frontend_dev_command(frontend, frontend_port)

    backend_host = os.environ.get("FLASK_HOST", BACKEND_HOST)
    backend_port = _port_from_environment("FLASK_PORT", BACKEND_PORT)
    _ensure_port_available(backend_host, backend_port, "Backend")
    _ensure_port_available(FRONTEND_HOST, frontend_port, "Frontend")

    instance_id = uuid.uuid4().hex
    service_environment = _runtime_environment()
    backend_environment = service_environment.copy()
    backend_environment["SIMULATOR_INSTANCE_ID"] = instance_id

    SERVICE_LOG_ROOT.mkdir(parents=True, exist_ok=True)
    backend_log_path = SERVICE_LOG_ROOT / "backend.log"
    frontend_log_path = SERVICE_LOG_ROOT / "frontend.log"
    ollama_log_path = SERVICE_LOG_ROOT / "ollama.log"
    backend_log = backend_log_path.open("w", encoding="utf-8", buffering=1)
    frontend_log = frontend_log_path.open("w", encoding="utf-8", buffering=1)
    ollama_log = ollama_log_path.open("w", encoding="utf-8", buffering=1)

    backend_process: subprocess.Popen[object] | None = None
    frontend_process: subprocess.Popen[object] | None = None
    ollama_process: subprocess.Popen[object] | None = None
    launcher_error = False
    try:
        ollama_process = _ensure_local_ai(service_environment, ollama_log)
        backend_process = subprocess.Popen(
            [sys.executable, "-m", "backend.app"],
            cwd=ROOT,
            env=backend_environment,
            stdout=backend_log,
            stderr=subprocess.STDOUT,
            **_popen_options(),
        )
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
            frontend_command,
            cwd=frontend,
            env=service_environment,
            stdout=frontend_log,
            stderr=subprocess.STDOUT,
            **_popen_options(),
        )
        frontend_url = f"http://{FRONTEND_HOST}:{frontend_port}"
        if not _wait_for_url(frontend_url, frontend_process):
            return_code = frontend_process.poll()
            raise RuntimeError(
                "Die Simulator-Oberfläche wurde nicht bereit"
                + (f" (Exit-Code {return_code})." if return_code is not None else ".")
            )

        print(f"Backend: {backend_url} (exklusiv)")
        print(f"Frontend: {frontend_url} (exklusiv)")
        print(f"Dienstlogs: {SERVICE_LOG_ROOT}")
        print("Beenden mit Strg+C")
        if os.environ.get("NETWORKIS_OPEN_BROWSER", "1").strip().lower() not in {
            "0",
            "false",
            "no",
        }:
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
        if backend_process is not None:
            _terminate_process_tree(backend_process)
        if ollama_process is not None:
            _terminate_process_tree(ollama_process)
        backend_log.close()
        frontend_log.close()
        ollama_log.close()
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
