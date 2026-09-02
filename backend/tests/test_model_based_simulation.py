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
from backend.simulator.signals.core.validation import validate_signal_emulation_model
from backend.simulator.signals.derived import DerivedSignalEngine
from backend.simulator.signals.derived import SignalDependencyCycleError, SignalDependencyGraph
from backend.simulator.signals.discrete import SignalStateMachineEngine
from backend.simulator.signals.states import StateMachineEngine, gateway_profile
from backend.simulator.signals.quality import SignalQualityEngine


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


def motor_simulation_config(tmp_path: Path) -> dict:
    signal_specs = [
        ("motor-start-command", "MotorStartCommand", 0, 1, 1, 1),
        ("drive-operating-state", "DriveOperatingState", 1, 4, 1, 7),
        ("motor-enabled", "MotorEnabled", 5, 1, 1, 1),
        ("motor-rpm", "MotorRPM", 8, 16, 1, 5000),
        ("motor-torque", "MotorTorque", 24, 12, 0.1, 250),
        ("motor-current", "MotorCurrent", 36, 12, 0.1, 200),
        ("motor-temperature", "MotorTemperature", 48, 12, 0.1, 150),
        ("drive-health-state", "DriveHealthState", 60, 2, 1, 3),
        ("drive-safety-state", "DriveSafetyState", 62, 2, 1, 3),
    ]
    signals = [
        signal_record(
            id=signal_id,
            name=name,
            message_id="msg-motor",
            start_bit=start_bit,
            length_bits=length_bits,
            factor=factor,
            offset_value=0,
            unit="",
            min_value=0,
            max_value=maximum,
            communication={"cycle_ms": 100},
        )
        for signal_id, name, start_bit, length_bits, factor, maximum in signal_specs
    ]
    return {
        **simulation_config(tmp_path),
        "duration_s": 6,
        "max_events": 1000,
        "communications": [{
            "id": "route-motor",
            "sender_interface": "if-sensor",
            "receiver_interfaces": ["if-ecu"],
            "network": "can-main",
            "technology": "can_fd",
            "cycle_ms": 100,
            "payload_bytes": 8,
            "message_ids": ["msg-motor"],
            "signal_ids": [signal["id"] for signal in signals],
        }],
        "engineering_model": {
            "messages": [{"id": "msg-motor", "name": "MotorStatus", "cycle_ms": 100, "interface_id": "if-sensor"}],
            "signals": signals,
            "behaviors": [
                {
                    "signal_id": signal["id"],
                    "behavior_type": "PHYSICS_MODEL",
                    "model_label": "RULE_BASED",
                    "parameters": (
                        {"initial_value": 22, "max_rise_rate": 4, "max_fall_rate": 2}
                        if signal["id"] == "motor-temperature"
                        else {}
                    ),
                }
                for signal in signals
            ],
        },
        "scenario": {"name": "Motor E2E", "mode": "NORMAL", "faults": []},
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


def test_physical_temperature_respects_rate_limits() -> None:
    signal = definition(
        id="motor-temperature",
        name="MotorTemperature",
        min_value=-40,
        max_value=150,
        factor=0.1,
        behavior={
            "behavior_type": "PHYSICS_MODEL",
            "model_label": "RULE_BASED",
            "parameters": {"initial_value": 20, "max_rise_rate": 3, "max_fall_rate": 2},
        },
    )
    engine = SignalBehaviorEngine([signal], seed=5)

    values = [engine.sample(signal, time_s) for time_s in (0, 1, 2, 3, 4, 5, 6)]

    assert values[0] == pytest.approx(20)
    assert all((right - left) <= 3.000001 for left, right in zip(values, values[1:]))
    assert values[-1] > values[0]


def test_counter_signal_wraps_by_modulus() -> None:
    signal = definition(
        id="alive-counter",
        name="AliveCounter",
        min_value=0,
        max_value=15,
        factor=1,
        length_bits=4,
        communication={"cycle_ms": 10},
        behavior={"behavior_type": "PHYSICS_MODEL", "parameters": {"modulus": 16, "increment": 1}},
    )
    engine = SignalBehaviorEngine([signal], seed=5)

    values = [engine.sample(signal, index * 0.01) for index in range(18)]

    assert values[:17] == pytest.approx([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 0])


def test_signal_emulation_preflight_blocks_invalid_formula(tmp_path: Path) -> None:
    config = simulation_config(tmp_path)
    config["engineering_model"]["behaviors"][0] = {
        "signal_id": "sig-temperature",
        "behavior_type": "FORMULA",
        "parameters": {"formula": "unknown_input + 1"},
    }

    validation = validate_signal_emulation_model(config)

    assert validation["valid"] is False
    assert validation["errors"][0]["code"] == "SIGNAL_FORMULA_INVALID"


def test_signal_emulation_preflight_blocks_dependency_cycle(tmp_path: Path) -> None:
    config = simulation_config(tmp_path)
    config["engineering_model"]["signals"].append(signal_record(id="sig-current", name="Current", start_bit=16))
    config["engineering_model"]["behaviors"] = [
        {"signal_id": "sig-temperature", "behavior_type": "STATE_DEPENDENT", "dependencies": ["sig-current"]},
        {"signal_id": "sig-current", "behavior_type": "STATE_DEPENDENT", "dependencies": ["sig-temperature"]},
    ]

    validation = validate_signal_emulation_model(config)

    assert validation["valid"] is False
    assert any(error["code"] == "SIGNAL_DEPENDENCY_CYCLE" for error in validation["errors"])


def test_signal_emulation_preflight_blocks_encoding_overflow(tmp_path: Path) -> None:
    config = simulation_config(tmp_path)
    config["engineering_model"]["signals"][0]["start_bit"] = 60
    config["engineering_model"]["signals"][0]["length_bits"] = 16

    validation = validate_signal_emulation_model(config)

    assert validation["valid"] is False
    assert validation["errors"][0]["code"] == "SIGNAL_ENCODING_OVERFLOW"


def test_motor_end_to_end_physics_model_produces_plausible_trace(tmp_path: Path) -> None:
    config = motor_simulation_config(tmp_path)
    config["signal_emulation_validation"] = validate_signal_emulation_model(config)

    result = run_simulation(config)
    trace = result["model_simulation"]
    series = {item["signal_id"]: item for item in trace["signals"]}
    rpm_values = [point["value"] for point in series["motor-rpm"]["points"] if point["value"] is not None]
    temperature_values = [point["value"] for point in series["motor-temperature"]["points"] if point["value"] is not None]
    state_values = [point["value"] for point in series["drive-operating-state"]["points"] if point["value"] is not None]

    assert trace["signal_emulation_validation"]["valid"] is True
    assert max(rpm_values) > 1000
    assert temperature_values[-1] > temperature_values[0]
    assert 4 in state_values


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
    assert result["model_simulation"]["signals"][0]["semantic_type"] == "NUMERIC_PHYSICAL"
    assert result["model_simulation"]["signals"][0]["quality"] in {"VALID", "ESTIMATED"}
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


def test_route_signals_are_ordered_before_derived_sampling(tmp_path: Path) -> None:
    rpm = signal_record(id="rpm", name="MotorRPM", start_bit=0, min_value=0, max_value=5000, factor=1)
    current = signal_record(id="current", name="MotorCurrent", start_bit=16, min_value=0, max_value=200, factor=0.1)
    config = simulation_config(tmp_path)
    config["engineering_model"]["signals"] = [current, rpm]
    config["engineering_model"]["behaviors"] = [
        {"signal_id": "current", "behavior_type": "FORMULA", "dependencies": ["MotorRPM"], "parameters": {"formula": "MotorRPM * 0.02"}, "model_label": "RULE_BASED"},
        {"signal_id": "rpm", "behavior_type": "CONSTANT", "parameters": {"value": 3000}, "model_label": "RULE_BASED"},
    ]
    config["communications"][0]["signal_ids"] = ["current", "rpm"]
    event = ModelBasedSimulationEngine(config).encode_event(config["communications"][0], 0.1, 8)

    samples = {sample["signal_id"]: sample for sample in event["signals"]}
    assert [sample["signal_id"] for sample in event["signals"]] == ["rpm", "current"]
    assert samples["current"]["actual_value"] == pytest.approx(60.0)
    assert samples["current"]["golden_value"] == pytest.approx(60.0)


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


def test_model_trace_decimates_each_signal_across_full_duration(tmp_path: Path) -> None:
    config = simulation_config(tmp_path)
    config["duration_s"] = 60
    config["model_trace_frame_limit"] = 5
    config["model_trace_points_per_signal"] = 4
    config["engineering_model"]["signals"].append(signal_record(id="sig-current", name="Current", start_bit=16))
    config["engineering_model"]["behaviors"].append({"signal_id": "sig-current", "behavior_type": "RAMP", "model_label": "RULE_BASED"})
    events = []
    for index in range(600):
        time_s = index * 0.1
        events.append({
            "time_s": time_s,
            "status": "transmitted",
            "network": "can-main",
            "route_id": "route-temperature",
            "signals": [
                {"signal_id": "sig-temperature", "signal": "Temperature", "time_s": time_s, "value": index, "golden_value": index, "faults": [], "cycle_ms": 100, "minimum": 0, "maximum": 600, "resolution": 1, "behavior_type": "RAMP", "model_label": "RULE_BASED"},
                {"signal_id": "sig-current", "signal": "Current", "time_s": time_s, "value": index * 2, "golden_value": index * 2, "faults": [], "cycle_ms": 100, "minimum": 0, "maximum": 1200, "resolution": 1, "behavior_type": "RAMP", "model_label": "RULE_BASED"},
            ],
        })

    trace = build_model_trace(events, config)

    assert trace["signal_summary"]["sample_count"] == 1200
    assert trace["signal_summary"]["stored_sample_count"] <= 8
    assert trace["storage"]["signal_point_limit"] == 0
    for series in trace["signals"]:
        assert series["sample_count"] == 600
        assert len(series["points"]) <= 4
        assert series["points"][-1]["time_s"] == pytest.approx(59.9)


def test_universal_trace_reaches_configured_duration_when_event_budget_allows(tmp_path: Path) -> None:
    config = simulation_config(tmp_path)
    config["duration_s"] = 60
    config["communications"][0]["cycle_ms"] = 100
    config["max_events"] = 1000
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1_700_000_000)

    assert events[-1]["scheduled_time_s"] == pytest.approx(60.0)
    assert events[-1]["time_s"] >= 59.9


def test_signal_engine_services_are_available_as_separate_contracts() -> None:
    state_machine = SignalStateMachineEngine()
    quality = SignalQualityEngine()
    ordered = DerivedSignalEngine().order([
        definition(id="derived", name="Derived", behavior={"behavior_type": "FORMULA", "dependencies": ["Base"]}),
        definition(id="base", name="Base"),
    ])

    assert state_machine.state_at(4.0) == "STARTING"
    assert quality.evaluate(definition(), None) == "NOT_AVAILABLE"
    assert [signal.id for signal in ordered] == ["base", "derived"]


def test_gateway_state_machine_lifecycle_and_transition_validation() -> None:
    engine = StateMachineEngine(gateway_profile())

    assert [engine.state_at(time_s) for time_s in (0.0, 0.1, 0.5, 1.2, 1.5)] == [
        "OFF",
        "INIT",
        "CONFIGURING",
        "READY",
        "ACTIVE",
    ]
    assert engine.can_transition("READY", "ACTIVE") is True
    assert engine.can_transition("OFF", "ACTIVE") is False
    assert engine.state_at(2.0, faults={"BUS_OFF"}) == "STANDBY"


def test_motor_physics_is_state_dependent_and_continuous() -> None:
    rpm = definition(id="motor-rpm", name="MotorRPM", min_value=0, max_value=5000, factor=1, behavior={"behavior_type": "PHYSICS_MODEL", "model_label": "PHYSICS_BASED"})
    temp = definition(id="motor-temperature", name="MotorTemperature", min_value=-40, max_value=150, factor=0.1, behavior={"behavior_type": "PHYSICS_MODEL", "model_label": "PHYSICS_BASED", "parameters": {"initial_value": 22, "max_rise_rate": 2}})
    engine = SignalBehaviorEngine([rpm, temp], seed=12)

    rpm_values = [engine.sample(rpm, time_s) for time_s in (0.0, 3.5, 5.5)]
    temp_values = [engine.sample(temp, time_s, {"MotorRPM": rpm_values[-1]}) for time_s in (0.0, 1.0, 2.0)]

    assert rpm_values[0] == 0
    assert rpm_values[-1] > rpm_values[1]
    assert temp_values == sorted(temp_values)
    assert temp_values[-1] - temp_values[0] <= 4.000001


def test_dependency_graph_rejects_cycles_and_reports_dirty_dependents() -> None:
    first = definition(id="first", name="First", behavior={"behavior_type": "FORMULA", "dependencies": ["Second"]})
    second = definition(id="second", name="Second", behavior={"behavior_type": "FORMULA", "dependencies": ["First"]})

    with pytest.raises(SignalDependencyCycleError):
        SignalDependencyGraph([first, second]).topological_order()

    base = definition(id="base", name="Base")
    derived = definition(id="derived", name="Derived", behavior={"behavior_type": "FORMULA", "dependencies": ["Base"]})
    graph = SignalDependencyGraph([base, derived])
    assert graph.dirty_dependents("base") == {"derived"}


def test_trace_marks_discrete_samples_as_step_lanes(tmp_path: Path) -> None:
    config = simulation_config(tmp_path)
    config["engineering_model"]["signals"][0] = signal_record(id="gateway-state", name="GatewayOperatingState", min_value=0, max_value=7, factor=1, length_bits=4)
    config["engineering_model"]["behaviors"] = [{"signal_id": "gateway-state", "behavior_type": "STATE_MACHINE", "model_label": "RULE_BASED"}]
    config["communications"][0]["signal_ids"] = ["gateway-state"]

    event = ModelBasedSimulationEngine(config).encode_event(config["communications"][0], 1.5, 8)
    trace = build_model_trace([{**event, "time_s": 1.5, "status": "transmitted", "network": "can-main"}], config)
    series = trace["signals"][0]

    assert series["trace_kind"] == "state"
    assert series["interpolation"] == "step"
    assert series["points"][0]["state"] == "ACTIVE"
    assert series["points"][0]["value"] == 4


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
