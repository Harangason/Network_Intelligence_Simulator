"""Deterministic signal and network integrity checks for generated models."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and result not in {float("inf"), float("-inf")} else None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _severity(checks: list[dict[str, Any]]) -> str:
    if any(item["severity"] == "ERROR" for item in checks):
        return "ERROR"
    if any(item["severity"] == "OPEN" for item in checks):
        return "OPEN"
    if checks:
        return "WARNING"
    return "PASS"


def required_signal_bits(signal: dict[str, Any]) -> int | None:
    data_type = _text(signal.get("data_type")).lower()
    factor = _number(signal.get("factor"))
    offset = _number(signal.get("offset_value"))
    minimum = _number(signal.get("min_value"))
    maximum = _number(signal.get("max_value"))
    if factor is None or factor == 0 or offset is None or minimum is None or maximum is None or minimum >= maximum:
        return None
    if data_type in {"float", "double", "float32", "float64", "enum"}:
        return None
    signed = data_type in {"signed", "int", "int8", "int16", "int32", "int64", "sint8", "sint16", "sint32", "sint64"} or minimum < 0
    raw_min = round((minimum - offset) / factor)
    raw_max = round((maximum - offset) / factor)
    if abs(raw_min - ((minimum - offset) / factor)) > 1e-8 or abs(raw_max - ((maximum - offset) / factor)) > 1e-8:
        return None
    for width in range(1, 65):
        if signed:
            if raw_min >= -(2 ** (width - 1)) and raw_max < 2 ** (width - 1):
                return width
        elif raw_min >= 0 and raw_max < 2 ** width:
            return width
    return 64


def occupied_signal_bits(signal: dict[str, Any]) -> set[int] | None:
    start = _number(signal.get("start_bit"))
    length = _number(signal.get("length_bits"))
    byte_order = _text(signal.get("byte_order"))
    if start is None or length is None or int(start) != start or int(length) != length or start < 0 or length <= 0:
        return None
    if byte_order not in {"little_endian", "big_endian"}:
        return None
    position = int(start)
    occupied: set[int] = set()
    for _ in range(int(length)):
        occupied.add(position)
        position = position + 1 if byte_order == "little_endian" else position + 15 if position % 8 == 0 else position - 1
    return occupied


def inspect_signal(signal: dict[str, Any], message: dict[str, Any] | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(code: str, severity: str, text: str) -> None:
        checks.append({"code": code, "severity": severity, "text": text})

    length = _number(signal.get("length_bits"))
    start = _number(signal.get("start_bit"))
    byte_order = _text(signal.get("byte_order"))
    data_type = _text(signal.get("data_type")).lower()
    if length is None or int(length) != length or length <= 0:
        add("SIGNAL_BIT_LENGTH_MISSING", "OPEN", "Signalbitlaenge fehlt oder ist ungueltig.")
    if start is None or int(start) != start or start < 0:
        add("SIGNAL_START_BIT_MISSING", "OPEN", "Startbit fehlt oder ist ungueltig.")
    if byte_order not in {"little_endian", "big_endian"}:
        add("SIGNAL_BYTE_ORDER_MISSING", "OPEN", "Byte-Reihenfolge fehlt.")
    if not data_type:
        add("SIGNAL_DATA_TYPE_MISSING", "OPEN", "Datentyp fehlt.")

    occupied = occupied_signal_bits(signal)
    dlc = _number((message or {}).get("dlc"))
    if not message:
        add("SIGNAL_MESSAGE_MISSING", "OPEN", "Zugeordnete Nachricht fehlt.")
    elif dlc is None or int(dlc) != dlc or dlc < 0:
        add("MESSAGE_DLC_MISSING", "OPEN", "Nachrichten-DLC fehlt oder ist ungueltig.")
    elif occupied and any(bit >= int(dlc) * 8 for bit in occupied):
        add("SIGNAL_PAYLOAD_OVERFLOW", "ERROR", f"Signal liegt ausserhalb der {int(dlc)} Byte grossen Nachricht.")

    required = required_signal_bits(signal)
    if required is None and not any(item["code"].startswith("SIGNAL_") for item in checks):
        add("SIGNAL_BIT_NEED_OPEN", "OPEN", "Wertebereich, Skalierung oder Datentyp reichen fuer eine Bitoptimierung nicht aus.")
    if length is not None and required is not None:
        if required > int(length):
            add("SIGNAL_TOO_NARROW", "ERROR", f"{int(length)} Bit reichen nicht; mindestens {required} Bit sind erforderlich.")
        elif required < int(length):
            add("SIGNAL_OVERSIZED", "WARNING", f"Rechnerisch {required} statt {int(length)} Bit ausreichend; fachliche Reserven pruefen.")

    return {
        "signal_id": _text(signal.get("id")),
        "name": _text(signal.get("display_name")) or _text(signal.get("name")) or _text(signal.get("id")),
        "message_id": _text(signal.get("message_id")),
        "message_name": _text((message or {}).get("name")),
        "length_bits": int(length) if length is not None and int(length) == length else None,
        "required_bits": required,
        "start_bit": int(start) if start is not None and int(start) == start else None,
        "byte_order": byte_order,
        "data_type": data_type,
        "min_value": _number(signal.get("min_value")),
        "max_value": _number(signal.get("max_value")),
        "factor": _number(signal.get("factor")),
        "offset_value": _number(signal.get("offset_value")),
        "unit": _text(signal.get("unit")),
        "occupied_bits": sorted(occupied) if occupied else None,
        "checks": checks,
        "status": _severity(checks),
    }


def inspect_message_signals(signals: list[dict[str, Any]], message: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    inspected = [inspect_signal(signal, message) for signal in signals]
    occupants: dict[int, list[int]] = defaultdict(list)
    for index, item in enumerate(inspected):
        for bit in item.get("occupied_bits") or []:
            occupants[int(bit)].append(index)
    for indexes in occupants.values():
        if len(indexes) < 2:
            continue
        for index in indexes:
            others = [inspected[other]["name"] for other in indexes if other != index]
            inspected[index]["checks"].append({
                "code": "SIGNAL_OVERLAP",
                "severity": "ERROR",
                "text": "Bitueberlappung mit " + ", ".join(others) + ".",
            })
            inspected[index]["status"] = _severity(inspected[index]["checks"])
    return inspected


def build_generation_signal_audit(
    *,
    hardware: list[dict[str, Any]],
    interfaces: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    routes: list[dict[str, Any]],
    topology: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hardware_by_id = {_text(item.get("id")): item for item in hardware}
    interfaces_by_id = {_text(item.get("id")): item for item in interfaces}
    messages_by_id = {_text(item.get("id")): item for item in messages}
    signals_by_message: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        signals_by_message[_text(signal.get("message_id"))].append(signal)

    signal_checks: list[dict[str, Any]] = []
    messages_summary: list[dict[str, Any]] = []
    for message in messages:
        message_signals = signals_by_message.get(_text(message.get("id")), [])
        inspected = inspect_message_signals(message_signals, message)
        signal_checks.extend(inspected)
        occupied = {bit for item in inspected for bit in item.get("occupied_bits") or []}
        messages_summary.append({
            "message_id": _text(message.get("id")),
            "name": _text(message.get("name")),
            "signal_count": len(message_signals),
            "dlc": int(_number(message.get("dlc")) or 0),
            "occupied_bits": len(occupied),
            "minimum_dlc": max(1, (max(occupied) + 8) // 8) if occupied else None,
        })

    network_participants: dict[str, dict[str, Any]] = {}

    def system_frame(node_id: str) -> dict[str, Any] | None:
        node = hardware_by_id.get(node_id)
        if not node:
            return None
        if _text(node.get("device_type")).lower() == "ecu":
            return {"id": node_id, "name": _text(node.get("name")) or node_id, "basis": "self"}
        owner_id = _text(_as_dict(node.get("identity")).get("system_owner_id"))
        owner = hardware_by_id.get(owner_id)
        if owner:
            return {"id": owner_id, "name": _text(owner.get("name")) or owner_id, "basis": "explicit"}
        return None

    for route in routes:
        source = _as_dict(route.get("source"))
        network_id = _text(source.get("network_id") or source.get("interface_id") or source.get("protocol") or "unassigned")
        summary = network_participants.setdefault(network_id, {"network_id": network_id, "participants": {}, "signal_ids": set(), "message_ids": set()})
        for endpoint, role in [(source, "Sender"), *[(_as_dict(item), "Teilnehmer") for item in route.get("destinations") or []]]:
            node_id = _text(endpoint.get("node_id"))
            if not node_id:
                continue
            node = hardware_by_id.get(node_id, {})
            participant = summary["participants"].setdefault(node_id, {
                "id": node_id,
                "name": _text(node.get("name")) or node_id,
                "type": _text(node.get("device_type")),
                "roles": set(),
                "interfaces": set(),
                "system_frame": system_frame(node_id),
            })
            participant["roles"].add(role)
            interface_id = _text(endpoint.get("interface_id"))
            if interface_id:
                participant["interfaces"].add(_text(interfaces_by_id.get(interface_id, {}).get("name")) or interface_id)
        payload = _as_dict(route.get("payload"))
        for key in ("message_id",):
            if payload.get(key):
                summary["message_ids"].add(_text(payload.get(key)))
        for message_id in payload.get("message_ids") or []:
            summary["message_ids"].add(_text(message_id))
        for signal_id in payload.get("signal_ids") or []:
            summary["signal_ids"].add(_text(signal_id))

    networks = []
    for summary in network_participants.values():
        participants = []
        for participant in summary["participants"].values():
            participants.append({
                **participant,
                "roles": sorted(participant["roles"]),
                "interfaces": sorted(participant["interfaces"]),
            })
        networks.append({
            "network_id": summary["network_id"],
            "participant_count": len(participants),
            "sender_count": sum("Sender" in item["roles"] for item in participants),
            "system_frame_count": len({(item.get("system_frame") or {}).get("id") for item in participants if item.get("system_frame")}),
            "message_count": len(summary["message_ids"]),
            "signal_count": len(summary["signal_ids"]),
            "participants": sorted(participants, key=lambda item: item["name"]),
        })

    issue_checks = [item for item in signal_checks if item["status"] != "PASS"]
    return {
        "summary": {
            "networks": len(networks),
            "participants": sum(item["participant_count"] for item in networks),
            "messages": len(messages),
            "signals": len(signals),
            "passed": sum(item["status"] == "PASS" for item in signal_checks),
            "warnings": sum(item["status"] == "WARNING" for item in signal_checks),
            "errors": sum(item["status"] == "ERROR" for item in signal_checks),
            "open": sum(item["status"] == "OPEN" for item in signal_checks),
        },
        "networks": sorted(networks, key=lambda item: item["network_id"]),
        "messages": messages_summary,
        "signals": signal_checks,
        "issues": issue_checks,
        "topology_available": bool((topology or {}).get("nodes")),
        "ai_assist_context": "Signal- und Netzdiagnose fuer KI-gestuetzte Vorschlaege; keine automatische Freigabe.",
    }
