from __future__ import annotations

import pytest

from backend.app.simulation_service import SimulationService
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY, MODEL_TYPES
from backend.communication.technologies.core.models import (
    HardwareInterface,
    HardwareNode,
    PayloadElement,
    PayloadElementType,
    TechnologyStack,
    TransportRequirement,
)
from backend.communication.technologies.core.registry import BindingResolver


def test_complete_registry_exposes_layers_status_and_required_technologies() -> None:
    summary = DEFAULT_TECHNOLOGY_REGISTRY.summary()

    assert summary["technology_count"] >= 100
    assert summary["layers"] == ["PHYSICAL", "DATA_LINK", "NETWORK", "TRANSPORT", "APPLICATION", "INDUSTRY_PROFILE"]
    assert summary["implementation_status"]["IMPLEMENTED"] >= 12
    required = {
        "can_fd", "someip", "profinet", "ethercat", "modbus_tcp", "dds", "ros2",
        "arinc429", "afdx", "mil_std_1553", "trdp", "bacnet_ip", "iec61850",
        "i2c", "mqtt", "profisafe", "custom_protocol",
    }
    assert required <= {item["id"] for item in summary["technologies"]}


def test_device_hardware_interface_protocol_and_payload_are_distinct_types() -> None:
    plc = HardwareNode("plc-1", "Line PLC", "PLC", capabilities=("ethernet_port", "rs485_port"))
    port = HardwareInterface("plc-1-eth0", plc.id, "ethernet_port", network_ref="plant-net")

    assert plc.device_type == "PLC"
    assert port.hardware_node_ref == plc.id
    assert port.interface_type != plc.device_type
    assert "plc" not in {item["id"] for item in DEFAULT_TECHNOLOGY_REGISTRY.profiles()}


@pytest.mark.parametrize(
    ("stack", "expected_unit"),
    [
        (("can_fd",), "FRAME"),
        (("ethernet", "ip", "tcp", "modbus_tcp"), "PDU"),
        (("ethernet", "profinet"), "PROCESS_DATA"),
        (("ethernet", "ip", "udp", "dds"), "TOPIC_SAMPLE"),
    ],
)
def test_same_temperature_payload_resolves_cross_technology(stack: tuple[str, ...], expected_unit: str) -> None:
    resolved = DEFAULT_TECHNOLOGY_REGISTRY.resolve_stack(stack)
    binding = resolved["binding"].bind(
        "temperature-interface",
        stack,
        stack_model=TechnologyStack(stack),
        hardware_interface_ref="controller-port",
        network_ref="network-1",
    )
    payload = PayloadElement(
        id="temperature",
        element_type=PayloadElementType.SIGNAL,
        semantic_ref="Temperature",
        data_type="float32",
        size=32,
        unit="degC",
        source_ref="temperature-sensor",
    )
    unit = resolved["generator"].generate(
        binding,
        [payload],
        producer_ref="temperature-sensor",
        consumer_refs=["plc-1"],
        timing={"cycle_ms": 10},
    )

    assert unit.transport_unit_type.value == expected_unit
    assert unit.payload_elements[0].semantic_ref == "Temperature"
    assert unit.payload_elements[0].unit == "degC"


def test_plc_binding_resolver_uses_hardware_capabilities_and_rejects_video_on_can() -> None:
    resolver = BindingResolver(DEFAULT_TECHNOLOGY_REGISTRY)
    plc_candidates = resolver.resolve(
        requirement=TransportRequirement(data_complexity="PHYSICAL_SCALAR", deterministic=True),
        hardware_capabilities=("ethernet_port", "ethercat_port", "rs485_port", "can_controller", "io_link_master_port"),
        domain_profile="industrial_automation",
    )
    ids = {item["technology_id"] for item in plc_candidates}
    assert {"profinet", "ethercat", "modbus_tcp", "modbus_rtu", "io_link"} <= ids

    stream_candidates = resolver.resolve(
        requirement=TransportRequirement(data_complexity="IMAGE_STREAM", bandwidth_bps=5_000_000),
        hardware_capabilities=("ethernet_port", "can_fd_controller"),
    )
    stream_ids = {item["technology_id"] for item in stream_candidates}
    assert "dds" in stream_ids
    assert "can_fd" not in stream_ids


def test_validation_chain_and_planned_status_are_enforced() -> None:
    findings = DEFAULT_TECHNOLOGY_REGISTRY.validate_chain(
        ("can_fd",),
        {"payload_size": 65, "hardware_capabilities": ["can_controller"]},
    )
    assert {finding["code"] for finding in findings} == {"payload_too_large", "incompatible_interface"}

    assert DEFAULT_TECHNOLOGY_REGISTRY.profile("someip_sd")["implementation_status"] == "PLANNED"
    with pytest.raises(LookupError):
        DEFAULT_TECHNOLOGY_REGISTRY.resolve_generator(("someip_sd",))

    assert DEFAULT_TECHNOLOGY_REGISTRY.profile("custom_protocol")["implementation_status"] == "EXPERIMENTAL"
    assert DEFAULT_TECHNOLOGY_REGISTRY.resolve_generator(("custom_protocol",)) is not None


def test_catalog_exposes_new_project_model_types_and_registry_metadata() -> None:
    catalog = SimulationService().catalog()
    ids = {item["id"] for item in catalog["domains"]}

    assert ids == {item["id"] for item in MODEL_TYPES}
    assert {"rail", "industrial_automation", "process_industry", "embedded_systems", "iot_wireless", "custom"} <= ids
    assert catalog["core_model_types"] == [
        "HardwareNode", "HardwareInterface", "FunctionalInterface", "TechnologyBinding", "TransportUnit", "PayloadElement"
    ]
    plc = next(item for item in catalog["domains"] if item["id"] == "industrial_automation")
    plc_technologies = {item["id"]: item for item in plc["technologies"]}
    assert plc["device_types"][0] == "PLC"
    assert plc_technologies["profinet"]["default_stack"] == ["ethernet", "profinet"]
    assert plc_technologies["profinet"]["implementation_status"] == "IMPLEMENTED"
