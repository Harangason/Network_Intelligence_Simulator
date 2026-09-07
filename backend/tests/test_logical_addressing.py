import os
import uuid

import pytest

from backend.app import create_app
from backend.engineering.addressing import (
    AddressPolicy,
    LogicalNodeAddress,
    default_addressability_for_class,
    format_logical_node_address,
    parse_logical_node_address,
)
from backend.engineering.db import close_pool, get_connection
from backend.engineering.models import EngineeringValidationError


@pytest.mark.parametrize(
    ("raw", "expected", "formatted"),
    [
        (1, 1, "0x0001"),
        (15, 15, "0x000F"),
        ("12", 0x12, "0x0012"),
        (255, 255, "0x00FF"),
        (4096, 4096, "0x1000"),
        (65534, 65534, "0xFFFE"),
        ("FFFF", 0xFFFF, "0xFFFF"),
    ],
)
def test_logical_address_parse_and_format_are_canonical(raw, expected, formatted):
    assert parse_logical_node_address(raw) == expected
    assert format_logical_node_address(expected) == formatted


@pytest.mark.parametrize("raw", ["", "0x10000", "xyz", -1, 65536, 1.5, True])
def test_invalid_logical_addresses_are_rejected(raw):
    with pytest.raises(EngineeringValidationError):
        parse_logical_node_address(raw)


def test_policy_reserves_protocol_boundaries_and_configured_ranges():
    policy = AddressPolicy(reserved_ranges=(("0x0100", "0x01FF"),))
    assert policy.is_reserved(0x0000)
    assert policy.is_reserved(0xFFFF)
    assert policy.is_reserved(0x0150)
    assert not policy.is_reserved(0x0200)


def test_policy_normalizes_domain_and_device_class_ranges():
    policy = AddressPolicy(
        assignment_strategy="domain_range",
        domain_ranges={"powertrain": {"start": "0x0100", "end": "0x01FF"}},
        device_class_ranges={"4": ("0x0200", "0x02FF")},
    )

    assert policy.assignment_strategy == "DOMAIN_RANGE"
    assert policy.domain_ranges == {"POWERTRAIN": (0x0100, 0x01FF)}
    assert policy.device_class_ranges == {"4": (0x0200, 0x02FF)}
    assert policy.to_dict()["domain_ranges"]["POWERTRAIN"] == {
        "start": "0x0100",
        "end": "0x01FF",
    }


def test_logical_address_value_object_exposes_four_digit_hex():
    address = LogicalNodeAddress(0x23, "vehicle", "manual", "assigned", {"source": "test"})
    assert address.to_dict() == {
        "value": 0x23,
        "namespace": "VEHICLE",
        "assignment_mode": "MANUAL",
        "status": "ASSIGNED",
        "provenance": {"source": "test"},
        "formatted_value": "0x0023",
    }


def test_only_intelligent_subsystems_are_addressable_by_default():
    assert default_addressability_for_class(4) is True
    assert all(default_addressability_for_class(value) is False for value in (0, 1, 2, 3, None, "sensor"))


@pytest.fixture
def addressing_api(monkeypatch):
    database_url = os.environ.get("ENGINEERING_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("ENGINEERING_TEST_DATABASE_URL is required for allocator integration tests")
    monkeypatch.setenv("DATABASE_URL", database_url)
    close_pool()
    project_id = f"logical-address-{uuid.uuid4()}"
    app = create_app(testing=True)
    headers = {"X-Project-ID": project_id}

    def call(method, path, payload=None):
        with app.test_client() as client:
            return client.open(
                f"/api/engineering{path}", method=method, headers=headers, json=payload
            )

    call("GET", "/workflow")
    yield call
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM engineering_workflow_projects WHERE project_id = %s",
            (project_id,),
        )
    close_pool()


def test_allocator_policy_manual_validation_and_namespace_uniqueness(addressing_api):
    call = addressing_api
    policy = call(
        "PATCH",
        "/addressing/policy",
        {
            "reserved_ranges": [{"start": "0x0001", "end": "0x0001"}],
            "device_class_policy": {
                "0": False,
                "1": False,
                "2": False,
                "3": True,
                "4": True,
            },
        },
    )
    assert policy.status_code == 200, policy.get_json()

    class4 = call("POST", "/hardware-nodes", {"name": "CentralGateway", "device_class": 4})
    class3 = call("POST", "/hardware-nodes", {"name": "VisionUnit", "device_class": 3})
    class1 = call("POST", "/hardware-nodes", {"name": "BasicTemperatureSensor", "device_class": 1})
    assert class4.status_code == class3.status_code == class1.status_code == 201
    assert class4.get_json()["formatted_logical_node_address"] == "0x0002"
    assert class3.get_json()["formatted_logical_node_address"] == "0x0003"
    assert class1.get_json()["logical_node_address"] is None

    duplicate = call(
        "PATCH",
        f"/hardware-nodes/{class3.get_json()['id']}/address",
        {"logical_node_address": "0x0002", "confirm": True},
    )
    assert duplicate.status_code == 400
    assert "bereits" in duplicate.get_json()["error"]

    for invalid in ("0x0000", "0xFFFF", "0x10000", "0xGG01"):
        response = call(
            "PATCH",
            f"/hardware-nodes/{class3.get_json()['id']}/address",
            {"logical_node_address": invalid, "confirm": True},
        )
        assert response.status_code == 400, (invalid, response.get_json())

    manual = call(
        "PATCH",
        f"/hardware-nodes/{class3.get_json()['id']}/address",
        {"logical_node_address": "0x0010", "confirm": True},
    )
    assert manual.status_code == 200, manual.get_json()
    assert manual.get_json()["formatted_logical_node_address"] == "0x0010"
    assert manual.get_json()["address_assignment_mode"] == "MANUAL"

    other_namespace = call(
        "POST",
        "/hardware-nodes",
        {
            "name": "NamespacedController",
            "device_class": 4,
            "diagnostic_addressable": True,
            "logical_node_address": "0x0010",
            "address_namespace": "SYSTEM",
            "source": "import",
        },
    )
    assert other_namespace.status_code == 201, other_namespace.get_json()
    assert other_namespace.get_json()["address_assignment_mode"] == "IMPORTED"
    assert other_namespace.get_json()["diagnostic_addressable"] is True
