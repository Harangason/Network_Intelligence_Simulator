"""Scope persistence, canonical expansion and honest agent continuation."""
import asyncio

import pytest

from backend.engineering.models import EngineeringValidationError
from backend.engineering.simulation_scope import normalize_simulation_scope
from backend.engineering.simulation import _apply_simulation_scope
from backend.tests.test_model_ownership import db_project, _chain


def test_auto_observation_covers_slow_routes_and_preserves_explicit_duration():
    from backend.engineering.simulation import _apply_observation_duration
    config = {"duration_mode": "AUTO_OBSERVATION", "communications": [
        {"cycle_ms": 10, "jitter_limit_ms": 5, "maximum_latency_ms": 20},
        {"cycle_ms": 1000, "phase_ms": 50, "jitter_limit_ms": 5, "maximum_latency_ms": 20}]}
    _apply_observation_duration(config)
    assert config["duration_s"] == pytest.approx(1.071)
    explicit = {**config, "duration_s": 0.5}
    _apply_observation_duration(explicit)
    assert explicit["duration_s"] == 0.5
    manual = {"communications": [{"cycle_ms": 1000}], "duration_s": 1}
    _apply_observation_duration(manual)
    assert manual["duration_s"] == 1


def test_auto_observation_event_budget_covers_physical_routes():
    from backend.engineering.simulation import _apply_observation_duration
    config = {"duration_mode": "AUTO_OBSERVATION", "max_events": 1000, "communications": [
        *[{"cycle_ms": 10, "jitter_limit_ms": 5, "maximum_latency_ms": 20, "segments": [{}, {}]} for _ in range(150)],
        {"cycle_ms": 1000, "phase_ms": 50, "jitter_limit_ms": 5, "maximum_latency_ms": 20}]}
    _apply_observation_duration(config)
    assert config["max_events"] == 1000
    assert config["observation_window"]["minimum_release_event_count"] > config["max_events"]
    assert "OBSERVATION_EVENT_BUDGET_INSUFFICIENT" in [row["code"] for row in config["observation_window"]["warnings"]]


@pytest.mark.parametrize("cycle", [0, -1, float("nan"), float("inf"), 4_000_000])
def test_auto_observation_rejects_invalid_or_excessive_horizons(cycle):
    from backend.engineering.simulation import _apply_observation_duration
    config = {"duration_mode": "AUTO_OBSERVATION", "communications": [
        {"cycle_ms": cycle, "jitter_limit_ms": 5, "maximum_latency_ms": 20}]}
    if cycle == 4_000_000:
        with pytest.raises(EngineeringValidationError):
            _apply_observation_duration(config)
    else:
        _apply_observation_duration(config)
        assert config["observation_window"]["status"] == "UNVERIFIED"
        assert config["observation_window"]["warnings"][0]["code"] == "OBSERVATION_RELEASE_UNKNOWN"


def test_scope_normalization_and_mixed_expansion_preserve_full_inventory_counts():
    scope = normalize_simulation_scope({"mode": "SELECTED", "message_ids": ["m1", "m1"], "signal_ids": ["s2"], "reason": "Subsystemtest"}, require_reason=True)
    assert scope["message_ids"] == ["m1"]
    config = {"simulation_scope": scope, "engineering_model": {
        "messages": [{"id": "m1"}, {"id": "m2"}, {"id": "m3"}],
        "signals": [{"id": "s1", "message_id": "m1"}, {"id": "s2", "message_id": "m2"}, {"id": "s3", "message_id": "m3"}],
    }, "communications": [{"message_ids": ["m1"], "signal_ids": ["s1"]}, {"message_ids": ["m2"], "signal_ids": ["s2"]}]}
    _apply_simulation_scope(config)
    assert {row["id"] for row in config["engineering_model"]["signals"]} == {"s1", "s2"}
    assert config["scope_coverage"]["complete"]
    assert config["scope_coverage"]["total_messages"] == 3
    assert config["scope_coverage"]["excluded_messages"] == 1


@pytest.mark.parametrize("scope", [{"mode": "bad"}, {"mode": "SIGNAL", "signal_ids": []},
    {"mode": "MESSAGE", "message_ids": ["m1"]}, {"mode": "SIGNAL", "signal_ids": "s1"}])
def test_invalid_or_unexplained_scope_fails_closed(scope):
    with pytest.raises(EngineeringValidationError):
        normalize_simulation_scope(scope, require_reason=True)


def test_unknown_selected_id_is_not_silently_dropped():
    with pytest.raises(EngineeringValidationError, match="unbekannte"):
        _apply_simulation_scope({"simulation_scope": {"mode": "SIGNAL", "signal_ids": ["typo"]},
                                 "engineering_model": {"messages": [], "signals": []}, "communications": []})


@pytest.mark.parametrize(("scope", "expected"), [
    ({"mode": "SIGNAL", "signal_ids": ["s1"]}, {"pressure": ["s1"], "whole-message": ["s1"]}),
    ({"mode": "MESSAGE", "message_ids": ["m1"]},
        {"pressure": ["s1"], "temperature": ["s2"], "whole-message": ["s1", "s2"]}),
])
def test_signal_selection_does_not_activate_an_excluded_partial_route(scope, expected):
    from backend.simulator.model_based_simulation import ModelBasedSimulationEngine

    config = {"simulation_scope": {**scope, "reason": "Subsystem selection"}, "engineering_model": {
        "messages": [{"id": "m1"}],
        "signals": [{"id": "s1", "name": "Pressure", "message_id": "m1"},
                    {"id": "s2", "name": "Temperature", "message_id": "m1"}],
    }, "communications": [
        {"id": "pressure", "message_ids": ["m1"], "signal_ids": ["s1"]},
        {"id": "temperature", "message_ids": ["m1"], "signal_ids": ["s2"]},
        {"id": "whole-message", "message_ids": ["m1"]},
    ]}
    _apply_simulation_scope(config)
    engine = ModelBasedSimulationEngine(config)
    actual = {communication["id"]: sorted(signal.id for signal in engine.route_signals({"metadata": communication}))
              for communication in config["communications"]}
    assert actual == expected
    assert config["scope_coverage"]["complete"]


def test_excluded_partial_route_cannot_fill_missing_selected_signal_coverage():
    from backend.engineering.simulation_coverage import simulation_coverage

    scope = {"mode": "SIGNAL", "signal_ids": ["s1"], "reason": "Pressure only"}
    config = {"simulation_scope": scope, "engineering_model": {
        "messages": [{"id": "m1"}],
        "signals": [{"id": "s1", "message_id": "m1"}, {"id": "s2", "message_id": "m1"}],
    }, "communications": [{"message_ids": ["m1"], "signal_ids": ["s2"]}]}
    _apply_simulation_scope(config)
    assert config["communications"] == []
    coverage = simulation_coverage(config["engineering_model"]["messages"], config["engineering_model"]["signals"],
                                   config["communications"], scope)
    assert not coverage["complete"] and coverage["missing_signal_ids"] == ["s1"]


def test_scope_api_preserves_parameters_invalidates_preflight_and_is_idempotent(db_project, monkeypatch):
    from backend.app import create_app
    from backend.engineering.workflow.service import WorkflowStatusService
    import backend.engineering.api as api

    _sensor, _port, _interface, message, _signal = _chain()
    service = WorkflowStatusService(db_project)
    service.save_parameters({"industry": "automotive", "technology": "can_fd", "bitrate": 500000, "keep": "unchanged"})
    service.create_analysis_snapshot("preflight", input_data={}, provenance={}, status="APPROVED", results={}, findings=[])
    before = service.get()
    recalculated = []
    monkeypatch.setattr(api, "_auto_recalculate_capacity", lambda project: recalculated.append(project))
    client = create_app(testing=True).test_client()
    scope = {"mode": "MESSAGE", "message_ids": [str(message["id"])], "reason": "Nur AGR-Sensordaten im Subsystemtest"}
    def save(value):
        return client.patch("/api/engineering/workflow/simulation-scope", json={"simulation_scope": value}, headers={"X-Project-ID": db_project})
    response = save(scope)
    assert response.status_code == 200, response.get_json()
    state = response.get_json()
    assert state["parameters"]["keep"] == "unchanged"
    assert state["parameters"]["simulation_scope"] == normalize_simulation_scope(scope)
    assert state["versions"]["parameters"] == before["versions"]["parameters"] + 1
    assert state["statuses"]["validation"] == "OUTDATED"
    assert recalculated == [db_project]
    assert save(scope).get_json()["versions"]["parameters"] == state["versions"]["parameters"]
    assert recalculated == [db_project]
    assert save({**scope, "message_ids": ["missing"]}).status_code == 400
    assert save({**scope, "reason": ""}).status_code == 400
    assert service.get()["parameters"] == state["parameters"]
    service.save_parameters({"target_bus_load_percent": 60})
    assert service.get()["parameters"]["simulation_scope"] == normalize_simulation_scope(scope)


def test_snapshot_scope_uses_persisted_selection_and_full_canonical_inventory(db_project):
    from backend.engineering.repository import create_object
    from backend.engineering.workflow.service import WorkflowStatusService, WorkflowConflictError

    _sensor, port, interface, message, signal = _chain()
    create_object("Message", {"name": "OutsideSubsystem", "interface_id": str(interface["id"]),
                              "hardware_interface_id": str(port["id"]), "dlc": 8, "cycle_ms": 20})
    service = WorkflowStatusService(db_project)
    scope = normalize_simulation_scope({"mode": "MESSAGE", "message_ids": [str(message["id"])], "reason": "AGR-Subsystemtest"})
    service.save_parameters({"simulation_scope": scope})
    service.create_analysis_snapshot("preflight", input_data={}, provenance={}, status="APPROVED", results={}, findings=[])
    config = {"engineering_model": {"messages": [{"id": str(message["id"])}]},
              "communications": [{"message_ids": [str(message["id"])], "signal_ids": [str(signal["id"])]}],
              "scope_coverage": {"complete": True, "total_messages": 999}}
    with pytest.raises(WorkflowConflictError, match="weicht"):
        service.create_simulation_snapshot({**config, "scenario": {"simulation_scope": {"mode": "ALL"}}})
    snapshot = service.create_simulation_snapshot(config)
    frozen = snapshot["configuration"]
    assert frozen["simulation_scope"] == scope == frozen["scenario"]["simulation_scope"]
    assert frozen["scope_coverage"]["total_messages"] == 2
    assert frozen["scope_coverage"]["excluded_messages"] == 1
    assert frozen["scope_coverage"]["complete"]


def test_generic_parameter_scope_requires_reason_only_for_explicit_new_or_changed_selection(db_project):
    from psycopg.types.json import Jsonb
    from backend.engineering.db import get_connection
    from backend.engineering.workflow.service import WorkflowStatusService

    _sensor, _port, _interface, message, signal = _chain()
    service = WorkflowStatusService(db_project)
    service.save_parameters({"industry": "automotive", "technology": "can_fd", "bitrate": 500000})
    legacy = {"mode": "MESSAGE", "message_ids": [str(message["id"])], "selected_count": 1}
    with pytest.raises(EngineeringValidationError, match="begründen"):
        service.save_parameters({**service.get()["parameters"], "simulation_scope": legacy})
    assert "simulation_scope" not in service.get()["parameters"]
    # Seed an authentic pre-contract row; production writes cannot create it.
    with get_connection() as connection:
        connection.execute("UPDATE engineering_workflow_projects SET parameters = parameters || %s::jsonb WHERE project_id = %s",
                           (Jsonb({"simulation_scope": legacy}), db_project))
    inherited = service.save_parameters({"target_bus_load_percent": 60})
    assert inherited["parameters"]["simulation_scope"] == legacy
    repeated = service.save_parameters(inherited["parameters"])
    assert repeated["parameters"]["simulation_scope"] == legacy
    assert repeated["versions"]["parameters"] == inherited["versions"]["parameters"]
    changed = {"mode": "SIGNAL", "signal_ids": [str(signal["id"])]}
    with pytest.raises(EngineeringValidationError, match="begründen"):
        service.save_parameters({**repeated["parameters"], "simulation_scope": changed})
    assert service.get()["parameters"] == repeated["parameters"]
    changed["reason"] = "Einzelnes AGR-Signal separat untersuchen"
    saved = service.save_parameters({**repeated["parameters"], "simulation_scope": changed})
    assert saved["parameters"]["simulation_scope"] == normalize_simulation_scope(changed)
    restored = service.save_parameters({**saved["parameters"], "simulation_scope": {"mode": "ALL"}})
    assert restored["parameters"]["simulation_scope"]["include_all"] is True


@pytest.mark.parametrize('approved_counts', [False, True])
def test_applied_routing_with_missing_consumers_does_not_offer_repeat_approval(approved_counts):
    from backend.agent_core.api.tool_contract import ToolResult
    from backend.agent_core.context.agent_context import AgentContext
    from backend.agent_core.core.engineering_agent import EngineeringAgent

    calls = []
    class Client:
        async def call(self, name, arguments=None):
            calls.append(name)
            if name == "inspect_project":
                return ToolResult(data={"artifact_checks": {"engineering_model": {"complete": True}, "routing": {
                    "complete": False, "counts": {"total": 317, "approved": 317, "valid": 317} if approved_counts else {},
                    "coverage": {"complete": False, "missing_message_ids": ["ecu-status"], "missing_signal_ids": ["status"]}}}})
            if name == "generate_wizard_routing":
                return ToolResult(data={"status": "APPLIED", "proposal_id": "already-applied"})
            raise AssertionError(name)
    prompt = '''Strukturierte Vorgaben fuer den Engineering-Agenten:
- Hardware-Sollwerte: {"ecus":1}
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
Fortsetzung des bestätigten Wizard-Auftrags: Ziel: simulation.'''
    result = asyncio.run(EngineeringAgent(Client()).run(prompt, AgentContext(active_project_id="scope-test")))
    assert result["status"] == "INCOMPLETE"
    assert not result["proposals"]
    assert not any(event["type"] == "APPROVAL" for event in result["events"])
    assert "Empfänger" in result["text"] and "1 Nachrichten" in result["text"]
    assert calls == (["inspect_project"] if approved_counts else ["inspect_project", "generate_wizard_routing"])
