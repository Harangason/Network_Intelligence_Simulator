from __future__ import annotations

import importlib.util
import socket
from io import BytesIO
from pathlib import Path

import pytest

from backend.app import create_app
from backend.app.__main__ import ExclusiveThreadedWSGIServer, _server_settings


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


@pytest.mark.parametrize("value", ["0", "65536", "abc"])
def test_invalid_flask_port_is_rejected(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("FLASK_PORT", value)

    with pytest.raises(SystemExit):
        _server_settings()
