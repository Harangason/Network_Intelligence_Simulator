from __future__ import annotations

import pytest

from backend.app import create_app
from backend.app.simulation_service import SimulationService
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY, TechnologyRegistry, format_rate_bps


REGISTRY = DEFAULT_TECHNOLOGY_REGISTRY
LIN_CONTEXT = {**{'lin_'+key: 'synthetic-project-'+key for key in
    ('revision','device_source','binding_source','physical_source','ldf_source','encoding_source',
     'schedule_source','capacity_source','acceptance_source','commander_node_id')},
    'lin_edition':'LIN_2_2A_2010', 'lin_physical_profile':'LIN_2_2A_SINGLE_WIRE',
    'lin_node_role':'COMMANDER','lin_frame_kind':'UNCONDITIONAL','lin_bitrate_bps':19200}


@pytest.mark.parametrize('technology', [item['id'] for item in REGISTRY.profiles()])
def test_validation_reads_definitions_without_mutating_registry_or_inputs(technology):
    from copy import deepcopy
    before = REGISTRY.profile(technology)
    values = {'unrelated_project_control': {'nested': ['retained']}}
    original = deepcopy(values)
    first = REGISTRY.validate_parameters(technology, values)
    second = REGISTRY.validate_parameters(technology, values)
    assert first == second
    assert values == original
    assert REGISTRY.profile(technology) == before
    # Public schemas and resolved transport profiles must remain independent.
    exported = REGISTRY.profile(technology)
    exported['parameter_schema'].clear()
    rate = REGISTRY.rate_profile(technology)
    rate['parameter_schema'].clear()
    assert REGISTRY.profile(technology) == before
    assert REGISTRY.rate_profile(technology)['parameter_schema']



def codes(result: dict) -> set[str]:
    return {item["code"] for item in result["findings"]}


def test_lin_rate_profile_accepts_real_rate_and_blocks_can_fd_rate() -> None:
    assert REGISTRY.validate_parameters("LIN", LIN_CONTEXT)["status"] == "VALID"
    assert REGISTRY.validate_parameters("LIN", {"bitrate_bps": 19_200})["status"] != "VALID"
    invalid = REGISTRY.validate_parameters("LIN", {**LIN_CONTEXT,"lin_bitrate_bps": 2_000_000})
    assert invalid["status"] == "INVALID"
    assert codes(invalid) == {"TECHNOLOGY_PARAMETER_DEPENDENCY_MISMATCH"}
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


def test_dds_requires_actual_transport_binding_and_rejects_implicit_ethernet_rate() -> None:
    actual = {'dds_entity': 'DATAWRITER', 'dds_transport_binding': 'selected-transport', 'dds_implementation_source': 'actual-vendor-version'}
    assert REGISTRY.validate_parameters('dds', actual)['status'] == 'VALID'
    for rate in ({'bitrate_bps': 1_000_000_000}, {'nominal_bitrate_bps': 500_000}):
        invalid = REGISTRY.validate_parameters('dds', {**actual, **rate})
        assert invalid['status'] == 'INVALID'
        assert 'TECHNOLOGY_RATE_MODEL_MISMATCH' in codes(invalid) or 'TECHNOLOGY_PARAMETER_NOT_APPLICABLE' in codes(invalid)


def test_unknown_profile_blocks_instead_of_using_foreign_default() -> None:
    result = REGISTRY.validate_parameters("unobtainium_bus", {"bitrate_bps": 2_000_000})
    assert result["status"] == "UNKNOWN"
    assert codes(result) == {"TECHNOLOGY_PROFILE_MISSING"}


@pytest.mark.parametrize("technology", ["can", "can_fd", "lin", "ethernet", "dds", "i2c", "spi", "can_xl"])
def test_absent_transport_rates_are_unverified_and_not_filled_from_catalog(technology):
    parameters = {}
    result = REGISTRY.validate_parameters(technology, parameters)
    assert result["status"] == "UNVERIFIED"
    assert "TECHNOLOGY_PARAMETER_MISSING" in codes(result)
    assert parameters == {}


def test_missing_rate_http_response_is_unverified_not_valid():
    client = create_app().test_client()
    response = client.post('/api/technologies/validate-parameters', json={
        'technology_id': 'LIN', 'parameters': {},
    })
    assert response.status_code == 200
    assert response.get_json()['status'] == 'UNVERIFIED'
    assert any(item['severity']=='BLOCKER' and item['code']=='TECHNOLOGY_PARAMETER_MISSING'
               for item in response.get_json()['findings'])


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
    ("ethernet", "upper_layer_resolution", "ARP_IF_IPV4"),
    ("ethernet", "upper_layer_resolution", "NDP_IF_IPV6"),
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
    with pytest.raises(ValueError, match="contradicts lin"):
        model.transmission_time_us(8, 2_000_000, technology_parameters={**LIN_CONTEXT,'lin_bitrate_bps':2_000_000})
    with pytest.raises(ValueError, match="required"):
        model.transmission_time_us(8, 19_200)
    assert model.transmission_time_us(8,19_200,technology_parameters=LIN_CONTEXT) == pytest.approx(124/19_200*1e6)


def test_simulation_preflight_blocks_invalid_lin_rate(tmp_path) -> None:
    with pytest.raises(ValueError, match="Technology-Validierung fehlgeschlagen"):
        SimulationService().prepare_config({"technology": "lin", "bitrate": 2_000_000}, tmp_path)


def test_catalog_exposes_dynamic_rate_fields() -> None:
    domains = SimulationService().catalog()["domains"]
    technologies = {item["id"]: item for domain in domains for item in domain["technologies"]}
    lin_fields = {item["key"] for item in technologies["lin"]["parameter_schema"]}
    can_fd_fields = {item["key"] for item in technologies["can_fd"]["parameter_schema"]}
    assert "lin_bitrate_bps" in lin_fields and not {"bitrate","data_bitrate"} & lin_fields
    assert {"arbitration_bitrate", "data_bitrate"} <= can_fd_fields
    assert "bitrate" not in can_fd_fields


def test_someip_requires_explicit_transport_binding_without_foreign_phy_default() -> None:
    domains = SimulationService().catalog()["domains"]
    technologies = {item["id"]: item for domain in domains for item in domain["technologies"]}
    someip = technologies["someip"]
    fields = {field["key"]: field for field in someip["parameter_schema"]}
    assert "bitrate" not in fields
    assert fields["someip_transport"]["options"] == ["UDP", "TCP", "UDP_TP"]
    assert fields["someip_transport_source"]["required"] is True
    assert REGISTRY.validate_parameters("someip", {"bitrate_bps": 100_000_000})["status"] != "VALID"
    assert "ethernet" in technologies


def test_i2c_and_spi_forms_expose_required_clocks_without_invented_defaults() -> None:
    domains = SimulationService().catalog()["domains"]
    technologies = {item["id"]: item for domain in domains for item in domain["technologies"]}
    automotive_ids = {item["id"] for item in next(domain for domain in domains if domain["id"] == "automotive")["technologies"]}

    i2c_clock = next(field for field in technologies["i2c"]["parameter_schema"] if field["key"] == "bitrate")
    spi_clock = next(field for field in technologies["spi"]["parameter_schema"] if field["key"] == "bitrate")

    assert i2c_clock["label"] == "I²C Bus Clock"
    assert spi_clock["label"] == "SPI Device Clock"
    assert i2c_clock["required"] is True and i2c_clock["default"] == 100_000
    assert i2c_clock["default_review"]["status"] == "REVIEW_REQUIRED"
    assert spi_clock["required"] is True and "default" not in spi_clock
    local_io_ids = {"i2c", "spi", "uart", "gpio", "pwm", "adc", "dac"}
    assert local_io_ids <= technologies.keys()
    assert local_io_ids.isdisjoint(automotive_ids)


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
