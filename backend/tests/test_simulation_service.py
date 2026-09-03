from __future__ import annotations

from backend.app.simulation_service import SimulationService


def test_workflow_simulation_caps_interactive_event_volume(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("WORKFLOW_EVENT_LIMIT", "75000")
    payload = {
        "workflow_managed": True,
        "config": {
            "technology": "can_fd",
            "max_events": 1_645_650,
        },
    }

    config = SimulationService().prepare_config(payload, tmp_path)

    assert config["max_events"] == 75_000


def test_standalone_simulation_keeps_explicit_event_volume(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("WORKFLOW_EVENT_LIMIT", "75000")
    payload = {
        "config": {
            "technology": "can_fd",
            "max_events": 250_000,
        },
    }

    config = SimulationService().prepare_config(payload, tmp_path)

    assert config["max_events"] == 250_000
