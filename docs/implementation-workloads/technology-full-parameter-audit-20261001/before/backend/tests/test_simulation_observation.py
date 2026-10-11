"""Observation planning never changes confirmed transport requirements."""
from copy import deepcopy

import pytest

from backend.engineering.simulation_observation import (
    plan_observation_window, wizard_observation_request, mark_user_duration,
)
from backend.tests.test_model_ownership import db_project
from backend.tests.test_transport_integrity import gateway_config


def _config(*routes):
    return {"observation_window": {"mode": "AUTO_REQUIREMENTS"},
            "parameters": {"duration_s": 1, "parameter_provenance": {
                "duration_s": {"source": "TECHNOLOGY_DEFAULT", "value": 1}}},
            "communications": list(routes), "max_events": 100000,
            "scenario": {"mode": "NORMAL", "faults": []}}


def _route(identifier="washer", **values):
    return {"id": identifier, "routing_entry_id": "canonical-" + identifier,
            "cycle_ms": 1000, "phase_ms": 50, "jitter_limit_ms": 5,
            "maximum_latency_ms": 20, "transmission_contract": {"mode": "CYCLIC", "period_ms": 1000},
            **values}


def test_slow_lin_route_has_two_release_opportunities_plus_complete_delivery_window():
    config = _config(_route(), *[_route(corner, phase_ms=10) for corner in ["FL", "FR", "RL", "RR"]])
    before = deepcopy(config)
    planned = plan_observation_window(config)
    assert planned["duration_s"] == pytest.approx(1.071)
    assert planned["observation_window"]["requirement_minimum_duration_s"] == pytest.approx(1.071)
    assert planned["observation_window"]["source"] == "DERIVED_REQUIREMENTS"
    assert len(planned["observation_window"]["routes"]) == 5
    assert planned["communications"] == before["communications"]
    assert config == before


@pytest.mark.parametrize(("owner", "field", "value"), [
    ("config", "duration_s", 1), ("config", "duration", 0.2),
    ("scenario", "duration_s", 0.7), ("parameters", "duration_s", 1),
    ("parameters", "duration", 0.6),
])
def test_explicit_durations_remain_exact_even_when_too_short(owner, field, value):
    config = _config(_route())
    if owner == "parameters":
        config[owner] = {field: value, "defaults_source": "technology-registry"}
    elif owner == "config":
        config[field] = value
    else:
        config[owner][field] = value
    planned = plan_observation_window(config)
    assert planned["duration_s"] == value
    assert planned["observation_window"]["source"] == "EXPLICIT_" + owner.upper()
    assert "OBSERVATION_WINDOW_TOO_SHORT" in [row["code"] for row in planned["observation_window"]["warnings"]]


def test_manual_identical_duration_invalidates_a_copied_default_marker():
    parameters = _config()["parameters"]
    updated = mark_user_duration(parameters)
    assert updated["parameter_provenance"]["duration_s"] == {"source": "USER_PARAMETER", "value": 1}
    planned = plan_observation_window({**_config(_route()), "parameters": updated})
    assert planned["duration_s"] == 1
    assert parameters["parameter_provenance"]["duration_s"]["source"] == "TECHNOLOGY_DEFAULT"


def test_changed_parameter_does_not_inherit_an_old_default_marker():
    config = _config(_route())
    config["parameters"]["duration_s"] = 0.25
    assert plan_observation_window(config)["duration_s"] == 0.25


def test_first_physical_release_phase_not_later_gateway_phase_defines_observation():
    route = _route(network_id="source", phase_ms=0, segments=[
        {"network_id": "source", "phase_ms": 80, "segment_index": 0},
        {"network_id": "target", "phase_ms": 500, "segment_index": 1},
    ])
    assert plan_observation_window(_config(route))["duration_s"] == pytest.approx(1.101)


def test_runtime_cycle_is_authoritative_after_final_transmission_plan():
    route = _route(cycle_ms=2000, transmission_contract={"mode": "CYCLIC", "period_ms": 1000})
    assert plan_observation_window(_config(route))["duration_s"] == pytest.approx(2.071)


def test_missing_delivery_bound_and_noncyclic_data_never_claim_complete_observation():
    config = _config(_route(maximum_latency_ms=None), _route("event", transmission_contract={
        "mode": "EVENT", "trigger": "explicit", "minimum_interval_ms": 1000, "release_times_ms": []}))
    planned = plan_observation_window(config)
    assert planned["duration_s"] == 1
    assert planned["observation_window"]["status"] == "UNVERIFIED"
    assert {row["code"] for row in planned["observation_window"]["warnings"]} >= {
        "OBSERVATION_DELIVERY_BOUND_MISSING", "OBSERVATION_NONCYCLIC_JITTER"}
    assert planned["communications"] == config["communications"]


def test_event_budget_is_preserved_and_reported_as_insufficient():
    config = _config(_route())
    config["max_events"] = 1
    planned = plan_observation_window(config)
    assert planned["max_events"] == 1
    assert planned["observation_window"]["status"] == "UNVERIFIED"
    assert "OBSERVATION_EVENT_BUDGET_INSUFFICIENT" in [row["code"] for row in planned["observation_window"]["warnings"]]


def test_explicit_short_duration_survives_a_very_long_required_window():
    config = {**_config(_route(cycle_ms=4_000_000)), "duration_s": 1}
    planned = plan_observation_window(config)
    assert planned["duration_s"] == 1
    assert planned["observation_window"]["requirement_minimum_duration_s"] > 3600
    assert planned["observation_window"]["status"] == "UNVERIFIED"


@pytest.mark.parametrize("budget", [None, "invalid", 0, -1, 0.5, True, float("nan"), float("inf")])
def test_invalid_event_budget_fails_as_a_controlled_validation_error(budget):
    from backend.engineering.models import EngineeringValidationError
    with pytest.raises(EngineeringValidationError, match="Ereignisgrenze"):
        plan_observation_window({**_config(_route()), "max_events": budget})


def test_configured_worker_event_ceiling_is_the_actual_observation_limit(monkeypatch):
    monkeypatch.setenv("WORKFLOW_EVENT_LIMIT", "1")
    config = _config(_route())
    planned = plan_observation_window(config)
    assert planned["max_events"] == 100000
    assert planned["observation_window"]["effective_event_limit"] == 1
    assert planned["observation_window"]["status"] == "UNVERIFIED"


@pytest.mark.parametrize(("text", "duration"), [
    ("Simulationsdauer: 1,0 Sekunden", 1), ("Simulation duration: 250 ms", 0.25),
    ("Bitte simuliere für 2 Sekunden.", 2), ("Bitte fuer 3 s simulieren.", 3),
])
def test_explicit_request_duration_is_forwarded(text, duration):
    assert wizard_observation_request(text)["duration_s"] == duration


def test_unrelated_function_deadline_is_not_a_simulation_duration():
    assert "duration_s" not in wizard_observation_request("Simulation prüfen. Temperaturregelung für 20 ms auslegen.")


def test_conflicting_or_invalid_request_duration_is_not_silently_ignored():
    for text in ["Simulationsdauer: 0 s", "Simulationsdauer: 1 s\nSimulation duration: 2 seconds"]:
        with pytest.raises(ValueError):
            wizard_observation_request(text)


@pytest.mark.parametrize("existing_duration", [None, 1.0])
def test_registry_generation_marks_only_a_new_duration_default(db_project, monkeypatch, existing_duration):
    from backend.engineering.agent_tools import wizard_generation
    from backend.engineering.workflow.service import WorkflowStatusService
    workflow = WorkflowStatusService(db_project)
    parameters = {"spatial_zoning": {"enabled": False}, "communication_sizing": {"enabled": False},
                  "defaults_source": "technology-registry"}
    if existing_duration is not None:
        parameters["duration_s"] = existing_duration
    workflow.save_parameters(parameters)
    monkeypatch.setattr(wizard_generation, "_wizard_parameter_technology_ids", lambda _: ["lin"])
    generated = wizard_generation.generate_parameters({"prompt": "Technologie-Defaults verwenden."})["parameters"]
    if existing_duration is None:
        assert generated["parameter_provenance"]["duration_s"] == {"source": "TECHNOLOGY_DEFAULT", "value": 1}
        assert plan_observation_window({**_config(_route()), "parameters": generated})["duration_s"] == pytest.approx(1.071)
    else:
        assert "duration_s" not in generated.get("parameter_provenance", {})
        assert plan_observation_window({**_config(_route()), "parameters": generated})["duration_s"] == 1
    repeated = wizard_generation.generate_parameters({"prompt": "Technologie-Defaults verwenden."})["parameters"]
    assert repeated.get("parameter_provenance") == generated.get("parameter_provenance")


def test_dds_parameter_defaults_inherit_registered_ethernet_rate():
    from backend.engineering.agent_tools.wizard_generation import _parameter_defaults

    dds = _parameter_defaults("dds")
    ethernet = _parameter_defaults("ethernet")

    assert dds["bitrate"] == ethernet["bitrate"]
    assert dds["history_kind"] == "KEEP_LAST"


def test_mixed_robotics_defaults_are_complete_with_dds_as_primary(db_project, monkeypatch):
    from backend.engineering.agent_tools import wizard_generation
    from backend.engineering.workflow.service import WorkflowStatusService

    workflow = WorkflowStatusService(db_project)
    workflow.save_parameters({
        "spatial_zoning": {"enabled": False},
        "communication_sizing": {"enabled": False},
    })
    monkeypatch.setattr(
        wizard_generation,
        "_wizard_parameter_technology_ids",
        lambda _: ["dds", "ethercat", "ethernet", "can_fd"],
    )

    generated = wizard_generation.generate_parameters({
        "prompt": "- Projekt-Modelltyp: robotics_ros\nTechnologie-Defaults verwenden.",
    })

    assert generated["artifact_check"]["complete"]
    assert generated["parameters"]["technology"] == "dds"
    assert generated["parameters"]["bitrate"] > 0
    assert set(generated["technology_ids"]) == {"dds", "ethercat", "ethernet", "can_fd"}


def test_http_manual_identical_duration_cannot_retain_or_spoof_default_origin(db_project, monkeypatch):
    from backend.app import create_app
    from backend.engineering import api
    from backend.engineering.workflow.service import WorkflowStatusService
    workflow = WorkflowStatusService(db_project)
    parameters = _config()["parameters"]
    workflow.save_parameters(parameters, actor="engineering-agent")
    # Internal saves preserve origin; the public boundary owns explicit intent.
    workflow.save_parameters({**parameters, "target_bus_load_percent": 60}, actor="capacity")
    monkeypatch.setattr(api, "_auto_recalculate_capacity", lambda _: None)
    response = create_app(testing=True).test_client().patch(
        "/api/engineering/workflow/parameters", headers={"X-Project-ID": db_project},
        json={"parameters": parameters, "actor": "engineering-agent"},
    )
    assert response.status_code == 200, response.get_json()
    saved = workflow.get()["parameters"]
    assert saved["duration_s"] == 1
    assert saved["parameter_provenance"]["duration_s"] == {"source": "USER_PARAMETER", "value": 1}
    assert plan_observation_window({**_config(_route()), "parameters": saved})["duration_s"] == 1


def test_real_gateway_delivery_and_jitter_need_two_received_frames(gateway_config):
    from backend.app.runtime_analysis import analyze_runtime_trace
    from hardware_profile import normalize_hardware_config
    from universal_trace import generate_universal_events
    config = deepcopy(gateway_config)
    config.update(duration_s=1, max_events=100000, observation_window={"mode": "AUTO_REQUIREMENTS"})
    for message in config["engineering_model"]["messages"]:
        message["cycle_ms"] = 1000
    route = config["communications"][0]
    route.update(cycle_ms=1000, timeout_ms=3000, freshness_ms=3000,
                 transmission_contract={"mode": "CYCLIC", "period_ms": 1000})
    route["segments"][0]["phase_ms"] = 50
    def metrics(candidate):
        events = generate_universal_events(candidate, normalize_hardware_config(candidate), start_utc=1700000000)[1]
        return analyze_runtime_trace({"model_simulation": {"frames": events}}, candidate)["routes"][0]
    before = metrics(config)
    assert before["received_event_count"] == 1
    assert before["requirement_statuses"]["jitter"] == "NOT_EVALUATED"
    config.pop("duration_s")
    config.pop("duration", None)
    config["parameters"] = _config()["parameters"]
    planned = plan_observation_window(config)
    after = metrics(planned)
    assert planned["duration_s"] == pytest.approx(1.071)
    assert after["received_event_count"] >= 2 and after["status"] == "PASS"
    assert after["jitter_limit_ms"] == before["jitter_limit_ms"] == 5
    assert planned["communications"] == config["communications"]


def test_final_selected_scope_and_message_schedule_determine_the_window():
    from backend.engineering.capacity.runtime_plan import apply_runtime_plan
    from backend.engineering.simulation import _apply_simulation_scope, _apply_observation_duration
    config = _config(_route("selected", cycle_ms=10, message_ids=["selected-message"], network_id="net"),
                     _route("excluded", cycle_ms=9000, message_ids=["excluded-message"], network_id="net"))
    config["engineering_model"] = {
        "messages": [{"id": "selected-message", "cycle_ms": 1000, "dlc": 1},
                     {"id": "excluded-message", "cycle_ms": 9000, "dlc": 1}],
        "signals": [{"id": "selected-signal", "message_id": "selected-message"},
                    {"id": "excluded-signal", "message_id": "excluded-message"}],
    }
    config["simulation_scope"] = {"mode": "SIGNAL", "signal_ids": ["selected-signal"], "reason": "Subsystem"}
    config["parameters"]["communication_schedule"] = {"networks": [{"network_id": "net", "slots": [
        {"message_id": "selected-message", "route_ids": ["canonical-selected"], "period_ms": 1000, "offset_ms": 80}]}]}
    apply_runtime_plan(config, config["engineering_model"]["messages"])
    _apply_simulation_scope(config)
    _apply_observation_duration(config)
    assert len(config["communications"]) == 1
    assert config["communications"][0]["phase_ms"] == 80
    assert config["duration_s"] == pytest.approx(1.101)
