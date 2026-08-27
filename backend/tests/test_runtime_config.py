from __future__ import annotations

from backend.app.runtime_config import runtime_settings


def test_runtime_defaults_scale_for_workstation(monkeypatch) -> None:
    monkeypatch.setattr("backend.app.runtime_config.os.cpu_count", lambda: 32)
    for name in ("WAITRESS_THREADS", "SIMULATION_WORKERS", "SIMULATION_EXECUTOR"):
        monkeypatch.delenv(name, raising=False)

    settings = runtime_settings()

    assert settings.api_threads == 16
    assert settings.simulation_workers == 12
    assert settings.simulation_executor == "process"


def test_runtime_settings_are_bounded(monkeypatch) -> None:
    monkeypatch.setattr("backend.app.runtime_config.os.cpu_count", lambda: 8)
    monkeypatch.setenv("WAITRESS_THREADS", "999")
    monkeypatch.setenv("SIMULATION_WORKERS", "999")
    monkeypatch.setenv("SIMULATION_EXECUTOR", "invalid")

    settings = runtime_settings()

    assert settings.api_threads == 64
    assert settings.simulation_workers == 8
    assert settings.simulation_executor == "process"
