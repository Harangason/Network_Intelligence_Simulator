from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.runtime_analysis import analyze_runtime_trace
from backend.engineering import simulation as engineering_simulation
from backend.engineering.models import EngineeringValidationError
from backend.engineering.simulation import validate_scenario
from communication_simulator import run_simulation
from hardware_profile import normalize_hardware_config
from model_based_simulation import (
    BEHAVIOR_TYPES,
    MESSAGE_FAULTS,
    NETWORK_FAULTS,
    SIGNAL_FAULTS,
    FaultInjectionEngine,
    FaultCatalog,
    MessageCodec,
    ModelBasedSimulationEngine,
    SignalBehaviorEngine,
    SignalDefinition,
    build_model_trace,
    demo_scenarios,
)
from universal_trace import generate_universal_events


def signal_record(**overrides):
    return {
        "id": "sig-temperature",
        "name": "Temperature",
        "message_id": "msg-1",
        "start_bit": 0,
        "length_bits": 16,
        "byte_order": "little_endian",
        "factor": 0.1,
        "offset_value": -40,
        "unit": "degC",
        "min_value": -40,
        "max_value": 215,
        "communication": {"cycle_ms": 10},
        "configuration": {"resolution": 0.1},
        **overrides,
    }


def definition(**overrides):
    return SignalDefinition.from_record(signal_record(**overrides), {"cycle_ms": 10})


def simulation_config(tmp_path: Path, *, faults=None, seed=42):
    return {
        "name": "model-test",
        "output_dir": str(tmp_path),
        "duration_s": 0.08,
        "seed": seed,
        "max_events": 1000,
        "formats": ["universal-jsonl", "universal-csv"],
        "networks": [{"id": "can-main", "technology": "can_fd", "bitrate": 2_000_000}],
        "hardware": {
            "devices": [
                {"id": "sensor", "name": "Sensor", "type": "sensor", "ports": [{"id": "p1", "physical_type": "can", "network_interfaces": [{"id": "if-sensor", "technology": "can_fd", "network": "can-main"}]}]},
                {"id": "ecu", "name": "ECU", "type": "ecu", "ports": [{"id": "p2", "physical_type": "can", "network_interfaces": [{"id": "if-ecu", "technology": "can_fd", "network": "can-main"}]}]},
            ]
        },
        "communications": [{
            "id": "route-temperature", "sender_interface": "if-sensor",
            "receiver_interfaces": ["if-ecu"], "network": "can-main",
            "technology": "can_fd", "cycle_ms": 10, "payload_bytes": 8,
            "signal_ids": ["sig-temperature"],
        }],
        "engineering_model": {
            "messages": [{"id": "msg-1", "name": "TemperatureMessage", "cycle_ms": 10, "interface_id": "if-sensor"}],
            "signals": [signal_record()],
            "behaviors": [{"signal_id": "sig-temperature", "behavior_type": "SINE", "model_label": "RULE_BASED", "parameters": {"period_s": 1}}],
        },
        "scenario": {"name": "Fault run" if faults else "Golden run", "mode": "USER_DEFINED_FAULT" if faults else "NORMAL", "faults": faults or []},
    }


@pytest.mark.parametrize("behavior_type", BEHAVIOR_TYPES)
def test_all_required_behavior_models_are_bounded_and_deterministic(behavior_type: str) -> None:
    params = {"behavior_type": behavior_type, "model_label": "SYNTHETIC", "period_s": 1}
    if behavior_type == "FORMULA":
        params["formula"] = "mid + 5 * sin(t)"
    if behavior_type in {"LOOKUP_TABLE", "EXTERNAL_SERIES"}:
        params["points"] = [{"time_s": 0, "value": 20}, {"time_s": 1, "value": 30}]
    signal = definition(behavior={"behavior_type": behavior_type, "parameters": params})
    left = SignalBehaviorEngine([signal], seed=77).sample(signal, 0.2)
    right = SignalBehaviorEngine([signal], seed=77).sample(signal, 0.2)
    assert signal.minimum <= left <= signal.maximum
    assert left == right


def test_message_codec_encodes_engineering_factor_offset_and_start_bit() -> None:
    signal = definition()
    payload = MessageCodec.encode([(signal, 42.5)], 8)
    assert MessageCodec.decode(payload, signal) == pytest.approx(42.5)
    assert payload != "00 00 00 00 00 00 00 00"


@pytest.mark.parametrize("fault_type", SIGNAL_FAULTS)
def test_signal_fault_catalog_is_executable(fault_type: str) -> None:
    signal = definition()
    behavior = SignalBehaviorEngine([signal], seed=11)
    engine = FaultInjectionEngine([{"scope": "SIGNAL", "type": fault_type, "target": {"id": signal.id}, "magnitude": 5}], seed=11)
    value, applied = engine.signal_value(signal, 0.5, 20.0, behavior)
    assert fault_type in applied
    assert value != 20.0 or fault_type in {"SIGNAL_STUCK", "SIGNAL_FROZEN", "SIGNAL_DELAYED"}


@pytest.mark.parametrize("fault_type", MESSAGE_FAULTS + NETWORK_FAULTS)
def test_transport_fault_catalog_is_executable(fault_type: str) -> None:
    scope = "MESSAGE" if fault_type in MESSAGE_FAULTS else "NETWORK"
    target = "route-1" if scope == "MESSAGE" else "network-1"
    engine = FaultInjectionEngine([{"scope": scope, "type": fault_type, "target": {"id": target}}], seed=5)
    event = {"route_id": "route-1", "route_name": "Route", "network": "network-1", "scheduled_time_s": 0.2, "status": "transmitted", "payload_hex": "00", "configured_latency_ms": 0, "configured_cycle_ms": 10}
    assert fault_type in engine.event_faults(event)


def test_same_seed_produces_byte_identical_signal_trace(tmp_path: Path) -> None:
    config = simulation_config(tmp_path / "one", seed=123)
    profile = normalize_hardware_config(config)
    _, first = generate_universal_events(config, profile, start_utc=1_700_000_000)
    _, second = generate_universal_events(config, profile, start_utc=1_700_000_000)
    assert first == second


def test_different_seed_changes_stochastic_trace(tmp_path: Path) -> None:
    first_config = simulation_config(tmp_path / "one", seed=1)
    first_config["engineering_model"]["behaviors"][0]["behavior_type"] = "BOUNDED_RANDOM"
    second_config = simulation_config(tmp_path / "two", seed=2)
    second_config["engineering_model"]["behaviors"][0]["behavior_type"] = "BOUNDED_RANDOM"
    first_profile = normalize_hardware_config(first_config)
    second_profile = normalize_hardware_config(second_config)
    _, first = generate_universal_events(first_config, first_profile, start_utc=1_700_000_000)
    _, second = generate_universal_events(second_config, second_profile, start_utc=1_700_000_000)
    assert [event["value"] for event in first] != [event["value"] for event in second]


def test_model_run_writes_decoded_golden_fault_and_comparison_artifacts(tmp_path: Path) -> None:
    fault = {"scope": "SIGNAL", "type": "OFFSET", "target": {"id": "sig-temperature"}, "magnitude": 12, "start_s": 0}
    config = simulation_config(tmp_path, faults=[fault])
    result = run_simulation(config)
    paths = {Path(path).name for path in result["artifacts"]}
    assert {"universal_trace.jsonl", "universal_trace.csv", "model_trace.json", "golden_trace.jsonl", "fault_trace.jsonl"} <= paths
    assert result["model_simulation"]["comparison"]["changed_samples"] > 0
    assert result["model_simulation"]["signals"][0]["model_label"] == "RULE_BASED"
    assert len(result["model_simulation"]["frames"]) == result["trace"]["events"]
    assert result["model_simulation"]["bus_load"]
    event = json.loads((tmp_path / "traces" / "universal_trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert event["signal"] == "Temperature"
    assert event["value"] != event["golden_value"]
    assert event["payload_hex"] != ""


def test_fresh_job_directory_writes_model_trace_without_universal_format(tmp_path: Path) -> None:
    config = simulation_config(tmp_path)
    config["formats"] = ["json", "csv"]

    result = run_simulation(config)

    assert result["status"] == "completed"
    assert (tmp_path / "traces" / "model_trace.json").is_file()
    metrics = analyze_runtime_trace(result, config)
    assert metrics["available"] is True
    assert metrics["trace_source"] == "model_simulation.frames"


def test_project_enrichment_reconstructs_transport_config_server_side(monkeypatch) -> None:
    model = {
        "signals": [], "messages": [], "routes": [{"id": "route-1", "approval_state": "APPROVED"}],
        "nodes": [], "functions": [], "interfaces": [], "behaviors": [],
    }
    monkeypatch.setattr(engineering_simulation, "load_engineering_simulation_model", lambda _project_id: model)
    monkeypatch.setattr(
        engineering_simulation,
        "_load_project_transport_config",
        lambda _project_id, _routes: {
            "networks": [{"id": "network-1"}],
            "hardware": {"devices": [{"id": "node-a"}, {"id": "node-b"}]},
            "communications": [{"id": "route-1", "source": "node-a", "target": "node-b"}],
            "routing_entry_ids": ["route-1"],
        },
    )
    monkeypatch.setattr(
        "backend.engineering.workflow.service.WorkflowStatusService.get",
        lambda _self: {"topology": {"nodes": []}, "parameters": {"industry": "automotive"}},
    )

    enriched = engineering_simulation.enrich_simulation_config({"duration_s": 2}, "project-1")

    assert enriched["communications"][0]["id"] == "route-1"
    assert enriched["routing_entry_ids"] == ["route-1"]
    assert enriched["parameters"]["industry"] == "automotive"


def test_runtime_load_is_derived_from_transmitted_frames(tmp_path: Path) -> None:
    config = simulation_config(tmp_path)
    result = run_simulation(config)
    metrics = analyze_runtime_trace(result, config)
    assert metrics["available"] is True
    assert metrics["networks"][0]["event_count"] == result["trace"]["events"]
    assert metrics["networks"][0]["average_load_percent"] > 0
    assert metrics["networks"][0]["peak_load_percent"] >= metrics["networks"][0]["average_load_percent"]


def test_engine_uses_min_max_unit_resolution_and_cycle() -> None:
    engine = ModelBasedSimulationEngine({
        "seed": 9,
        "engineering_model": {"messages": [{"id": "msg-1", "cycle_ms": 25}], "signals": [signal_record(min_value=10, max_value=20, unit="km/h", factor=0.25)]},
    })
    signal = engine.signals[0]
    assert (signal.minimum, signal.maximum, signal.unit, signal.resolution, signal.cycle_ms) == (10, 20, "km/h", 0.25, 10)


def test_ai_fault_cannot_be_activated_without_review() -> None:
    with pytest.raises(EngineeringValidationError, match="expliziter Annahme"):
        validate_scenario({"mode": "AI_GENERATED_FAULT", "faults": [{"scope": "SIGNAL", "type": "NOISE", "source": "ai"}]})
    reviewed = validate_scenario({"mode": "AI_GENERATED_FAULT", "faults": [{"scope": "SIGNAL", "type": "NOISE", "source": "ai", "approved": True}]})
    assert reviewed["faults"][0]["approved"] is True


def test_cycle_time_and_resolution_are_visible_in_generated_trace(tmp_path: Path) -> None:
    config = simulation_config(tmp_path)
    profile = normalize_hardware_config(config)
    _, events = generate_universal_events(config, profile, start_utc=1_700_000_000)
    scheduled = [event["scheduled_time_s"] for event in events[:4]]
    assert scheduled == pytest.approx([0.0, 0.01, 0.02, 0.03])
    assert all(round(event["value"] / 0.1) * 0.1 == pytest.approx(event["value"]) for event in events)


def test_fault_starts_and_ends_at_configured_time() -> None:
    signal = definition()
    behavior = SignalBehaviorEngine([signal], seed=4)
    engine = FaultInjectionEngine([{"scope": "SIGNAL", "type": "SIGNAL_OFFSET", "target": {"id": signal.id}, "start_s": 0.2, "end_s": 0.4, "magnitude": 10}], seed=4)
    before, _ = engine.signal_value(signal, 0.19, 20.0, behavior)
    active, applied = engine.signal_value(signal, 0.3, 20.0, behavior)
    after, _ = engine.signal_value(signal, 0.41, 20.0, behavior)
    assert before == 20.0
    assert active == 30.0 and applied == ["SIGNAL_OFFSET"]
    assert after == 20.0


def test_fault_modifies_only_target_signal() -> None:
    target = definition()
    other = definition(id="sig-other", name="Other")
    behavior = SignalBehaviorEngine([target, other], seed=4)
    engine = FaultInjectionEngine([{"scope": "SIGNAL", "type": "SIGNAL_OFFSET", "target": {"id": target.id}, "magnitude": 7}], seed=4)
    target_value, _ = engine.signal_value(target, 0.2, 20.0, behavior)
    other_value, other_faults = engine.signal_value(other, 0.2, 20.0, behavior)
    assert target_value == 27.0
    assert other_value == 20.0 and other_faults == []


def test_formula_dependency_reacts_consistently() -> None:
    rpm = definition(id="rpm", name="MotorRPM", min_value=0, max_value=5000, factor=50, behavior={"behavior_type": "CONSTANT", "parameters": {"value": 3000}})
    current = definition(id="current", name="MotorCurrent", min_value=0, max_value=100, factor=0.1, behavior={"behavior_type": "FORMULA", "dependencies": ["MotorRPM"], "parameters": {"formula": "MotorRPM * 0.02"}})
    engine = SignalBehaviorEngine([rpm, current], seed=3)
    values = {"MotorRPM": engine.sample(rpm, 0.1)}
    assert engine.sample(current, 0.1, values) == pytest.approx(60.0)


def test_signed_big_endian_message_roundtrip() -> None:
    signal = definition(min_value=-100, max_value=100, factor=1, offset_value=0, data_type="int16", byte_order="big_endian", length_bits=16)
    payload = MessageCodec.encode([(signal, -25)], 2)
    assert payload == "FF E7"
    assert MessageCodec.decode(payload, signal) == -25


def test_normal_mode_suppresses_intentional_transport_faults(tmp_path: Path) -> None:
    config = simulation_config(tmp_path)
    config["dropout_probability"] = 1.0
    profile = normalize_hardware_config(config)
    _, events = generate_universal_events(config, profile, start_utc=1_700_000_000)
    assert all(event["status"] == "transmitted" for event in events)
    assert all(event["faults"] == [] for event in events)


def test_stress_mode_increases_event_rate(tmp_path: Path) -> None:
    normal = simulation_config(tmp_path / "normal")
    stress = simulation_config(tmp_path / "stress")
    stress["scenario"] = {"name": "Stress", "mode": "STRESS", "faults": []}
    _, normal_events = generate_universal_events(normal, normalize_hardware_config(normal), start_utc=1_700_000_000)
    _, stress_events = generate_universal_events(stress, normalize_hardware_config(stress), start_utc=1_700_000_000)
    assert len(stress_events) > len(normal_events)
    assert all(event["fault_load_multiplier"] == 2 for event in stress_events)


def test_live_event_rows_have_required_analysis_context(tmp_path: Path) -> None:
    fault = {"scope": "SIGNAL", "type": "SIGNAL_OFFSET", "target": {"id": "sig-temperature"}, "magnitude": 12, "start_s": 0, "end_s": 0.04}
    result = run_simulation(simulation_config(tmp_path, faults=[fault]))
    events = result["model_simulation"]["events"]
    assert events
    required = {"time_s", "severity", "event_type", "node", "message", "signal", "network", "description"}
    assert required <= events[0].keys()
    assert any(event["event_type"] == "FAULT_START" for event in events)
    assert any(event["event_type"] == "FAULT_END" for event in events)


def test_model_trace_limits_stored_samples_without_losing_totals(tmp_path: Path) -> None:
    config = simulation_config(tmp_path)
    config["duration_s"] = 0.2
    config["model_trace_frame_limit"] = 3
    config["model_trace_signal_point_limit"] = 2
    profile = normalize_hardware_config(config)
    _, events = generate_universal_events(config, profile, start_utc=1_700_000_000)

    trace = build_model_trace(events, config)

    assert len(events) > 3
    assert trace["timing_summary"]["frame_count"] == len(events)
    assert trace["timing_summary"]["stored_frame_count"] == 3
    assert len(trace["frames"]) == 3
    assert trace["signal_summary"]["sample_count"] == len(events)
    assert trace["signal_summary"]["stored_sample_count"] == 2
    assert sum(len(series["points"]) for series in trace["signals"]) == 2
    assert trace["storage"]["truncated"] is True


def test_fault_catalog_describes_handlers_constraints_and_targets() -> None:
    catalog = FaultCatalog()
    description = catalog.describe("SIGNAL_OFFSET")
    assert description is not None
    assert description["simulation_handler"] == "FaultInjectionEngine"
    assert description["applicable_object_types"] == ["SIGNAL"]
    assert description["constraints"]["end_s"]["after"] == "start_s"


def test_fault_scenario_validator_checks_target_time_and_normal_mode() -> None:
    model = {"signals": [{"id": "known"}], "messages": [], "routes": []}
    with pytest.raises(EngineeringValidationError, match="kein vorhandenes"):
        validate_scenario({"mode": "USER_DEFINED_FAULT", "faults": [{"scope": "SIGNAL", "type": "SIGNAL_OFFSET", "target": {"id": "missing"}}]}, model)
    with pytest.raises(EngineeringValidationError, match="Startzeit"):
        validate_scenario({"mode": "USER_DEFINED_FAULT", "faults": [{"scope": "SIGNAL", "type": "SIGNAL_OFFSET", "target": {"id": "known"}, "start_s": -1}]}, model)
    with pytest.raises(EngineeringValidationError, match="NORMAL"):
        validate_scenario({"mode": "NORMAL", "faults": [{"scope": "SIGNAL", "type": "SIGNAL_OFFSET"}]}, model)


def test_contract_demo_scenarios_a_to_e_are_complete_and_review_gated() -> None:
    scenarios = demo_scenarios()
    assert [item["id"] for item in scenarios] == [
        "DEMO_A_GOLDEN", "DEMO_B_RPM_LIMIT", "DEMO_C_TEMPERATURE_FROZEN",
        "DEMO_D_MESSAGE_LOSS", "DEMO_E_AI_CAMPAIGN",
    ]
    assert scenarios[0]["faults"] == []
    assert scenarios[1]["faults"][0]["start_s"] == 30
    assert scenarios[2]["faults"][0]["end_s"] == 50
    assert scenarios[3]["faults"][0]["type"] == "MESSAGE_LOSS"
    assert scenarios[4]["proposal_count"] == 3 and scenarios[4]["requires_review"] is True
