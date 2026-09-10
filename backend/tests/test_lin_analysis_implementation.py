from copy import deepcopy
import pytest
from backend.engineering.signal_integrity import LEGACY_ENUM, integrity_checks, legacy_numeric_repair
from backend.engineering.signal_audit import inspect_signal, required_signal_bits
from backend.engineering.workloads.handlers import _canonical_signal_layers
from backend.engineering.capacity.transmission import profile, release_grid
from backend.engineering.capacity.evaluation import network_evaluation
from backend.tests.test_model_based_simulation import simulation_config
from hardware_profile import normalize_hardware_config
from universal_trace import generate_universal_events


def legacy():
    return {"id": "position", "name": "ValveStatus", "source": "ai_generated", "unit": "%", "length_bits": 10,
        "start_bit": 1, "data_type": "unsigned", "byte_order": "little_endian", "factor": .1, "offset_value": 0,
        "min_value": 0, "max_value": 100, "semantic": {"semantic_type": "STATE", "generated_by": "engineering-specification-parser-v2"},
        "data": {"enum_values": LEGACY_ENUM, "reserved_values": [4, 5, 6, 7], "invalid_values": [15], "resolution": 1}}


def test_physical_status_repair_is_evidenced_idempotent_and_preserves_wire_encoding():
    before = legacy()
    assert integrity_checks(before)
    after = {**before, **legacy_numeric_repair(before)}
    assert not integrity_checks(after) and legacy_numeric_repair(after) is None
    assert inspect_signal(after, {"dlc": 2})["status"] == "PASS"
    for field in ("start_bit", "length_bits", "factor", "offset_value", "min_value", "max_value", "data_type"):
        assert before[field] == after[field]
    assert legacy_numeric_repair({**before, "source": "imported"}) is None
    assert legacy_numeric_repair({**before, "data": {**before["data"], "enum_values": {"CUSTOM": 100}}}) is None


def test_explicit_raw_codes_determine_width_and_cannot_overlap():
    signal = {**legacy(), "unit": "code", "length_bits": 3,
        "data": {"enum_values": {"OK": 0, "ERROR": 2}, "invalid_values": [15], "reserved_values": [15]}}
    assert required_signal_bits(signal) == 4
    assert {c["code"] for c in integrity_checks(signal)} == {"SIGNAL_CODE_OUT_OF_RANGE", "SIGNAL_CODE_DOMAIN_OVERLAP"}


def test_negative_physical_range_does_not_require_signed_raw_encoding():
    signal = {**legacy(), "semantic": {"semantic_type": "NUMERIC"}, "data": {}, "min_value": -40,
        "max_value": 215, "factor": 1, "offset_value": -40, "unit": "degC", "length_bits": 8}
    assert required_signal_bits(signal) == 8


def test_backend_generator_physical_status_has_no_invented_error_code():
    result = _canonical_signal_layers(name="ValveStatus", description="Position", category="valve", datatype="unsigned",
        unit="%", minimum=0, maximum=100, resolution=.1, producer="valve", consumers=[], cycle_time=50, length_bits=10, start_bit=0)
    assert result["semantic"]["semantic_type"] == "NUMERIC"
    assert result["data"]["invalid_values"] == [] and result["data"]["enum_values"] == {}


def test_request_and_event_profiles_never_fall_back_to_cyclic():
    assert profile({"mode": "ON_REQUEST"}, 20)["errors"]
    contract = {"mode": "ON_REQUEST", "minimum_interval_ms": 20, "request_source": "external_application"}
    assert release_grid(contract, 20, 100) == []
    assert release_grid({**contract, "request_times_ms": [30, 80]}, 20, 100) == [30, 80]
    with pytest.raises(ValueError, match="Mindest"):
        release_grid({**contract, "request_times_ms": [30, 40]}, 20, 100)
    assert profile({"mode": "EVENT", "trigger": "on_change", "minimum_interval_ms": 20}, 5)["load_basis"] == "BOUNDED_EVENT_DEMAND"


def test_runtime_request_traffic_only_at_explicit_requests(tmp_path):
    config = simulation_config(tmp_path)
    config["communications"][0]["transmission_contract"] = {"mode": "ON_REQUEST", "minimum_interval_ms": 20,
        "request_source": "external_application", "request_times_ms": [30, 70]}
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1700000000)
    assert [round(e["origin_scheduled_time_s"] * 1000) for e in events] == [30, 70]
    assert all(e["release_mode"] == "ON_REQUEST" for e in events)


def test_runtime_unchanged_event_state_is_not_periodically_sent(tmp_path):
    config = simulation_config(tmp_path)
    config["engineering_model"]["behaviors"][0].update(behavior_type="CONSTANT", parameters={"value": 0})
    config["communications"][0]["transmission_contract"] = {"mode": "EVENT", "minimum_interval_ms": 20, "trigger": "on_change"}
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1700000000)
    assert len(events) == 1
    config["communications"][0]["transmission_contract"]["mode"] = "MIXED"
    config["communications"][0]["transmission_contract"]["period_ms"] = 40
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1700000000)
    assert [round(e["origin_scheduled_time_s"] * 1000) for e in events] == [0, 40, 80]


def test_capacity_and_stress_are_distinct_from_functional_approval():
    network = {"communication_schedule": {"status": "FEASIBLE_UNDER_ASSUMPTIONS", "responses": {"s": 4.667}, "slot_load_percent": 80},
        "average_load_percent": 53.33, "peak_load_percent": 61.33, "burst_load_percent": 80, "target_bus_load_percent": 60}
    stream = {"stream_id": "s", "message_id": "m", "cycle_ms": 50}
    result = network_evaluation(network, [stream], [{"message_id": "m", "status": "PASS"}])
    assert result["capacity"]["status"] == "PASS" and result["stress"]["status"] == "EXCEEDED"
    assert result["functional"]["status"] == "UNVERIFIED"
    stream["transmission_contract"] = {"functional_requirements": {"confirmed": True, "maximum_event_to_response_ms": 50,
        "sampling_delay_ms": 0, "actuation_delay_ms": 0}}
    assert network_evaluation(network, [stream], [])["functional"]["status"] == "FAIL"
