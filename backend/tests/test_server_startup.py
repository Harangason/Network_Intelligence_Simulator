from __future__ import annotations

import importlib.util
import json
import socket
import sys
from io import BytesIO
from pathlib import Path

import pytest
import psycopg

from backend.app import create_app
from backend.app.__main__ import ExclusiveThreadedWSGIServer, _server_settings
from backend.engineering import api as engineering_api
from backend.engineering import db as engineering_db
from backend.engineering import schema as engineering_schema


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER_SPEC = importlib.util.spec_from_file_location(
    "communication_simulator_launcher",
    ROOT / "generate_realistic_communication_tool.py",
)
assert LAUNCHER_SPEC and LAUNCHER_SPEC.loader
LAUNCHER = importlib.util.module_from_spec(LAUNCHER_SPEC)
LAUNCHER_SPEC.loader.exec_module(LAUNCHER)


class _RunningProcess:
    @staticmethod
    def poll() -> None:
        return None


class _JsonResponse(BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def test_health_exposes_launcher_instance_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIMULATOR_INSTANCE_ID", "test-instance")

    response = create_app(testing=True).test_client().get("/api/health")

    payload = response.get_json()
    assert payload["instance_id"] == "test-instance"
    assert payload["runtime"]["cpu"]["logical_cores"] >= 1
    assert payload["runtime"]["ai"]["local_model"]
    assert payload["jobs"]["max_workers"] >= 1


def test_launcher_rejects_an_occupied_port() -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.listen()
    try:
        with pytest.raises(SystemExit, match="bereits von einem anderen Prozess"):
            LAUNCHER._ensure_port_available("127.0.0.1", port, "Testdienst")
    finally:
        listener.close()


def test_readiness_check_rejects_a_foreign_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        LAUNCHER,
        "urlopen",
        lambda *_args, **_kwargs: _JsonResponse(b'{"instance_id":"foreign"}'),
    )

    assert not LAUNCHER._wait_for_url(
        "http://127.0.0.1/health",
        _RunningProcess(),
        timeout_s=0.01,
        expected_instance_id="ours",
    )


def test_readiness_check_accepts_its_own_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        LAUNCHER,
        "urlopen",
        lambda *_args, **_kwargs: _JsonResponse(b'{"instance_id":"ours"}'),
    )

    assert LAUNCHER._wait_for_url(
        "http://127.0.0.1/health",
        _RunningProcess(),
        timeout_s=0.01,
        expected_instance_id="ours",
    )


def test_launcher_command_timeout_kills_hung_child_process() -> None:
    result = LAUNCHER._run_command(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        timeout_s=0.2,
    )

    assert result.returncode == 124
    assert "Prozessbaum wurde beendet" in result.stdout


def test_backend_server_owns_its_port_exclusively() -> None:
    server = ExclusiveThreadedWSGIServer("127.0.0.1", 0, create_app(testing=True))
    competing_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(OSError):
            competing_socket.bind(("127.0.0.1", server.server_port))
    finally:
        competing_socket.close()
        server.server_close()


def test_frontend_dev_command_uses_local_next_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    next_cli = tmp_path / "node_modules" / "next" / "dist" / "bin" / "next"
    next_cli.parent.mkdir(parents=True)
    next_cli.write_text("", encoding="utf-8")
    monkeypatch.setattr(LAUNCHER.shutil, "which", lambda command: "node.exe")

    command = LAUNCHER._frontend_dev_command(tmp_path)

    assert command == [
        "node.exe",
        str(next_cli),
        "dev",
        "--webpack",
        "-p",
        str(LAUNCHER.FRONTEND_PORT),
    ]


def test_frontend_dev_server_uses_isolated_next_dist_dir(tmp_path: Path) -> None:
    frontend = tmp_path / "frontend"
    environment: dict[str, str] = {}

    dist_dir = LAUNCHER._prepare_frontend_dist_dir(frontend, environment, "abcdef123456")

    assert dist_dir == ".next-networkis"
    assert environment["NETWORKIS_NEXT_DIST_DIR"] == ".next-networkis"


def test_frontend_dev_server_reports_unwritable_project_dist_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frontend = tmp_path / "frontend"
    environment: dict[str, str] = {}

    monkeypatch.setattr(LAUNCHER, "_can_write_file", lambda _path: False)

    with pytest.raises(RuntimeError, match="relativen beschreibbaren Build-Ordner"):
        LAUNCHER._prepare_frontend_dist_dir(frontend, environment, "abcdef123456")

    assert "NETWORKIS_NEXT_DIST_DIR" not in environment


def test_backend_runtime_root_falls_back_when_project_runtime_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(LAUNCHER, "ROOT", tmp_path)
    monkeypatch.setattr(LAUNCHER, "_can_write_file", lambda _path: False)
    monkeypatch.setattr(LAUNCHER.tempfile, "gettempdir", lambda: str(tmp_path / "temp"))
    environment: dict[str, str] = {}

    fallback = LAUNCHER._prepare_backend_runtime_root(environment, "abcdef123456")

    assert fallback == tmp_path / "temp" / "networkis-runtime" / "abcdef12"
    assert environment["SIMULATOR_RUNTIME_ROOT"] == str(fallback)


def test_runtime_environment_uses_hybrid_demand_ai_and_thread_workers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "AI_PROVIDER",
        "LOCAL_AI_BASE_URL",
        "LOCAL_AI_MODEL",
        "LOCAL_AI_FAST_MODEL",
        "CLOUD_ESCALATION",
        "OLLAMA_MODELS",
        "OLLAMA_CONTEXT_LENGTH",
        "OLLAMA_KEEP_ALIVE",
        "NETWORKIS_SHARED_ENV_FILE",
        "WAITRESS_THREADS",
        "SIMULATION_WORKERS",
        "SIMULATION_EXECUTOR",
        "WORKFLOW_EVENT_LIMIT",
        "DATABASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(LAUNCHER.os, "cpu_count", lambda: 32)

    environment = LAUNCHER._runtime_environment()

    assert environment["AI_PROVIDER"] == "hybrid-demand"
    assert environment["LOCAL_AI_MODEL"] == "qwen3.8:27b"
    assert environment["LOCAL_AI_FAST_MODEL"] == "llama3.1:8b"
    assert environment["CLOUD_ESCALATION"] == "on_failure"
    assert environment["OLLAMA_CONTEXT_LENGTH"] == "8192"
    assert environment["WAITRESS_THREADS"] == "16"
    assert environment["SIMULATION_WORKERS"] == "12"
    assert environment["SIMULATION_EXECUTOR"] == "thread"
    assert environment["WORKFLOW_EVENT_LIMIT"] == "100000"
    assert environment["OMP_NUM_THREADS"] == "1"
    assert environment["DATABASE_URL"] == LAUNCHER.DEFAULT_DATABASE_URL


def test_runtime_environment_uses_persisted_resource_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "simulator"
    project_root.mkdir()
    config_dir = project_root / "config"
    config_dir.mkdir()
    (config_dir / "networkis.resources.json").write_text(
        """
        {
          "paths": {"ollama_models": "X:\\\\models\\\\ollama"},
          "resources": {
            "waitress_threads": 10,
            "simulation_workers": 6,
            "simulation_executor": "thread",
            "workflow_event_limit": 75000,
            "service_restarts": 2,
            "numeric_threads": 2,
            "ollama_context_length": 4096,
            "ollama_keep_alive": "5m"
          },
          "ai": {
            "active_provider": "local",
            "cloud_escalation": "never",
            "providers": {
              "ollama": {
                "base_url_windows": "http://127.0.0.1:11434/v1",
                "model": "llama3.1:8b",
                "fast_model": "llama3.1:8b",
                "api_key": "ollama"
              },
              "nvidia": {"model": "nvidia/test"}
            }
          }
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(LAUNCHER, "ROOT", project_root)
    monkeypatch.setattr(LAUNCHER, "RUNTIME_CONFIG_FILE", config_dir / "networkis.resources.json")
    for name in (
        "AI_PROVIDER",
        "LOCAL_AI_BASE_URL",
        "LOCAL_AI_MODEL",
        "LOCAL_AI_FAST_MODEL",
        "LOCAL_AI_API_KEY",
        "CLOUD_ESCALATION",
        "OLLAMA_MODELS",
        "OLLAMA_CONTEXT_LENGTH",
        "OLLAMA_KEEP_ALIVE",
        "WAITRESS_THREADS",
        "SIMULATION_WORKERS",
        "SIMULATION_EXECUTOR",
        "WORKFLOW_EVENT_LIMIT",
        "NETWORKIS_SERVICE_RESTARTS",
        "OMP_NUM_THREADS",
    ):
        monkeypatch.delenv(name, raising=False)

    environment = LAUNCHER._runtime_environment()

    assert environment["AI_PROVIDER"] == "local"
    assert environment["LOCAL_AI_MODEL"] == "llama3.1:8b"
    assert environment["WAITRESS_THREADS"] == "10"
    assert environment["SIMULATION_WORKERS"] == "6"
    assert environment["SIMULATION_EXECUTOR"] == "thread"
    assert environment["WORKFLOW_EVENT_LIMIT"] == "75000"
    assert environment["NETWORKIS_SERVICE_RESTARTS"] == "2"
    assert environment["OLLAMA_MODELS"] == "X:\\models\\ollama"
    assert environment["OLLAMA_CONTEXT_LENGTH"] == "4096"
    assert environment["OMP_NUM_THREADS"] == "2"


def test_docker_probe_uses_persisted_docker_cli_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    docker = tmp_path / "docker.exe"
    docker.write_text("", encoding="utf-8")
    config_file = tmp_path / "networkis.resources.json"
    config_file.write_text(
        json.dumps({"paths": {"docker_cli": str(docker)}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(LAUNCHER, "RUNTIME_CONFIG_FILE", config_file)
    monkeypatch.setattr(LAUNCHER.shutil, "which", lambda _command: None)
    monkeypatch.setattr(
        LAUNCHER,
        "_run_command",
        lambda args, **_kwargs: LAUNCHER.subprocess.CompletedProcess(args, 0, "ok"),
    )

    probe = LAUNCHER._docker_probe()

    assert probe.available
    assert probe.executable == str(docker)


def test_launcher_rejects_non_canonical_project_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(LAUNCHER, "ROOT", tmp_path)
    monkeypatch.setattr(LAUNCHER, "CANONICAL_ROOT", tmp_path / "canonical")
    monkeypatch.delenv("NETWORKIS_ALLOW_NON_CANONICAL_ROOT", raising=False)

    with pytest.raises(SystemExit, match="Falscher Simulator-Projektpfad"):
        LAUNCHER._assert_canonical_project_root()


def test_launcher_can_explicitly_allow_diagnostic_project_copy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(LAUNCHER, "ROOT", tmp_path)
    monkeypatch.setattr(LAUNCHER, "CANONICAL_ROOT", tmp_path / "canonical")
    monkeypatch.setenv("NETWORKIS_ALLOW_NON_CANONICAL_ROOT", "1")

    LAUNCHER._assert_canonical_project_root()


def test_runtime_environment_loads_local_env_without_overwriting_process_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / ".env.local").write_text(
        "OPENAI_API_KEY=file-key\nAI_PROVIDER=hybrid\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(LAUNCHER, "ROOT", tmp_path)
    monkeypatch.setenv("AI_PROVIDER", "local")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    environment = LAUNCHER._runtime_environment()

    assert environment["OPENAI_API_KEY"] == "file-key"
    assert environment["AI_PROVIDER"] == "local"


def test_runtime_environment_replaces_invalid_process_api_key_placeholder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / ".env.local").write_text(
        "OPENAI_API_KEY=file-key-with-sufficient-length\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(LAUNCHER, "ROOT", tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "placeholder")

    environment = LAUNCHER._runtime_environment()

    assert environment["OPENAI_API_KEY"] == "file-key-with-sufficient-length"


def test_runtime_environment_prefers_shared_openai_organization_alias(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "simulator"
    project_root.mkdir()
    (project_root / ".env.local").write_text(
        "OPENAI_API_KEY=project-key-with-sufficient-length\n",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "OPEN_AI_KEY=organization-key-with-sufficient-length\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(LAUNCHER, "ROOT", project_root)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPEN_AI_KEY", raising=False)

    environment = LAUNCHER._runtime_environment()

    assert environment["OPENAI_API_KEY"] == "organization-key-with-sufficient-length"


def test_runtime_environment_loads_shared_parent_env_as_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "simulator"
    project_root.mkdir()
    (tmp_path / ".env").write_text(
        "NVIDIA_API_KEY=shared-nvidia-key\nLOCAL_AI_MODEL=shared-model\n",
        encoding="utf-8",
    )
    (project_root / ".env.local").write_text(
        "LOCAL_AI_MODEL=project-model\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(LAUNCHER, "ROOT", project_root)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("LOCAL_AI_MODEL", raising=False)

    environment = LAUNCHER._runtime_environment()

    assert environment["NVIDIA_API_KEY"] == "shared-nvidia-key"
    assert environment["LOCAL_AI_MODEL"] == "project-model"


def test_runtime_environment_loads_explicit_shared_env_after_project_move(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "moved" / "simulator"
    project_root.mkdir(parents=True)
    shared_env = tmp_path / "original-location.env"
    shared_env.write_text(
        "OPEN_AI_KEY=organization-key-after-project-move\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(LAUNCHER, "ROOT", project_root)
    monkeypatch.setenv("NETWORKIS_SHARED_ENV_FILE", str(shared_env))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPEN_AI_KEY", raising=False)

    environment = LAUNCHER._runtime_environment()

    assert environment["OPENAI_API_KEY"] == "organization-key-after-project-move"


def test_ollama_model_matching_accepts_latest_alias() -> None:
    assert LAUNCHER._model_is_installed("qwen3.8", ["qwen3.8:latest"])


def test_hybrid_demand_checks_local_ollama_model(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(LAUNCHER, "ROOT", tmp_path)
    monkeypatch.setattr(LAUNCHER, "_ollama_models", lambda _environment: ["qwen3.8:27b"])

    owned_process = LAUNCHER._ensure_local_ai(
        {"AI_PROVIDER": "hybrid-demand", "LOCAL_AI_MODEL": "qwen3.8:27b"},
        None,
    )

    assert owned_process is None
    assert LAUNCHER._service_restart_limit({}) == 5


def test_missing_fast_model_falls_back_to_deep_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(LAUNCHER, "_ollama_models", lambda _environment: ["qwen3.8:27b"])
    environment = {
        "AI_PROVIDER": "hybrid-demand",
        "LOCAL_AI_MODEL": "qwen3.8:27b",
        "LOCAL_AI_FAST_MODEL": "missing:8b",
    }

    assert LAUNCHER._ensure_local_ai(environment, None) is None
    assert environment["LOCAL_AI_FAST_MODEL"] == "qwen3.8:27b"


def test_service_restart_limit_rejects_invalid_values() -> None:
    with pytest.raises(RuntimeError, match="ganze Zahl"):
        LAUNCHER._service_restart_limit({"NETWORKIS_SERVICE_RESTARTS": "many"})
    with pytest.raises(RuntimeError, match="nicht negativ"):
        LAUNCHER._service_restart_limit({"NETWORKIS_SERVICE_RESTARTS": "-1"})


def test_docker_inference_failure_is_actionable() -> None:
    probe = LAUNCHER.DockerProbe(
        False,
        "docker",
        "starting services: initializing Inference manager: listening on dockerInference: remove dockerInference: file is locked",
    )

    message = LAUNCHER._docker_unavailable_message(probe)

    assert "Engineering-Datenbank" in message
    assert "dockerInference" in message
    assert "Inference-Manager" in message
    assert "repariert oder deaktiviert" in message


def test_engineering_database_start_reports_docker_inference_blocker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    compose_file = tmp_path / "docker-compose.engineering-db.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setattr(LAUNCHER, "ROOT", tmp_path)
    monkeypatch.setattr(LAUNCHER, "_tcp_endpoint_available", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        LAUNCHER,
        "_docker_probe",
        lambda *_args, **_kwargs: LAUNCHER.DockerProbe(
            False,
            "docker",
            "starting services: initializing Inference manager: listening on dockerInference: remove dockerInference: file is locked",
        ),
    )
    monkeypatch.setattr(
        LAUNCHER,
        "_try_start_docker_desktop",
        lambda: pytest.fail("Known actionable Docker failures must not enter auto-start."),
    )
    monkeypatch.setattr(
        LAUNCHER,
        "_wait_for_docker",
        lambda *_args, **_kwargs: LAUNCHER.DockerProbe(
            False,
            "docker",
            "failed to connect to dockerDesktopLinuxEngine",
        ),
    )

    with pytest.raises(RuntimeError, match="dockerInference"):
        LAUNCHER._ensure_engineering_database({"DATABASE_URL": LAUNCHER.DEFAULT_DATABASE_URL})


def test_dependency_doctor_surfaces_docker_failure_without_starting_services(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frontend_next = tmp_path / "frontend" / "node_modules" / "next" / "dist" / "bin" / "next"
    frontend_next.parent.mkdir(parents=True)
    frontend_next.write_text("", encoding="utf-8")
    monkeypatch.setattr(LAUNCHER, "ROOT", tmp_path)
    monkeypatch.setattr(LAUNCHER, "CANONICAL_ROOT", tmp_path)
    monkeypatch.setattr(LAUNCHER, "_tcp_endpoint_available", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        LAUNCHER,
        "_docker_probe",
        lambda *_args, **_kwargs: LAUNCHER.DockerProbe(False, "docker", "permission denied while trying to connect to docker_engine"),
    )

    checks = LAUNCHER._run_dependency_doctor({"DATABASE_URL": LAUNCHER.DEFAULT_DATABASE_URL})

    docker = next(check for check in checks if check.name == "Docker Engine")
    assert not docker.ok
    assert "Docker Engine" in docker.hint


def test_engineering_database_url_accepts_sqlalchemy_psycopg_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/db")

    assert engineering_db._database_url() == "postgresql://user:pass@localhost/db"


def test_engineering_database_timeout_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENGINEERING_DB_TIMEOUT", "0")

    with pytest.raises(RuntimeError, match="größer als 0"):
        engineering_db._timeout_seconds("ENGINEERING_DB_TIMEOUT", 2.0)


def test_engineering_missing_tables_return_service_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_missing_table(*_args, **_kwargs):
        raise psycopg.errors.UndefinedTable("missing engineering table")

    monkeypatch.setattr(engineering_api, "list_objects", raise_missing_table)
    client = create_app(testing=False).test_client()

    response = client.get("/api/engineering/hardware-nodes")

    assert response.status_code == 503
    assert "Engineering-Datenbank" in response.get_json()["error"]


def test_direct_ai_object_write_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        engineering_api,
        "create_object",
        lambda *_args, **_kwargs: pytest.fail("repository must not be called"),
    )
    response = create_app(testing=True).test_client().post(
        "/api/engineering/hardware-nodes",
        json={"name": "AI Node", "source": "ai_generated"},
    )

    assert response.status_code == 409
    assert "AIProposal" in response.get_json()["error"]


def test_direct_approval_write_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        engineering_api,
        "update_object",
        lambda *_args, **_kwargs: pytest.fail("repository must not be called"),
    )
    response = create_app(testing=True).test_client().patch(
        "/api/engineering/hardware-nodes/00000000-0000-0000-0000-000000000000",
        json={"approval_state": "approved"},
    )

    assert response.status_code == 409
    assert "Approval-Service" in response.get_json()["error"]


def test_schema_contains_phase_one_and_proposal_tables() -> None:
    ddl = "\n".join(engineering_schema.MIGRATION_STATEMENTS)

    assert "engineering_hardware_nodes" in ddl
    assert "engineering_signals" in ddl
    assert "engineering_relations" in ddl
    assert "engineering_object_versions" in ddl
    assert "engineering_ai_proposals" in ddl


@pytest.mark.parametrize("value", ["0", "65536", "abc"])
def test_invalid_flask_port_is_rejected(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("FLASK_PORT", value)

    with pytest.raises(SystemExit):
        _server_settings()
