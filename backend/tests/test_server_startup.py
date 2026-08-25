from __future__ import annotations

import importlib.util
import socket
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

    assert response.get_json()["instance_id"] == "test-instance"


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
        "--turbopack",
        "-p",
        str(LAUNCHER.FRONTEND_PORT),
    ]


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
