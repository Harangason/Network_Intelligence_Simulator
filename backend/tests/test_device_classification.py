from __future__ import annotations

import pytest

from backend.engineering.device_classification import (
    DeviceClassificationRegistry, TechnologyCandidateResolver, DEVICE_CLASS_PROFILES,
)
from backend.engineering import schema as engineering_schema


@pytest.mark.parametrize(
    ("name", "device_type", "device_class", "typing", "complexity", "auto_function"),
    [
        ("CoolantTemperature", "SensorController", 1, "Basic Sensor", "PHYSICAL_SCALAR", "NO"),
        ("BrakeServo", "ActuatorController", 2, "Controlled Actuator", "CONTROL_COMMAND", "NO"),
        ("FrontCamera", "SensorController", 3, "Perception Sensor", "IMAGE_STREAM", "YES"),
        ("CentralGateway", "Gateway", 4, "Intelligent Subsystem", "SERVICE_DATA", "YES"),
        ("Motorsteuerung", "ECU", 4, "Intelligent Subsystem", "SERVICE_DATA", "YES"),
        ("Elektromotorsteuerung", "ECU", 4, "Intelligent Subsystem", "SERVICE_DATA", "YES"),
    ],
)
def test_device_classification_registry_resolves_generator_policy(
    name: str,
    device_type: str,
    device_class: int,
    typing: str,
    complexity: str,
    auto_function: str,
) -> None:
    profile = DeviceClassificationRegistry().resolve_profile(name=name, device_type=device_type)

    assert profile.device_class == device_class
    assert profile.device_typing == typing
    assert profile.data_complexity == complexity
    assert profile.generator_policy["auto_function"] == auto_function


def test_user_confirmed_classification_wins_over_heuristic() -> None:
    profile = DeviceClassificationRegistry().resolve_profile(
        name="DigitalPressureSensor",
        device_type="SensorController",
        device_class=2,
        device_typing="Smart Sensor",
        data_complexity="MULTI_VALUE",
    )

    assert profile.device_class == 2
    assert profile.device_typing == "Smart Sensor"
    assert profile.data_complexity == "MULTI_VALUE"
    assert profile.provenance == "user_confirmed"


def test_main_controller_keeps_controller_capabilities_without_gatewaying() -> None:
    profile = DeviceClassificationRegistry().resolve_profile(
        name="RaspberryPi",
        device_type="EmbeddedController",
        device_typing="Main Controller",
    )

    assert profile.device_class == 4
    assert profile.device_typing == "Main Controller"
    assert profile.device_role == "controller"
    assert profile.requires_function_model is True
    assert profile.communication_capabilities == ("network_endpoint",)


def test_invalid_typing_falls_back_to_class_default() -> None:
    profile = DeviceClassificationRegistry().resolve_profile(
        name="FrontCamera",
        device_type="SensorController",
        device_class=3,
        device_typing="Basic Sensor",
    )

    assert profile.device_class == 3
    assert profile.device_typing == "Perception Sensor"


def test_schema_contains_device_class_columns_and_indexes() -> None:
    ddl = "\n".join(engineering_schema.MIGRATION_STATEMENTS)

    assert "device_class INTEGER" in ddl
    assert "device_typing TEXT" in ddl
    assert "data_complexity TEXT" in ddl
    assert "classification_status TEXT" in ddl
    assert "capability_profile_ref TEXT" in ddl
    assert "idx_hardware_nodes_device_class" in ddl


def test_class_profile_does_not_choose_a_technology_without_hardware():
    assert set(DEVICE_CLASS_PROFILES) == set(range(5))
    resolver = TechnologyCandidateResolver()
    assert resolver.resolve(device_class=2, data_complexity="PHYSICAL_SCALAR", hardware_capabilities=[]) == []
    choices = resolver.resolve(device_class=2, data_complexity="PHYSICAL_SCALAR",
                               hardware_capabilities=["i2c_controller", "spi_controller"])
    assert {row["technology_id"] for row in choices} >= {"i2c", "spi"}
    assert all(row["status"] == "REVIEW_REQUIRED" for row in choices)


def test_image_stream_filters_low_bandwidth_and_direct_io_candidates():
    choices = TechnologyCandidateResolver().resolve(device_class=3, data_complexity="IMAGE_STREAM",
        hardware_capabilities=["gpio_port", "lin_channel", "ethernet_port"],
        existing_interfaces=["ethernet"])
    assert choices[0]["technology_id"] == "ethernet"
    assert all(row["technology_id"] not in {"gpio", "lin"} for row in choices)


def test_actuator_role_wins_over_camera_system_prefix():
    profile = DeviceClassificationRegistry().resolve_profile(
        name="KameraverarbeitungStellglied", device_type="ActuatorController")
    assert profile.device_class == 1
    assert profile.data_complexity == "CONTROL_COMMAND"
