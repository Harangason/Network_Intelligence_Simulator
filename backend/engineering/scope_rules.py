"""Validation helpers for project-specific engineering scope rules."""

from __future__ import annotations

import re
from typing import Any

from .models import EngineeringValidationError

SCOPE_COUNT_KEYS = ("sensors", "ecus", "gateways")
SUPPORTED_COMMUNICATION_SYSTEMS = {
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
    "MQTT",
    "OPCUA",
    "Other",
}


def normalize_engineering_scope_rules(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EngineeringValidationError("engineering_scope_rules muss ein Objekt sein.")

    raw_counts = value.get("hardware_counts")
    if not isinstance(raw_counts, dict):
        raise EngineeringValidationError("engineering_scope_rules.hardware_counts muss ein Objekt sein.")

    counts: dict[str, int] = {}
    for key in SCOPE_COUNT_KEYS:
        raw_count = raw_counts.get(key)
        if isinstance(raw_count, bool) or not isinstance(raw_count, int) or raw_count < 0:
            raise EngineeringValidationError(
                f"engineering_scope_rules.hardware_counts.{key} muss eine nicht-negative Ganzzahl sein."
            )
        counts[key] = raw_count

    raw_systems = value.get("communication_systems") or []
    if not isinstance(raw_systems, list) or not all(isinstance(item, str) for item in raw_systems):
        raise EngineeringValidationError("engineering_scope_rules.communication_systems muss eine Liste sein.")
    systems = list(dict.fromkeys(item.strip() for item in raw_systems if item.strip()))
    unsupported = [item for item in systems if item not in SUPPORTED_COMMUNICATION_SYSTEMS]
    if unsupported:
        raise EngineeringValidationError(
            f"Nicht unterstuetzte Kommunikationssysteme in engineering_scope_rules: {unsupported}."
        )

    enforcement = str(value.get("enforcement") or "exact").strip().lower()
    if enforcement != "exact":
        raise EngineeringValidationError("engineering_scope_rules.enforcement muss 'exact' sein.")

    return {
        "version": 1,
        "source": str(value.get("source") or "engineering-specification").strip(),
        "enforcement": "exact",
        "hardware_counts": counts,
        "communication_systems": systems,
    }


def hardware_scope_category(device_type: Any) -> str | None:
    return {
        "SensorController": "sensors",
        "ECU": "ecus",
        "Gateway": "gateways",
    }.get(str(device_type or ""))


def is_scope_placeholder_hardware(name: Any, source: Any) -> bool:
    if str(source or "") != "ai_generated":
        return False
    normalized = re.sub(r"[^a-z0-9]+", " ", str(name or "").casefold()).strip()
    if normalized in {"ecu", "ecus", "gateway", "gateways", "sensor", "sensoren", "sensors"}:
        return True
    return bool(
        re.match(r"^\d+\s+.*(?:sensor(?:en|s)?|ecu(?:s)?|gateway(?:s)?)$", normalized)
    )


def scope_placeholder_sql(alias: str) -> str:
    if alias not in {"h", "engineering_hardware_nodes"}:
        raise ValueError("Unbekannter SQL-Alias fuer Scope-Platzhalter.")
    return (
        f"({alias}.source = 'ai_generated' AND ("
        f"LOWER(BTRIM({alias}.name)) IN ('ecu', 'ecus', 'gateway', 'gateways', 'sensor', 'sensoren', 'sensors') "
        f"OR LOWER(BTRIM({alias}.name)) ~ '^[0-9]+[[:space:]].*(sensor(en|s)?|ecu(s)?|gateway(s)?)$'"
        "))"
    )
