from __future__ import annotations

import pytest

from backend.app import create_app
from backend.app.simulation_service import SimulationService
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY, TechnologyRegistry, format_rate_bps


REGISTRY = DEFAULT_TECHNOLOGY_REGISTRY


def codes(result: dict) -> set[str]:
    return {item["code"] for item in result["findings"]}


def test_lin_rate_profile_accepts_real_rate_and_blocks_can_fd_rate() -> None:
    assert REGISTRY.validate_parameters("LIN", {"bitrate_bps": 19_200})["status"] == "VALID"
    invalid = REGISTRY.validate_parameters("LIN", {"bitrate_bps": 2_000_000})
    assert invalid["status"] == "INVALID"
    assert codes(invalid) == {"TECHNOLOGY_PARAMETER_OUT_OF_RANGE"}
    assert invalid["findings"][0]["severity"] == "BLOCKER"


def test_can_fd_requires_and_validates_both_rate_phases() -> None:
    assert REGISTRY.validate_parameters("CAN-FD", {
        "nominal_bitrate_bps": 500_000, "data_bitrate_bps": 2_000_000,
    })["status"] == "VALID"
    incomplete = REGISTRY.validate_parameters("CAN_FD", {"data_bitrate_bps": 2_000_000})
    assert "TECHNOLOGY_PARAMETER_INVALID" in codes(incomplete)


def test_ethernet_link_speed_and_rate_formatting_are_canonical() -> None:
    assert REGISTRY.validate_parameters("Ethernet", {"bitrate_bps": 1_000_000_000})["status"] == "VALID"
    assert format_rate_bps(19_200) == "19,2 kbit/s"
    assert format_rate_bps(2_000_000) == "2 Mbit/s"
    assert format_rate_bps(1_000_000_000) == "1 Gbit/s"


def test_dds_rate_is_validated_by_its_registered_ethernet_stack() -> None:
    assert REGISTRY.validate_parameters("dds", {"bitrate_bps": 1_000_000_000})["status"] == "VALID"
    invalid = REGISTRY.validate_parameters("dds", {"nominal_bitrate_bps": 500_000})
    assert invalid["status"] == "INVALID"
    assert codes(invalid) == {"TECHNOLOGY_RATE_MODEL_MISMATCH"}


def test_unknown_profile_blocks_instead_of_using_foreign_default() -> None:
    result = REGISTRY.validate_parameters("unobtainium_bus", {"bitrate_bps": 2_000_000})
    assert result["status"] == "UNKNOWN"
    assert codes(result) == {"TECHNOLOGY_PROFILE_MISSING"}


def test_registered_profile_with_missing_stack_layer_is_not_silently_valid() -> None:
    custom = TechnologyRegistry()
    custom.register_defaults([{
        "id": "custom_stack", "layer": "APPLICATION", "implementation_status": "PLANNED",
        "default_stack": ["missing_phy", "custom_stack"], "rate_model": {"fields": []},
    }])
    result = custom.validate_parameters("custom_stack", {})
    assert result["status"] == "INVALID"
    assert codes(result) == {"TECHNOLOGY_STACK_PROFILE_MISSING"}


def test_can_fd_to_lin_invalidates_phase_fields_and_marks_dependents_stale() -> None:
    changed = REGISTRY.change_parameters("CAN_FD", "LIN", {
        "nominal_bitrate_bps": 500_000, "data_bitrate_bps": 2_000_000, "schedule": "body",
    })
    assert changed["parameters"] == {"schedule": "body"}
    assert changed["invalidated_fields"] == ["data_bitrate_bps", "nominal_bitrate_bps"]
    assert set(changed["dependent_status"].values()) == {"STALE"}


def test_audit_reports_legacy_invalid_lin_binding() -> None:
    findings = REGISTRY.audit_bindings([{
        "binding_id": "lin-legacy", "technology_id": "LIN", "parameters": {"bitrate_bps": 2_000_000},
    }])
    assert findings[0]["binding_id"] == "lin-legacy"
    assert findings[0]["code"] == "TECHNOLOGY_PARAMETER_OUT_OF_RANGE"


@pytest.mark.parametrize(("technology", "category", "mechanism"), [
    ("CAN_FD", "integrity", "CAN_FD_CRC"),
    ("LIN", "integrity", "LIN_CHECKSUM"),
    ("ethernet", "address_resolution", "ARP"),
    ("ethernet", "address_resolution", "IPV6_NDP"),
    ("j1939", "address_resolution", "J1939_ADDRESS_CLAIM"),
    ("profinet", "discovery", "PROFINET_DCP"),
    ("dds", "discovery", "DDS_PARTICIPANT_DISCOVERY"),
    ("bacnet_ip", "discovery", "BACNET_WHO_IS_I_AM"),
    ("canopen", "supervision", "HEARTBEAT"),
    ("ethercat", "supervision", "WORKING_COUNTER"),
])
def test_communication_mechanisms_are_profile_backed(technology: str, category: str, mechanism: str) -> None:
    assert mechanism in REGISTRY.mechanisms(technology)[category]


def test_lin_calculation_refuses_invalid_rate() -> None:
    model = REGISTRY.resolve_stack(("lin",))["timing_model"]
    with pytest.raises(ValueError, match="violates the lin profile"):
        model.transmission_time_us(8, 2_000_000)


def test_simulation_preflight_blocks_invalid_lin_rate(tmp_path) -> None:
    with pytest.raises(ValueError, match="Technology-Validierung fehlgeschlagen"):
        SimulationService().prepare_config({"technology": "lin", "bitrate": 2_000_000}, tmp_path)


def test_catalog_exposes_dynamic_rate_fields() -> None:
    domains = SimulationService().catalog()["domains"]
    technologies = {item["id"]: item for domain in domains for item in domain["technologies"]}
    lin_fields = {item["key"] for item in technologies["lin"]["parameter_schema"]}
    can_fd_fields = {item["key"] for item in technologies["can_fd"]["parameter_schema"]}
    assert "bitrate" in lin_fields and "data_bitrate" not in lin_fields
    assert {"arbitration_bitrate", "data_bitrate"} <= can_fd_fields
    assert "bitrate" not in can_fd_fields


def test_parameter_validation_and_audit_api() -> None:
    client = create_app(testing=True).test_client()
    invalid = client.post("/api/technologies/validate-parameters", json={
        "technology": "LIN", "parameters": {"bitrate_bps": 2_000_000},
    })
    assert invalid.status_code == 422
    assert invalid.get_json()["findings"][0]["code"] == "TECHNOLOGY_PARAMETER_OUT_OF_RANGE"
    audit = client.post("/api/technologies/audit", json={"bindings": [{
        "id": "legacy-lin", "technology": "LIN", "parameters": {"bitrate_bps": 2_000_000},
    }]})
    assert audit.status_code == 200
    assert audit.get_json()["status"] == "INVALID"
