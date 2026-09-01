"""Unified launcher for the Communication Simulator CLI and web application."""

from __future__ import annotations

import os
import json
import signal
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
import webbrowser
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlparse
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent
CANONICAL_ROOT = Path(r"I:\PycharmProjects\My_first_Network_Simulator")
SIMULATOR_ROOT = ROOT / "backend" / "simulator"
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 15050
FRONTEND_HOST = "127.0.0.1"
FRONTEND_PORT = 13500
SERVICE_LOG_ROOT = ROOT / "backend" / "runtime" / "service-logs"
DEFAULT_LOCAL_AI_URL = "http://127.0.0.1:11434/v1"
DEFAULT_LOCAL_AI_MODEL = "qwen3.8:27b"
DEFAULT_LOCAL_AI_FAST_MODEL = "llama3.1:8b"
DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://eip_user:localDockerOnly7a1c9e4f2b8d6a3c5e0f"
    "@127.0.0.1:5432/eip_blocker"
)
ENGINEERING_DB_CONTAINER = "network-simulator-engineering-db"
DEPENDENCY_HEALTH_INTERVAL_SECONDS = 5.0
DEFAULT_SERVICE_RESTART_LIMIT = 5


class DependencyCheck(NamedTuple):
    name: str
    ok: bool
    detail: str
    hint: str = ""


class DockerProbe(NamedTuple):
    available: bool
    executable: str | None
    output: str
    timed_out: bool = False


DOCKER_INFERENCE_MARKERS = (
    "dockerinference",
    "inference manager",
)


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


def _url_available(url: str, timeout_s: float = 0.8) -> bool:
    """Return true only for a successful local HTTP health response."""
    try:
        with urlopen(url, timeout=timeout_s) as response:
            return 200 <= response.status < 300
    except (OSError, URLError):
        return False


def _service_restart_limit(environment: dict[str, str]) -> int:
    raw = environment.get("NETWORKIS_SERVICE_RESTARTS", str(DEFAULT_SERVICE_RESTART_LIMIT))
    try:
        value = int(raw)
    except ValueError as error:
        raise RuntimeError("NETWORKIS_SERVICE_RESTARTS muss eine ganze Zahl sein.") from error
    if value < 0:
        raise RuntimeError("NETWORKIS_SERVICE_RESTARTS darf nicht negativ sein.")
    return value


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


def _assert_canonical_project_root() -> None:
    if os.environ.get("NETWORKIS_ALLOW_NON_CANONICAL_ROOT", "").strip().lower() in {"1", "true", "yes"}:
        return
    try:
        current = ROOT.resolve()
        canonical = CANONICAL_ROOT.resolve()
    except OSError:
        current = ROOT
        canonical = CANONICAL_ROOT
    if os.name == "nt":
        current_text = str(current).lower()
        canonical_text = str(canonical).lower()
    else:
        current_text = str(current)
        canonical_text = str(canonical)
    if current_text != canonical_text:
        raise SystemExit(
            "Falscher Simulator-Projektpfad. Dieser Launcher darf standardmäßig nur aus "
            f"{CANONICAL_ROOT} gestartet werden. Aktuell: {ROOT}. "
            "Setze NETWORKIS_ALLOW_NON_CANONICAL_ROOT=1 nur für bewusste Diagnose-Kopien."
        )


def _port_from_environment(name: str, default: int) -> int:
    raw_port = os.environ.get(name, str(default)).strip()
    try:
        port = int(raw_port)
    except ValueError as error:
        raise SystemExit(f"{name} muss eine ganze Zahl sein.") from error
    if not 1 <= port <= 65535:
        raise SystemExit(f"{name} muss zwischen 1 und 65535 liegen.")
    return port


def _tcp_endpoint_available(host: str, port: int, timeout_s: float = 1.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(timeout_s)
        try:
            client.connect((host, port))
            return True
        except OSError:
            return False


def _database_endpoint(database_url: str) -> tuple[str, int]:
    normalized = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    parsed = urlparse(normalized)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 5432
    return host, port


def _run_command(arguments: list[str], *, timeout_s: float | None = None) -> subprocess.CompletedProcess[str]:
    def _timeout_text(value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value

    def _kill_process_tree(process: subprocess.Popen[str]) -> None:
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
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()

    popen_options: dict[str, object] = {}
    if os.name == "nt":
        popen_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_options["start_new_session"] = True
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            arguments,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            **popen_options,
        )
        output, _ = process.communicate(timeout=timeout_s)
        return subprocess.CompletedProcess(arguments, process.returncode or 0, output or "")
    except subprocess.TimeoutExpired as error:
        if process is not None:
            _kill_process_tree(process)
            try:
                output, _ = process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                output = _timeout_text(error.stdout) + _timeout_text(error.stderr)
        else:
            output = _timeout_text(error.stdout) + _timeout_text(error.stderr)
        return subprocess.CompletedProcess(
            arguments,
            124,
            (output or "")
            + "\nBefehl wurde wegen Timeout beendet und der Prozessbaum wurde beendet.",
        )


def _docker_probe(timeout_s: float = 5.0) -> DockerProbe:
    docker = shutil.which("docker")
    if docker is None:
        return DockerProbe(False, None, "Docker CLI wurde nicht gefunden.")
    result = _run_command([docker, "info"], timeout_s=timeout_s)
    return DockerProbe(
        result.returncode == 0,
        docker,
        result.stdout.strip(),
        result.returncode == 124,
    )


def _docker_available() -> bool:
    return _docker_probe().available


def _docker_failure_hint(output: str) -> str:
    key = output.lower()
    if any(marker in key for marker in DOCKER_INFERENCE_MARKERS):
        return (
            "Docker Desktop startet nicht sauber: Der Inference-Manager blockiert den "
            "`dockerInference`-Listener. Beende Docker Desktop vollstaendig, starte es "
            "mit Windows-Rechten neu und pruefe in Docker Desktop, ob die Inference-/AI-"
            "Komponente repariert oder deaktiviert werden muss."
        )
    if "permission denied" in key and ("docker_engine" in key or "dockerdesktoplinuxengine" in key):
        return (
            "Docker Engine ist fuer diesen Prozess nicht erreichbar. Starte Docker Desktop "
            "vollstaendig und pruefe, ob der aktuelle Windows-Nutzer Zugriff auf die Docker-"
            "Engine hat."
        )
    if "dockerdesktoplinuxengine" in key and (
        "nicht finden" in key or "cannot find" in key or "does not exist" in key
    ):
        return (
            "Der Docker-Kontext zeigt auf `desktop-linux`, aber die Linux-Engine-Pipe ist "
            "nicht vorhanden. Docker Desktop ist nicht fertig gestartet oder der Kontext ist defekt."
        )
    if "timeout" in key or "timeout" in output:
        return (
            "Docker antwortet nicht innerhalb des Startfensters. Docker Desktop haengt "
            "wahrscheinlich im Initialisieren; die App wird deshalb nicht teilgestartet."
        )
    return (
        "Docker Desktop ist nicht bereit. Starte Docker Desktop manuell und wiederhole den "
        "Start, sobald `docker info` erfolgreich ist."
    )


def _docker_failure_is_actionable(output: str) -> bool:
    key = output.lower()
    return (
        any(marker in key for marker in DOCKER_INFERENCE_MARKERS)
        or ("permission denied" in key and ("docker_engine" in key or "dockerdesktoplinuxengine" in key))
        or (
            "dockerdesktoplinuxengine" in key
            and ("nicht finden" in key or "cannot find" in key or "does not exist" in key)
        )
    )


def _docker_unavailable_message(probe: DockerProbe) -> str:
    detail = probe.output or "keine Docker-Ausgabe"
    return (
        "Docker Desktop wurde nicht bereit. Die Engineering-Datenbank kann deshalb nicht "
        "automatisch gestartet werden.\n\n"
        f"Docker-Diagnose: {detail}\n\n"
        f"Naechster Schritt: {_docker_failure_hint(detail)}"
    )


def _docker_doctor_detail(probe: DockerProbe) -> str:
    if probe.available:
        return f"{probe.executable or 'docker'} info erfolgreich"
    return probe.output or probe.executable or "nicht verfuegbar"


def _try_start_docker_desktop() -> str:
    outputs: list[str] = []
    docker = shutil.which("docker")
    use_desktop_cli = os.environ.get("NETWORKIS_USE_DOCKER_DESKTOP_CLI_START", "").strip().lower() in {"1", "true", "yes"}
    if docker is not None and use_desktop_cli:
        result = _run_command([docker, "desktop", "start"], timeout_s=8)
        if result.stdout.strip():
            outputs.append(result.stdout.strip())
    elif docker is not None:
        outputs.append("Docker Desktop CLI-Start wurde uebersprungen, weil dieser Befehl auf Windows haengen kann.")
    docker_desktop = Path(r"C:\Program Files\Docker\Docker\Docker Desktop.exe")
    if docker_desktop.is_file():
        subprocess.Popen([str(docker_desktop)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return "\n".join(outputs)


def _wait_for_docker(timeout_s: float = 35.0) -> DockerProbe:
    deadline = time.monotonic() + timeout_s
    last_probe = _docker_probe(timeout_s=2)
    if last_probe.available:
        return last_probe
    while time.monotonic() < deadline:
        last_probe = _docker_probe(timeout_s=2)
        if last_probe.available:
            return last_probe
        time.sleep(2.0)
    return last_probe


def _run_dependency_doctor(environment: dict[str, str]) -> list[DependencyCheck]:
    frontend = ROOT / "frontend"
    database_host, database_port = _database_endpoint(environment.get("DATABASE_URL", DEFAULT_DATABASE_URL))
    docker = _docker_probe(timeout_s=5)
    checks = [
        DependencyCheck(
            "Projektpfad",
            ROOT.resolve() == CANONICAL_ROOT.resolve() or os.environ.get("NETWORKIS_ALLOW_NON_CANONICAL_ROOT", "").strip().lower() in {"1", "true", "yes"},
            str(ROOT),
            "Launcher aus dem kanonischen Projektpfad starten.",
        ),
        DependencyCheck(
            "Frontend-Abhaengigkeiten",
            (frontend / "node_modules" / "next" / "dist" / "bin" / "next").is_file(),
            str(frontend / "node_modules"),
            "Im Ordner frontend `npm install` ausfuehren.",
        ),
        DependencyCheck(
            "Backend-Port",
            not _tcp_endpoint_available(BACKEND_HOST, _port_from_environment("FLASK_PORT", BACKEND_PORT), timeout_s=0.3),
            f"{BACKEND_HOST}:{_port_from_environment('FLASK_PORT', BACKEND_PORT)}",
            "Fremden Prozess auf dem Backend-Port beenden.",
        ),
        DependencyCheck(
            "Frontend-Port",
            not _tcp_endpoint_available(FRONTEND_HOST, _port_from_environment("FRONTEND_PORT", FRONTEND_PORT), timeout_s=0.3),
            f"{FRONTEND_HOST}:{_port_from_environment('FRONTEND_PORT', FRONTEND_PORT)}",
            "Fremden Prozess auf dem Frontend-Port beenden.",
        ),
        DependencyCheck(
            "Docker Engine",
            docker.available,
            _docker_doctor_detail(docker),
            _docker_failure_hint(docker.output),
        ),
        DependencyCheck(
            "Engineering-Datenbank-Port",
            _tcp_endpoint_available(database_host, database_port, timeout_s=0.5),
            f"{database_host}:{database_port}",
            "Wird vom Launcher via Docker Compose gestartet, sobald Docker bereit ist.",
        ),
    ]
    return checks


def _print_dependency_doctor(checks: list[DependencyCheck]) -> None:
    print("NetworkIS Start-Doctor")
    for check in checks:
        marker = "OK" if check.ok else "FEHLT"
        print(f"- {marker}: {check.name} - {check.detail}")
        if not check.ok and check.hint:
            print(f"  Hinweis: {check.hint}")


def _ensure_engineering_database(environment: dict[str, str]) -> None:
    environment.setdefault("DATABASE_URL", DEFAULT_DATABASE_URL)
    host, port = _database_endpoint(environment["DATABASE_URL"])
    endpoint_available = _tcp_endpoint_available(host, port)

    compose_file = ROOT / "docker-compose.engineering-db.yml"
    if not compose_file.is_file():
        raise RuntimeError(f"Engineering-Datenbank ist nicht erreichbar und {compose_file.name} fehlt.")

    docker_probe = _docker_probe(timeout_s=2)
    if not docker_probe.available:
        if endpoint_available:
            return
        if _docker_failure_is_actionable(docker_probe.output):
            raise RuntimeError(_docker_unavailable_message(docker_probe))
        docker_start_output = _try_start_docker_desktop()
        docker_probe = _wait_for_docker()
        if not docker_probe.available:
            if docker_start_output:
                docker_probe = DockerProbe(
                    docker_probe.available,
                    docker_probe.executable,
                    f"{docker_start_output}\n{docker_probe.output}".strip(),
                    docker_probe.timed_out,
                )
            raise RuntimeError(_docker_unavailable_message(docker_probe))

    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker CLI wurde nicht gefunden. Die Engineering-Datenbank kann nicht gestartet werden.")
    origin = _run_command(
        [
            docker,
            "inspect",
            "--format",
            '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}',
            ENGINEERING_DB_CONTAINER,
        ],
        timeout_s=5,
    )
    container_root = Path(origin.stdout.strip()) if origin.returncode == 0 and origin.stdout.strip() else None
    wrong_project = container_root is not None and container_root.resolve() != ROOT.resolve()
    if endpoint_available and not wrong_project:
        return

    compose_command = [docker, "compose", "-f", str(compose_file), "up", "-d"]
    if wrong_project:
        compose_command.append("--force-recreate")
    started = _run_command(compose_command, timeout_s=120)
    if started.returncode != 0:
        raise RuntimeError(f"Engineering-Datenbank konnte nicht gestartet werden:\n{started.stdout.strip()}")

    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
        ready = _run_command(
            [docker, "exec", ENGINEERING_DB_CONTAINER, "pg_isready", "-U", "eip_user", "-d", "eip_blocker"],
            timeout_s=5,
        )
        if ready.returncode == 0 and _tcp_endpoint_available(host, port):
            return
        time.sleep(1.0)
    raise RuntimeError("Engineering-Datenbankcontainer läuft nicht rechtzeitig gesund.")


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


def _ollama_executable() -> str | None:
    executable = shutil.which("ollama")
    if executable is not None:
        return executable
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    candidates = [
        Path(local_app_data) / "Programs" / "Ollama" / "ollama.exe" if local_app_data else None,
        Path(r"C:\Program Files\Ollama\ollama.exe"),
    ]
    return next((str(path) for path in candidates if path is not None and path.is_file()), None)


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
        executable = _ollama_executable()
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
    fast_model = environment.get("LOCAL_AI_FAST_MODEL", requested_model).strip() or requested_model
    if not _model_is_installed(fast_model, models):
        environment["LOCAL_AI_FAST_MODEL"] = requested_model
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
    environment.setdefault("LOCAL_AI_FAST_MODEL", DEFAULT_LOCAL_AI_FAST_MODEL)
    environment.setdefault("CLOUD_ESCALATION", "on_failure")
    environment.setdefault("DATABASE_URL", DEFAULT_DATABASE_URL)
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


def _can_write_file(path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ok", encoding="ascii")
        path.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _prepare_backend_runtime_root(environment: dict[str, str], instance_id: str) -> Path | None:
    if environment.get("SIMULATOR_RUNTIME_ROOT"):
        return None
    runtime_root = ROOT / "backend" / "runtime"
    probes = [
        runtime_root / "jobs" / f"launcher-probe-{instance_id[:8]}.tmp",
        runtime_root / "traces" / f"launcher-probe-{instance_id[:8]}.tmp",
    ]
    if all(_can_write_file(path) for path in probes):
        return None
    fallback = Path(tempfile.gettempdir()) / "networkis-runtime" / instance_id[:8]
    environment["SIMULATOR_RUNTIME_ROOT"] = str(fallback)
    return fallback


def _prepare_frontend_dist_dir(frontend: Path, environment: dict[str, str], instance_id: str) -> str | None:
    if environment.get("NETWORKIS_NEXT_DIST_DIR"):
        return None
    isolated_name = ".next-networkis"
    probe = frontend / isolated_name / f"launcher-probe-{instance_id[:8]}.tmp"
    if not _can_write_file(probe):
        raise RuntimeError(
            "Next.js braucht einen relativen beschreibbaren Build-Ordner im Frontend. "
            "Starte den Simulator ausserhalb der Codex-Dateisandbox oder pruefe die "
            "Windows-Dateirechte im Projektordner."
        )
    environment["NETWORKIS_NEXT_DIST_DIR"] = isolated_name
    return isolated_name


def _open_service_log(name: str, instance_id: str):
    candidates = [
        SERVICE_LOG_ROOT / f"{name}.log",
        SERVICE_LOG_ROOT / f"{name}-{instance_id[:8]}.log",
        Path(tempfile.gettempdir()) / "networkis-service-logs" / f"{name}-{instance_id[:8]}.log",
    ]
    last_error: PermissionError | None = None
    for path in candidates:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            return path.open("w", encoding="utf-8", buffering=1)
        except PermissionError as error:
            last_error = error
            continue
    if last_error:
        raise last_error
    raise PermissionError(f"Logdatei fuer {name!r} konnte nicht geoeffnet werden.")


def _run_web() -> int:
    _assert_canonical_project_root()
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
    runtime_fallback = _prepare_backend_runtime_root(service_environment, instance_id)
    frontend_dist_dir = _prepare_frontend_dist_dir(frontend, service_environment, instance_id)
    backend_environment = service_environment.copy()
    backend_environment["SIMULATOR_INSTANCE_ID"] = instance_id

    try:
        SERVICE_LOG_ROOT.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        pass
    backend_log = _open_service_log("backend", instance_id)
    frontend_log = _open_service_log("frontend", instance_id)
    ollama_log = _open_service_log("ollama", instance_id)

    backend_process: subprocess.Popen[object] | None = None
    frontend_process: subprocess.Popen[object] | None = None
    ollama_process: subprocess.Popen[object] | None = None
    launcher_error = False
    restart_counts = {"Backend": 0, "Frontend": 0}
    restart_limit = _service_restart_limit(service_environment)
    backend_url = f"http://{backend_host}:{backend_port}"
    frontend_url = f"http://{FRONTEND_HOST}:{frontend_port}"

    def start_backend() -> subprocess.Popen[object]:
        return subprocess.Popen(
            [sys.executable, "-m", "backend.app"],
            cwd=ROOT,
            env=backend_environment,
            stdout=backend_log,
            stderr=subprocess.STDOUT,
            **_popen_options(),
        )

    def start_frontend() -> subprocess.Popen[object]:
        return subprocess.Popen(
            frontend_command,
            cwd=frontend,
            env=service_environment,
            stdout=frontend_log,
            stderr=subprocess.STDOUT,
            **_popen_options(),
        )

    try:
        _ensure_engineering_database(service_environment)
        backend_environment["DATABASE_URL"] = service_environment["DATABASE_URL"]
        ollama_process = _ensure_local_ai(service_environment, ollama_log)
        backend_process = start_backend()
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
        if not _wait_for_url(f"{backend_url}/api/engineering/health", backend_process):
            raise RuntimeError(
                "Die Engineering-Datenbank wurde nicht bereit. Starte zuerst "
                "`start-engineering-db.bat` oder prüfe DATABASE_URL."
            )

        frontend_process = start_frontend()
        if not _wait_for_url(frontend_url, frontend_process):
            return_code = frontend_process.poll()
            raise RuntimeError(
                "Die Simulator-Oberfläche wurde nicht bereit"
                + (f" (Exit-Code {return_code})." if return_code is not None else ".")
            )

        print(f"Backend: {backend_url} (exklusiv)")
        print(f"Frontend: {frontend_url} (exklusiv)")
        print(f"Dienstlogs: {SERVICE_LOG_ROOT}")
        if runtime_fallback is not None:
            print(f"Runtime-Fallback: {runtime_fallback}")
        if frontend_dist_dir is not None:
            print(f"Next.js Dev-Ordner: frontend/{frontend_dist_dir}")
        print("Beenden mit Strg+C")
        if os.environ.get("NETWORKIS_OPEN_BROWSER", "1").strip().lower() not in {
            "0",
            "false",
            "no",
        }:
            webbrowser.open(frontend_url, new=2)

        next_dependency_check = time.monotonic() + DEPENDENCY_HEALTH_INTERVAL_SECONDS
        while True:
            if backend_process.poll() is not None:
                restart_counts["Backend"] += 1
                if restart_counts["Backend"] > restart_limit:
                    print(
                        f"Backend wurde nach {restart_limit} Neustarts nicht stabil "
                        f"(letzter Exit-Code {backend_process.returncode}).",
                        file=sys.stderr,
                    )
                    launcher_error = True
                    break
                print(
                    f"Backend wurde unerwartet beendet (Exit-Code {backend_process.returncode}). "
                    f"Automatischer Neustart {restart_counts['Backend']}/{restart_limit}.",
                    file=sys.stderr,
                )
                time.sleep(min(2 ** (restart_counts["Backend"] - 1), 5))
                backend_process = start_backend()
                if not _wait_for_url(
                    f"{backend_url}/api/health",
                    backend_process,
                    expected_instance_id=instance_id,
                ):
                    _terminate_process_tree(backend_process)
                    continue
                print("Backend ist nach dem automatischen Neustart wieder bereit.")

            if frontend_process.poll() is not None:
                restart_counts["Frontend"] += 1
                if restart_counts["Frontend"] > restart_limit:
                    print(
                        f"Frontend wurde nach {restart_limit} Neustarts nicht stabil "
                        f"(letzter Exit-Code {frontend_process.returncode}).",
                        file=sys.stderr,
                    )
                    launcher_error = True
                    break
                print(
                    f"Frontend wurde unerwartet beendet (Exit-Code {frontend_process.returncode}). "
                    f"Automatischer Neustart {restart_counts['Frontend']}/{restart_limit}.",
                    file=sys.stderr,
                )
                time.sleep(min(2 ** (restart_counts["Frontend"] - 1), 5))
                frontend_process = start_frontend()
                if not _wait_for_url(frontend_url, frontend_process):
                    _terminate_process_tree(frontend_process)
                    continue
                print("Frontend ist nach dem automatischen Neustart wieder bereit.")

            now = time.monotonic()
            if now >= next_dependency_check:
                next_dependency_check = now + DEPENDENCY_HEALTH_INTERVAL_SECONDS
                local_ai_required = service_environment.get("AI_PROVIDER", "hybrid-demand").strip().lower() in {
                    "local",
                    "ollama",
                    "hybrid",
                    "hybrid-demand",
                }
                if local_ai_required and _ollama_models(service_environment) is None:
                    if ollama_process is not None and ollama_process.poll() is None:
                        _terminate_process_tree(ollama_process)
                    ollama_process = None
                    try:
                        ollama_process = _ensure_local_ai(service_environment, ollama_log)
                        print("Lokaler AI-Dienst wurde automatisch wiederhergestellt.")
                    except RuntimeError as error:
                        print(f"Lokaler AI-Dienst bleibt nicht verfügbar: {error}", file=sys.stderr)

                database_host, database_port = _database_endpoint(service_environment["DATABASE_URL"])
                if not _tcp_endpoint_available(database_host, database_port):
                    try:
                        _ensure_engineering_database(service_environment)
                        print("Engineering-Datenbank wurde automatisch wiederhergestellt.")
                    except RuntimeError as error:
                        print(f"Engineering-Datenbank bleibt nicht verfügbar: {error}", file=sys.stderr)

            time.sleep(0.5)
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
    if command == "doctor":
        checks = _run_dependency_doctor(_runtime_environment())
        _print_dependency_doctor(checks)
        return 0 if all(check.ok for check in checks if check.name != "Engineering-Datenbank-Port") else 1
    if command == "cli":
        arguments = arguments[1:]
    return _run_cli(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
