"""Unverified technologies cannot gain a capacity release from a generic rate."""

import pytest
from uuid import uuid4

from backend.engineering.capacity.evaluation import network_evaluation
from backend.engineering.capacity.calculators import estimate_frame
from backend.engineering.capacity.service import parameters_for_protocol
from backend.engineering.capacity.service import CapacityTimingService, PreflightService
from backend.engineering.capacity.dimensioning import SUPPORTED_CAPACITY_PROTOCOLS, bus_schedule, DEFAULT_POLICY
from backend.communication.technologies.catalog import technology_definitions
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY, TechnologyRegistry
from backend.engineering.capacity import service as capacity_service
from backend.engineering.workflow.models import default_statuses, default_versions
from backend.engineering.agent_tools.wizard_generation import _technology_contract
from backend.engineering.routing.validation import RoutingValidator
from backend.app.simulation_service import SimulationService


@pytest.mark.parametrize("protocol", ["I2C", "SPI", "ETHERCAT", "PROFINET", "RS485", "CAN_XL"])
def test_foreign_global_rate_is_not_replaced_by_a_custom_capacity(protocol):
    parameters = parameters_for_protocol(protocol, {"technology": "CAN", "bitrate": 500_000})
    assert "bitrate" not in parameters


def test_supported_can_rate_stays_missing_without_explicit_capacity_input():
    parameters = parameters_for_protocol("CAN", {"technology": "LIN"})
    assert "bitrate" not in parameters


def test_explicit_secondary_lin_rate_is_evidence_without_inheriting_can_fd_rate():
    confirmed = {"technology": "can_fd", "bitrate": 2_000_000,
                 "defaults_source": "technology-registry-with-explicit-user-rates",
                 "explicit_technology_bitrates": {"lin": 19_200}}
    parameters = parameters_for_protocol("LIN", confirmed, confirmed_parameters=confirmed)
    assert parameters["bitrate"] == 19_200
    assert parameters["_rate_evidenced"] is True


def test_registry_rate_remains_unverified_until_explicitly_confirmed():
    generated = {"technology": "can", "bitrate": 500_000,
                 "defaults_source": "technology-registry", "explicit_technology_bitrates": {}}
    assert parameters_for_protocol("CAN", generated, confirmed_parameters=generated)["_rate_evidenced"] is False
    confirmed = {**generated, "explicit_technology_bitrates": {"can": 500_000}}
    assert parameters_for_protocol("CAN", confirmed, confirmed_parameters=confirmed)["_rate_evidenced"] is True


def test_can_fd_requires_evidence_for_both_phases():
    parameters = {"technology": "can_fd", "bitrate": 500_000,
                  "arbitration_bitrate": 500_000, "data_bitrate": 2_000_000,
                  "defaults_source": "technology-registry"}
    assert parameters_for_protocol("CAN_FD", parameters, confirmed_parameters=parameters)["_rate_evidenced"] is False
    one_phase = {"arbitration_bitrate": 500_000}
    assert parameters_for_protocol("CAN_FD", parameters, one_phase,
                                   confirmed_parameters=parameters)["_rate_evidenced"] is False
    both_phases = {**one_phase, "data_bitrate": 2_000_000}
    assert parameters_for_protocol("CAN_FD", parameters, both_phases,
                                   confirmed_parameters=parameters)["_rate_evidenced"] is True
    named_primary_rate = {"bitrate": 500_000, "data_bitrate": 2_000_000}
    assert parameters_for_protocol("CAN_FD", parameters, named_primary_rate,
                                   confirmed_parameters=parameters)["_rate_evidenced"] is True


def test_can_xl_is_not_reported_or_released_as_can_fd():
    estimate = estimate_frame("CAN_XL", 8, {"bitrate": 10_000_000})
    assert estimate.protocol == "CAN_XL"
    assert estimate.is_generic_estimate is True


def test_missing_rate_cannot_create_a_one_mbit_generic_transmission_time():
    estimate = estimate_frame("CUSTOM_PROTOCOL", 8, {})
    assert estimate.protocol == "CUSTOM_PROTOCOL"
    assert estimate.is_generic_estimate is True
    assert estimate.transmission_time_available is False
    assert estimate.to_dict()["transmission_time_s"] is None


def test_every_registered_profile_requires_rate_evidence_for_numeric_frame_time():
    for profile in DEFAULT_TECHNOLOGY_REGISTRY.profiles():
        estimate = estimate_frame(profile['id'], 8, {})
        assert estimate.transmission_time_available is False, profile['id']
        assert estimate.to_dict()['transmission_time_s'] is None, profile['id']


@pytest.mark.parametrize('rate', [None, 0, -1, True, float('nan'), float('inf')])
@pytest.mark.parametrize('protocol', ['CAN', 'LIN', 'ETHERNET', 'CAN_FD'])
def test_invalid_rates_cannot_become_catalog_fallback_times(protocol, rate):
    frame = estimate_frame(protocol, 8, {'bitrate': rate, 'data_bitrate': rate})
    assert frame.to_dict()['transmission_time_s'] is None


def test_can_fd_needs_both_explicit_phases_and_can_bound_needs_rate():
    from backend.engineering.capacity.calculators import can_frame_time_bound_ms
    for parameters in ({}, {'bitrate': 500_000}, {'data_bitrate': 2_000_000}):
        assert estimate_frame('CAN_FD', 8, parameters).to_dict()['transmission_time_s'] is None
        assert can_frame_time_bound_ms('CAN_FD', 8, parameters) is None
    assert can_frame_time_bound_ms('CAN', 8, {}) is None
    assert can_frame_time_bound_ms('CAN', 8, {'bitrate': 500_000}) > 0


def test_unconfirmed_catalog_proposal_has_no_numeric_frame_time():
    for protocol in ['CAN', 'LIN', 'ETHERNET', 'CAN_FD']:
        frame = estimate_frame(protocol, 8, {'bitrate': 500_000, 'data_bitrate': 2_000_000,
                                           '_rate_evidenced': False})
        assert frame.to_dict()['transmission_time_s'] is None


def test_i2c_catalog_rate_is_not_silently_used_as_a_preview():
    estimate = estimate_frame("I2C", 8, {})
    assert estimate.is_generic_estimate is True
    assert estimate.transmission_time_available is False
    assert estimate.to_dict()["transmission_time_s"] is None


def test_catalog_has_no_implicit_supported_capacity_for_partial_technologies():
    profiles = technology_definitions()
    assert len(profiles) == 125
    assert SUPPORTED_CAPACITY_PROTOCOLS == {"CAN", "CAN_FD", "LIN", "ETHERNET", "I2C", "SPI"}
    assert {"i2c", "spi", "ethercat", "profinet"}.issubset({item["id"] for item in profiles})


def test_all_catalog_profiles_disclose_actual_capacity_and_schedule_support():
    profiles = DEFAULT_TECHNOLOGY_REGISTRY.profiles()
    assert len(profiles) == 125
    supported = {item["id"] for item in profiles
                 if item["capacity_evidence"]["status"] == "MODEL_AVAILABLE"}
    assert supported == {"can", "can_fd", "lin", "ethernet", "i2c", "spi"}
    for item in profiles:
        evidence = item["capacity_evidence"]
        runtime = DEFAULT_TECHNOLOGY_REGISTRY.resolve_stack((item["id"],)) if item["implementation_status"] != "PLANNED" else None
        if item["id"] in supported:
            assert evidence["frame_model"] and evidence["schedule_model"]
            assert item["components"]["timing_model"] and item["components"]["load_model"]
            assert runtime and runtime["timing_model"] and runtime["load_calculator"]
        else:
            assert evidence["status"] == ("NOT_APPLICABLE" if item["connection_type"] == "DIRECT_IO" else "MODEL_MISSING")
            assert evidence["frame_model"] is None and evidence["schedule_model"] is None
            assert item["components"]["timing_model"] is None
            assert item["components"]["load_model"] is None
            if runtime:
                assert runtime["timing_model"] is None
                assert runtime["load_calculator"] is None


def test_no_unmodelled_catalog_entry_uses_a_verified_frame_branch():
    for item in DEFAULT_TECHNOLOGY_REGISTRY.profiles():
        estimate = estimate_frame(item["id"], 8, {})
        model_available = item["capacity_evidence"]["status"] == "MODEL_AVAILABLE"
        if item["connection_type"] == "DIRECT_IO":
            assert estimate.calculation_model == "DIRECT_IO_NO_FRAME"
            assert estimate.transmission_time_available is False
        elif item["id"] in {"i2c", "spi"}:
            assert estimate.is_generic_estimate is True  # model exists, device evidence does not
            assert estimate.transmission_time_available is False
        else:
            assert estimate.is_generic_estimate is not model_available, item["id"]
        if not model_available:
            assert estimate.protocol == item["id"].upper(), item["id"]


def test_direct_io_has_no_bus_capacity_but_keeps_timing_review():
    for protocol in ("GPIO", "PWM", "ADC", "DAC"):
        profile = DEFAULT_TECHNOLOGY_REGISTRY.profile(protocol)
        assert profile["connection_type"] == "DIRECT_IO"
        assert profile["capacity_evidence"]["status"] == "NOT_APPLICABLE"
        frame = estimate_frame(protocol, 1, {})
        assert frame.frame_bits == 0
        assert frame.transmission_time_available is False
        evaluation = network_evaluation({
            "capacity_applicable": False, "capacity_verified": False,
            "average_load_percent": 0, "peak_load_percent": 0,
            "burst_load_percent": 0, "target_bus_load_percent": 60,
            "communication_schedule": {"status": "UNVERIFIED", "responses": {}},
        }, [], [])
        assert evaluation["capacity"]["status"] == "NOT_APPLICABLE"
        assert evaluation["capacity"]["load_percent"] is None
        assert evaluation["schedule"]["status"] == "UNVERIFIED"


def test_direct_only_project_has_no_route_error_or_fictional_bus_load(monkeypatch):
    state = {
        "project_id": "isolated-direct-only",
        "versions": default_versions(),
        "statuses": {step: "COMPLETE" for step in default_statuses()},
        "parameters": {},
        "topology": {"nodes": [], "edges": []},
    }
    direct = {
        "id": "direct-1", "name": "SwitchState", "message_id": None,
        "configuration": {"direct_signal_binding": {
            "source_hardware_node_ref": "switch", "destination_hardware_node_ref": "controller",
            "physical_port_ref": "gpio-1", "signal_type": "GPIO",
            "validation_status": "REVIEW_REQUIRED", "timing_profile": {},
        }},
    }
    monkeypatch.setattr(capacity_service, "list_routes", lambda **_kwargs: [])
    monkeypatch.setattr(capacity_service, "list_objects", lambda object_type, **_kwargs: [direct] if object_type == "Signal" else [])
    calculation = CapacityTimingService("isolated-direct-only")
    monkeypatch.setattr(calculation.workflow, "get", lambda: state)
    monkeypatch.setattr(calculation, "latest", lambda: None)
    result = calculation.calculate(persist=False)
    assert result["results"]["overview"]["capacity_status"] == "NOT_APPLICABLE"
    assert result["results"]["signals"][0]["capacity_status"] == "NOT_APPLICABLE"
    assert result["results"]["signals"][0]["load_contribution_percent"] is None
    codes = {finding["code"] for finding in result["findings"]}
    assert "DIRECT_IO_CAPACITY_NOT_APPLICABLE" in codes
    assert "CAPACITY_NO_ROUTES" not in codes
    assert "CAPACITY_SOURCE_NOT_READY" not in codes


def test_i2c_reference_modes_are_review_proposals_not_automatic_evidence():
    profile = DEFAULT_TECHNOLOGY_REGISTRY.profile("i2c")
    proposal = profile["parameter_proposals"]
    assert proposal["status"] == "REVIEW_REQUIRED"
    assert [option["maximum"] for option in proposal["options"]] == [100_000, 400_000, 1_000_000, 3_400_000]
    assert profile["capacity_evidence"]["status"] == "MODEL_AVAILABLE"
    assert estimate_frame("I2C", 8, {}).transmission_time_available is False
    assert estimate_frame("SPI", 8, {}).transmission_time_available is False


@pytest.mark.parametrize(("protocol", "evidence", "expected_us"), [
    ("I2C", {"master_node_id": "controller", "slave_address": "0x20", "address_bits": 7,
             "i2c_mode": "FAST",
             "transfer_direction": "READ", "start_stop_bound_us": 2,
             "clock_stretch_limit_us": 5, "multi_master": False,
             "transfer_bits_bound": 100, "bitrate_bps": 400_000}, 257),
    ("SPI", {"master_node_id": "controller", "chip_select": "CS0", "word_length_bits": 8,
             "duplex_mode": "FULL_DUPLEX", "cpol": 0, "cpha": 0,
             "cs_setup_bound_us": 2, "inter_transfer_gap_us": 1,
             "transfer_bits_bound": 64, "bitrate_bps": 1_000_000}, 67),
])
def test_confirmed_serial_transaction_gets_technology_specific_capacity_and_schedule(protocol, evidence, expected_us):
    confirmed = {**evidence, "confirmed": True, "source": "approved device datasheet"}
    parameters = parameters_for_protocol(protocol, {}, {"local_timing_evidence": confirmed},
                                         confirmed_parameters={})
    assert parameters["_rate_evidenced"] is True
    frame = estimate_frame(protocol, 8, parameters)
    assert frame.is_generic_estimate is False
    assert frame.transmission_time_s * 1_000_000 == pytest.approx(expected_us)
    adapter = DEFAULT_TECHNOLOGY_REGISTRY.resolve_stack(protocol)["timing_model"]
    assert adapter.transmission_time_us(8, local_timing_evidence=confirmed) == pytest.approx(expected_us)
    row = {"stream_id": "tx-1", "protocol": protocol, "payload_bytes": 8,
           "cycle_ms": 10, "bitrate": confirmed["bitrate_bps"],
           "segment_transmission_latency_ms": expected_us / 1000,
           "local_timing_evidence": confirmed, "physical_path_resolved": True}
    schedule = bus_schedule([row], DEFAULT_POLICY)
    assert schedule["status"] == "FEASIBLE_UNDER_ASSUMPTIONS"
    assert schedule["responses"]["tx-1"] == pytest.approx(expected_us / 1000)
    missing = {key: value for key, value in confirmed.items() if key != "bitrate_bps"}
    assert estimate_frame(protocol, 8, {"local_timing_evidence": missing}).transmission_time_available is False
    assert bus_schedule([{**row, "local_timing_evidence": missing}], DEFAULT_POLICY)["status"] == "UNVERIFIED"


def test_direct_signal_audit_uses_timing_review_without_message_gap():
    from backend.engineering.signal_audit import build_generation_signal_audit

    signal = {"id": "direct-1", "name": "SwitchState", "message_id": None,
              "configuration": {"direct_signal_binding": {
                  "source_hardware_node_ref": "switch", "destination_hardware_node_ref": "controller",
                  "physical_port_ref": "gpio-1", "signal_type": "GPIO",
                  "validation_status": "REVIEW_REQUIRED", "timing_profile": {}}}}
    audit = build_generation_signal_audit(hardware=[], interfaces=[], messages=[],
                                          signals=[signal], routes=[])
    direct = next(item for item in audit["signals"] if item["signal_id"] == "direct-1")
    assert direct["capacity_status"] == "NOT_APPLICABLE"
    codes = {check["code"] for check in direct["checks"]}
    assert "DIRECT_IO_TIMING_UNVERIFIED" in codes
    assert "SIGNAL_MESSAGE_MISSING" not in codes


def test_generated_profile_cannot_claim_an_executable_capacity_model():
    registry = TechnologyRegistry()
    profile = next(item for item in technology_definitions() if item["id"] == "i2c")
    profile["id"] = "generated_i2c_like"
    profile["default_stack"] = ["generated_i2c_like"]
    profile["knowledge_origin"] = "GENERATED_TECHNOLOGY_PACK"
    profile["capacity_evidence"] = {"status": "MODEL_AVAILABLE", "frame_model": "FICTIONAL"}
    registry.register_generated_profile(profile)
    saved = registry.profile("generated_i2c_like")
    assert saved["capacity_evidence"]["status"] == "MODEL_MISSING"
    assert registry.resolve_stack("generated_i2c_like")["timing_model"] is None


def test_registered_timing_adapters_require_rates_and_match_frame_models():
    for technology, rate in (("can", 500_000), ("lin", 19_200), ("ethernet", 100_000_000)):
        adapter = DEFAULT_TECHNOLOGY_REGISTRY.resolve_stack(technology)["timing_model"]
        with pytest.raises(ValueError, match="bestätigte Bitrate"):
            adapter.transmission_time_us(8)
        expected = estimate_frame(technology, 8, {"bitrate": rate})
        assert adapter.transmission_time_us(8, rate) == pytest.approx(expected.transmission_time_s * 1_000_000)
    fd = DEFAULT_TECHNOLOGY_REGISTRY.resolve_stack("can_fd")["timing_model"]
    with pytest.raises(ValueError, match="Arbitrierungs- und Datenphasenraten"):
        fd.transmission_time_us(8, 2_000_000)
    expected_fd = estimate_frame("can_fd", 8, {"bitrate": 500_000,
                                                "arbitration_bitrate": 500_000,
                                                "data_bitrate": 2_000_000})
    assert fd.transmission_time_us(8, arbitration_bitrate=500_000, data_bitrate=2_000_000) == pytest.approx(
        expected_fd.transmission_time_s * 1_000_000)


def test_wizard_contract_exposes_serial_adapter_that_requires_evidence():
    contract = _technology_contract("I2C")
    assert contract["capacity_evidence"]["status"] == "MODEL_AVAILABLE"
    assert contract["timing_model"] is not None
    assert contract["load_calculator"] is not None
    adapter = DEFAULT_TECHNOLOGY_REGISTRY.resolve_stack("i2c")["timing_model"]
    with pytest.raises(ValueError, match="Geräte- und Transaktionsgrenzen"):
        adapter.transmission_time_us(8, 400_000)


def test_public_catalog_exposes_all_registered_evidence_statuses():
    catalog = SimulationService().catalog()
    by_id = {item["id"]: item for domain in catalog["domains"]
             for item in domain["technologies"]}
    assert catalog["technology_count"] == len(by_id) == 125
    assert sum(item["capacity_evidence"]["status"] == "MODEL_AVAILABLE"
               for item in by_id.values()) == 6


def test_registered_bus_without_capacity_key_keeps_its_routing_identity(monkeypatch):
    source, target = str(uuid4()), str(uuid4())
    ports = [{"hardware_node_id": node, "network_ref": "rs485-net", "technology": "RS485"}
             for node in (source, target)]

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, *_args):
            return self

        def fetchall(self):
            return ports

    monkeypatch.setattr("backend.engineering.routing.validation.get_connection", Connection)
    segments = RoutingValidator("isolated")._canonical_transport_segments(
        {"node_id": source, "network_id": "rs485-net"},
        [{"node_id": target, "network_id": "rs485-net"}],
        {"hops": [source, target]})
    assert segments == [{"network_id": "rs485-net", "protocol": "RS485",
                         "source_node_id": source, "target_node_id": target}]


def test_network_evaluation_withholds_capacity_and_stress_without_model():
    network = {
        "communication_schedule": {"status": "UNVERIFIED", "responses": {}},
        "capacity_applicable": True,
        "capacity_verified": False,
        "average_load_percent": 0.0256,
        "peak_load_percent": 0.03,
        "burst_load_percent": 0.04,
        "target_bus_load_percent": 60,
    }
    result = network_evaluation(network, [], [])
    assert result["capacity"]["status"] == "UNVERIFIED"
    assert result["stress"]["status"] == "UNVERIFIED"
    assert result['capacity']['load_percent'] is None
    assert result['stress']['peak_percent'] is None
    assert result['stress']['burst_percent'] is None


def test_i2c_capacity_stays_unverified_and_preflight_cannot_approve_it(monkeypatch):
    state = {
        "project_id": "isolated-i2c",
        "versions": default_versions(),
        "statuses": {step: "COMPLETE" for step in default_statuses()},
        "parameters": {"technology": "i2c", "cycle_ms": 100, "payload_bytes": 8},
        "topology": {"nodes": [], "edges": []},
    }
    route = {
        "id": "i2c-route", "route_code": "RT-I2C", "name": "I2C sensor",
        "status": "APPROVED", "approval_state": "APPROVED",
        "source": {"node_id": "controller", "protocol": "I2C", "network_id": "i2c-1"},
        "payload": {"payload_bytes": 8},
        "destinations": [{"node_id": "sensor", "protocol": "I2C", "network_id": "i2c-1"}],
        "route": {"gateways": []}, "timing": {"cycle_time_ms": 100},
        "routing_policy": {"priority": "NORMAL"},
    }
    monkeypatch.setattr(capacity_service, "list_routes", lambda **_kwargs: [route])
    monkeypatch.setattr(capacity_service, "list_objects", lambda *_args, **_kwargs: [])
    calculation = CapacityTimingService("isolated-i2c")
    monkeypatch.setattr(calculation.workflow, "get", lambda: state)
    monkeypatch.setattr(calculation, "latest", lambda: None)
    result = calculation.calculate(persist=False)
    network = result["results"]["networks"][0]
    assert network["capacity_verified"] is False
    assert network["status"] == "UNVERIFIED"
    assert network['average_load_percent'] is None
    assert network['evaluation']['capacity']['load_percent'] is None
    assert result['results']['routes'][0]['end_to_end_latency_ms'] is None
    assert result['results']['overview']['max_peak_load_percent'] is None
    assert result["results"]["overview"]["capacity_verified"] is False
    review_codes = {finding["code"] for finding in result["findings"] if finding["severity"] == "REVIEW"}
    assert "GENERIC_ESTIMATE" in review_codes
    assert any(finding["code"].startswith("COMMUNICATION_") for finding in result["findings"])

    monkeypatch.setattr(capacity_service, "list_routes", lambda **_kwargs: [])
    preflight = PreflightService("isolated-i2c")
    monkeypatch.setattr(preflight.workflow, "get", lambda: state)
    monkeypatch.setattr(preflight.workflow, "latest_analysis", lambda *_args, **_kwargs: {
        "id": "current-capacity", "provenance": {"calculation_version": calculation.CALCULATION_VERSION},
        "findings": [finding for finding in result["findings"] if finding["code"] == "GENERIC_ESTIMATE"],
    })
    monkeypatch.setattr(preflight.workflow, "create_analysis_snapshot", lambda *_args, **_kwargs: {"id": "preflight"})
    decision = preflight.run()
    assert decision["ready_for_simulation"] is False
    assert decision["review_count"] >= 1
    assert decision["category_statuses"]["capacity"] == "REVIEW"
    assert any(finding["code"] == "GENERIC_ESTIMATE" for finding in decision["category_checks"]["capacity"])


@pytest.mark.parametrize('rate', [None, 0, -1, True, float('nan'), float('inf')])
def test_explicit_invalid_arbitration_phase_is_never_replaced_by_bitrate_alias(rate):
    from backend.engineering.capacity.calculators import can_frame_time_bound_ms
    parameters = {'bitrate': 500_000, 'arbitration_bitrate': rate, 'data_bitrate': 2_000_000}
    frame = estimate_frame('CAN_FD', 8, parameters)
    assert frame.transmission_time_available is False
    assert frame.to_dict()['transmission_time_s'] is None
    assert can_frame_time_bound_ms('CAN_FD', 8, parameters) is None
