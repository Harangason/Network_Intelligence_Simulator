import pytest

from backend.engineering.models import EngineeringValidationError
from backend.engineering.scope_rules import (
    hardware_scope_category,
    is_scope_placeholder_hardware,
    normalize_engineering_scope_rules,
)
from backend.engineering.repository import _enforce_engineering_scope_rules


class ScopeRuleConnection:
    def __init__(self, rules, count=0):
        self.rules = rules
        self.count = count

    def execute(self, query, _values):
        if "SELECT context" in query:
            return ScopeRuleResult({"context": {"engineering_scope_rules": self.rules}})
        if "SELECT count(*)" in query:
            return ScopeRuleResult({"count": self.count})
        raise AssertionError(f"Unerwartete Abfrage: {query}")


class ScopeRuleResult:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


def test_scope_rules_normalize_exact_system_limits():
    rules = normalize_engineering_scope_rules(
        {
            "source": "engineering-specification",
            "enforcement": "exact",
            "hardware_counts": {"sensors": 100, "ecus": 50, "gateways": 1},
            "communication_systems": ["LIN", "CAN_FD", "Ethernet", "LIN"],
        }
    )

    assert rules == {
        "version": 1,
        "source": "engineering-specification",
        "enforcement": "exact",
        "hardware_counts": {"sensors": 100, "ecus": 50, "gateways": 1},
        "communication_systems": ["LIN", "CAN_FD", "Ethernet"],
    }


@pytest.mark.parametrize(
    ("device_type", "category"),
    [
        ("SensorController", "sensors"),
        ("ECU", "ecus"),
        ("Gateway", "gateways"),
        ("PLC", None),
    ],
)
def test_hardware_scope_category(device_type, category):
    assert hardware_scope_category(device_type) == category


def test_scope_rules_reject_unknown_communication_system():
    with pytest.raises(EngineeringValidationError, match="Nicht unterstuetzte"):
        normalize_engineering_scope_rules(
            {
                "hardware_counts": {"sensors": 100, "ecus": 50, "gateways": 1},
                "communication_systems": ["SpaceBus"],
            }
        )


def test_hardware_creation_is_blocked_at_exact_limit():
    rules = {
        "hardware_counts": {"sensors": 100, "ecus": 50, "gateways": 1},
        "communication_systems": ["LIN", "CAN_FD", "Ethernet"],
    }
    connection = ScopeRuleConnection(rules, count=50)

    with pytest.raises(EngineeringValidationError, match="exakt 50"):
        _enforce_engineering_scope_rules(
            connection,
            "HardwareNode",
            {"device_type": "ECU"},
            "project-a",
        )


def test_interface_creation_must_use_allowed_communication_system():
    rules = {
        "hardware_counts": {"sensors": 100, "ecus": 50, "gateways": 1},
        "communication_systems": ["LIN", "CAN_FD", "Ethernet"],
    }
    connection = ScopeRuleConnection(rules)

    with pytest.raises(EngineeringValidationError, match="nicht erlaubt"):
        _enforce_engineering_scope_rules(
            connection,
            "Interface",
            {"interface_type": "FlexRay"},
            "project-a",
        )


@pytest.mark.parametrize(
    ("name", "source", "expected"),
    [
        ("1 zentrales Gateway", "ai_generated", True),
        ("Gateway", "ai_generated", True),
        ("100 Sensoren", "ai_generated", True),
        ("System-Gateway", "ai_generated", False),
        ("Gateway", "manual", False),
    ],
)
def test_scope_placeholder_detection(name, source, expected):
    assert is_scope_placeholder_hardware(name, source) is expected
