"""Validation helpers for project-specific engineering scope rules."""

from __future__ import annotations

import re
from typing import Any

from .models import EngineeringValidationError

SCOPE_COUNT_KEYS = ("sensors", "ecus", "gateways", "actuators")
SUPPORTED_COMMUNICATION_SYSTEMS = {
    "CAN",
    "CAN_FD",
    "LIN",
    "FlexRay",
    "Ethernet",
    "SOME_IP",
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
}

COMMUNICATION_SYSTEM_ALIASES = {
    "AUTOMOTIVE_ETHERNET": "Ethernet",
    "ETHERNET": "Ethernet",
    "ETH": "Ethernet",
    "CANFD": "CAN_FD",
    "CAN_FD": "CAN_FD",
    "CAN_CLASSIC": "CAN",
    "CAN": "CAN",
    "LIN": "LIN",
    "SOMEIP": "SOME_IP",
    "SOME_IP": "SOME_IP",
    "SOME/IP": "SOME_IP",
    "SOME-IP": "SOME_IP",
    "FLEXRAY": "FlexRay",
    "ETHERCAT": "EtherCAT",
    "PROFINET": "ProfiNET",
    "MODBUSTCP": "ModbusTCP",
    "MODBUS_TCP": "ModbusTCP",
    "MODBUSRTU": "ModbusRTU",
    "MODBUS_RTU": "ModbusRTU",
    "OPCUA": "OPCUA",
    "OPC_UA": "OPCUA",
    "MQTT": "MQTT",
    "RS232": "RS232",
    "RS485": "RS485",
    "SPI": "SPI",
    "I2C": "I2C",
    "USB": "USB",
    "PCIE": "PCIe",
    "ARINC": "ARINC",
    "ARINC429": "ARINC",
    "ARINC_429": "ARINC",
    "MIL_STD_1553": "MIL_STD_1553",
    "MILSTD1553": "MIL_STD_1553",
    "OTHER": "Other",
}


def canonical_communication_system(value: Any) -> str:
    raw = str(value or "").strip()
    key = re.sub(r"[^A-Z0-9]+", "_", raw.upper()).strip("_")
    if raw.upper() == "SOME/IP":
        key = "SOME/IP"
    return COMMUNICATION_SYSTEM_ALIASES.get(key) or COMMUNICATION_SYSTEM_ALIASES.get(raw.upper(), raw)


def communication_system_allows_interface(allowed_systems: list[str], interface_type: Any) -> bool:
    if not allowed_systems:
        return True
    actual = canonical_communication_system(interface_type)
    allowed = {canonical_communication_system(item) for item in allowed_systems}
    if actual in allowed:
        return True
    # SOME/IP is modeled as a protocol carried by an Ethernet engineering interface.
    if actual == "Ethernet" and "SOME_IP" in allowed:
        return True
    if actual == "SOME_IP" and "Ethernet" in allowed:
        return True
    return False


def normalize_engineering_scope_rules(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EngineeringValidationError("engineering_scope_rules muss ein Objekt sein.")

    raw_counts = value.get("hardware_counts")
    if not isinstance(raw_counts, dict):
        raise EngineeringValidationError("engineering_scope_rules.hardware_counts muss ein Objekt sein.")

    counts: dict[str, int] = {}
    for key in SCOPE_COUNT_KEYS:
        # Legacy projects did not constrain actuators; do not silently impose zero.
        if key == "actuators" and key not in raw_counts:
            continue
        raw_count = raw_counts.get(key)
        if isinstance(raw_count, bool) or not isinstance(raw_count, int) or raw_count < 0:
            raise EngineeringValidationError(
                f"engineering_scope_rules.hardware_counts.{key} muss eine nicht-negative Ganzzahl sein."
            )
        counts[key] = raw_count

    raw_systems = value.get("communication_systems") or []
    if not isinstance(raw_systems, list) or not all(isinstance(item, str) for item in raw_systems):
        raise EngineeringValidationError("engineering_scope_rules.communication_systems muss eine Liste sein.")
    systems = list(dict.fromkeys(canonical_communication_system(item) for item in raw_systems if item.strip()))
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
        "ActuatorController": "actuators",
        "ECU": "ecus",
        "Gateway": "gateways",
    }.get(str(device_type or ""))


def scope_count_mismatches(hardware_by_type: dict[str, int], rules: Any) -> dict[str, Any]:
    if not rules:
        return {}
    limits = normalize_engineering_scope_rules(rules)["hardware_counts"]
    actual = dict.fromkeys(SCOPE_COUNT_KEYS, 0)
    for device_type, count in hardware_by_type.items():
        category = hardware_scope_category(device_type)
        if category:
            actual[category] += count
    return {key: {"target": target, "actual": actual[key]}
            for key, target in limits.items() if actual[key] != target}


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
