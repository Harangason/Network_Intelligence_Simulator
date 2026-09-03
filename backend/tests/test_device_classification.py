from __future__ import annotations

import pytest

from backend.engineering.device_classification import DeviceClassificationRegistry
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
