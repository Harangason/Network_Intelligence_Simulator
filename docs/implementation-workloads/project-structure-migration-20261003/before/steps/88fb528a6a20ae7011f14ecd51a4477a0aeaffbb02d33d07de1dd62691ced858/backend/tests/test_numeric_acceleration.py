from __future__ import annotations

import pytest

from backend.simulator import numeric_acceleration


def test_trace_statistics_cpu_fallback_is_exact_and_reproducible(monkeypatch) -> None:
    monkeypatch.setenv("NUMERIC_ACCELERATOR", "cpu")
    loads = {"drive-can": [10.0, 20.0, 30.0, 70.0], "body-can": [2.0, 4.0]}

    first, first_info = numeric_acceleration.trace_statistics([0.0, 3.0, 4.0], loads)
    second, second_info = numeric_acceleration.trace_statistics([0.0, 3.0, 4.0], loads)

    assert first == second
    assert first["changed_samples"] == 2
    assert first["rmse"] == pytest.approx(5 / 3**0.5)
    # Existing trace semantics include shortened trailing windows.
    assert first["burst_percent"] == pytest.approx(70.0)
    assert first_info == second_info
    assert first_info["backend"] == "python"
    assert first_info["accelerated"] is False
    assert first_info["deterministic"] is True


def test_grouped_route_statistics_keeps_capacity_contract_on_cpu(monkeypatch) -> None:
    monkeypatch.setenv("NUMERIC_ACCELERATOR", "cpu")
    groups = {
        "drive-can": [
            {"average_load_percent": 2.0, "peak_load_percent": 3.0, "burst_load_percent": 4.0, "end_to_end_latency_ms": 1.2},
            {"average_load_percent": 5.0, "peak_load_percent": 6.0, "burst_load_percent": 7.0, "end_to_end_latency_ms": 2.4},
        ]
    }

    result, info = numeric_acceleration.grouped_route_statistics(groups)

    assert result["drive-can"] == {
        "average_load_percent": 7.0,
        "peak_load_percent": 9.0,
        "burst_load_percent": 11.0,
        "worst_end_to_end_latency_ms": 2.4,
    }
    assert info["fallback_reason"] == "cpu-forced"


def test_auto_mode_falls_back_when_cupy_is_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("NUMERIC_ACCELERATOR", "auto")
    monkeypatch.setenv("NUMERIC_ACCELERATOR_MIN_ITEMS", "1")
    monkeypatch.setitem(__import__("sys").modules, "cupy", None)

    status = numeric_acceleration.acceleration_status(probe_items=1)

    assert status["backend"] == "python"
    assert status["accelerated"] is False
    assert "ModuleNotFoundError" in status["fallback_reason"]
