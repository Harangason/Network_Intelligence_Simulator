"""Kanonisches Engineering-Modell: Enums und Objekttyp-Definitionen.

Dieses Modul definiert ausschließlich die Vokabulare (erlaubte Werte) für die
Engineering-Objekte. Die eigentliche Persistenz erfolgt spaltenbasiert in
Postgres (siehe ``engineering/repository.py``); dataclasses werden hier nur
für Validierungszwecke und IDE-Unterstützung bereitgestellt.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .device_classification import (
    CLASSIFICATION_STATUSES,
    DATA_COMPLEXITIES,
    DEVICE_CLASSES,
    DEVICE_TYPINGS_BY_CLASS,
)

# ---------------------------------------------------------------------------
# Gemeinsame Governance-Vokabulare (gelten für jedes EngineeringObject)
# ---------------------------------------------------------------------------

LIFECYCLE_STATES = ("draft", "active", "deprecated", "superseded")
SOURCES = ("manual", "import", "ai_generated", "simulation_derived")
REVIEW_STATES = ("unreviewed", "in_review", "reviewed", "rejected")
APPROVAL_STATES = ("pending", "approved", "rejected")

# ---------------------------------------------------------------------------
# HardwareNode: ECU ist nur noch ein möglicher Gerätetyp unter vielen.
# ---------------------------------------------------------------------------

DEVICE_TYPES = (
    "ECU",
    "PLC",
    "RobotController",
    "SensorController",
    "ActuatorController",
    "Gateway",
    "EmbeddedController",
    "IndustrialPC",
    "FlightComputer",
    "BatteryManagementSystem",
    "EnergyController",
    "BuildingController",
    "GenericDevice",
    "CustomDevice",
)

# ---------------------------------------------------------------------------
# Interface: protokoll-agnostisch, Signal wird separat modelliert.
# ---------------------------------------------------------------------------

INTERFACE_TYPES = (
    "CAN",
    "CAN_FD",
    "LIN",
    "FlexRay",
    "Ethernet",
    "EtherCAT",
    "ProfiNET",
    "ModbusTCP",
    "ModbusRTU",
    "RS232",
    "RS485",
    "SPI",
    "I2C",
    "USB",
    "PCIe",
    "MQTT",
    "OPCUA",
    "ARINC",
    "MIL_STD_1553",
    "Other",
)

DEVICE_TYPINGS = tuple(
    typing
    for typings in DEVICE_TYPINGS_BY_CLASS.values()
    for typing in typings
)

MESSAGE_DIRECTIONS = ("rx", "tx", "bidirectional")
SIGNAL_BYTE_ORDERS = ("little_endian", "big_endian")

# Engineering-Objekttypen, die in engineering_relations als source_type /
# target_type referenziert werden können.
RELATABLE_OBJECT_TYPES = (
    "HardwareNode",
    "HardwareNetworkInterface",
    "Function",
    "Interface",
    "Message",
    "Signal",
    "RoutingEntry",
)

# Mindest-Vokabular für Kantentypen im Knowledge Graph (Abschnitt 7 der Spec).
RELATION_TYPES = (
    "HAS_FUNCTION",
    "HAS_CAPABILITY",
    "HAS_PORT",
    "HAS_HARDWARE_INTERFACE",
    "HAS_INTERFACE",
    "CONNECTED_TO",
    "COMMUNICATES_WITH",
    "PROVIDES",
    "CONSUMES",
    "SENDS",
    "RECEIVES",
    "HAS_MESSAGE",
    "CONTAINS_SIGNAL",
    "RUNS_ON",
    "MAPPED_TO",
    "USES_PROTOCOL",
    "CONNECTED_VIA",
    "DERIVED_FROM",
    "DEFINED_BY",
    "IMPORTED_FROM",
    "SUPPORTED_BY",
    "VALIDATED_BY",
    "CONFLICTS_WITH",
    "DEPENDS_ON",
    "RELATED_TO",
    "SIMULATED_IN",
    "FAILED_IN",
    "OBSERVED_IN",
    "REPLACES",
    "VERSION_OF",
    "USES_NETWORK",
    "PRODUCES",
    "ROUTES_TO",
    "ROUTES_VIA",
    "HAS_GATEWAY",
    "BRIDGES_NETWORK",
    "TRANSLATES_PROTOCOL",
    "CONTAINS_MESSAGE",
    "HAS_ROUTE",
    "USES_ROUTE",
)


class EngineeringValidationError(ValueError):
    """Wird ausgelöst, wenn ein Wert nicht im erlaubten Vokabular liegt."""


def validate_choice(value: str, allowed: tuple[str, ...], field_name: str) -> str:
    if value not in allowed:
        raise EngineeringValidationError(
            f"Ungültiger Wert für {field_name!r}: {value!r}. "
            f"Erlaubt sind: {', '.join(allowed)}."
        )
    return value


def validate_uuid(value: str) -> str:
    try:
        uuid.UUID(str(value))
    except (ValueError, AttributeError) as error:
        raise EngineeringValidationError(f"Ungültige UUID: {value!r}") from error
    return str(value)


@dataclass
class GovernanceFields:
    """Provenance-/Review-/Approval-Felder, die jedes Objekt trägt."""

    source: str = "manual"
    provenance: dict[str, Any] = field(default_factory=dict)
    confidence: float | None = None
    review_state: str = "unreviewed"
    approval_state: str = "pending"

    def __post_init__(self) -> None:
        validate_choice(self.source, SOURCES, "source")
        validate_choice(self.review_state, REVIEW_STATES, "review_state")
        validate_choice(self.approval_state, APPROVAL_STATES, "approval_state")
