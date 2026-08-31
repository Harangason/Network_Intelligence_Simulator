"""Preview and import Engineering files into the canonical hierarchy."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import threading
import zipfile
from pathlib import PurePath
from typing import Any
from xml.etree import ElementTree

import yaml

from .db import get_connection
from .models import DEVICE_TYPES, INTERFACE_TYPES, EngineeringValidationError
from .repository import ENTITY_SPECS, create_object

IMPORT_ORIGIN = "engineering-import"
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()

FIELD_ALIASES = {
    "domain": ("domain", "industry", "application_domain", "anwendungsbereich"),
    "hardware": ("hardware", "hardware_name", "node", "node_name", "ecu", "device", "device_name", "asset", "asset_name"),
    "device_type": ("device_type", "hardware_type", "node_type", "kind"),
    "function": ("function", "function_name", "funktion", "service", "service_name", "runnable"),
    "interface": ("interface", "interface_name", "channel", "port", "connector"),
    "interface_type": ("interface_type", "bus", "bus_type", "protocol", "technology", "network", "network_type"),
    "message": ("message", "message_name", "frame", "frame_name", "pdu", "pdu_name", "telegram", "telegram_name", "packet", "nachricht"),
    "message_id_hex": ("message_id_hex", "message_id", "frame_id", "can_id", "id"),
    "direction": ("direction", "richtung"),
    "cycle_ms": ("cycle_ms", "cycle", "zyklus_ms"),
    "dlc": ("dlc", "payload_bytes", "length_bytes"),
    "signal": ("signal", "signal_name", "signalname", "data_element", "data_element_name", "variable", "variable_name"),
    "start_bit": ("start_bit", "startbit", "bit_start"),
    "length_bits": ("length_bits", "signal_length", "bit_length", "length"),
    "byte_order": ("byte_order", "endianness", "byteorder"),
    "data_type": ("data_type", "datatype", "signal_type"),
    "factor": ("factor", "scale"),
    "offset_value": ("offset_value", "offset"),
    "unit": ("unit", "einheit"),
    "min_value": ("min_value", "minimum", "min"),
    "max_value": ("max_value", "maximum", "max"),
}


def _lock(import_id: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(import_id, threading.Lock())


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "item"


def _number(value: Any, *, integer: bool = False) -> int | float | None:
    text = str(value or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        return int(float(text)) if integer else float(text)
    except ValueError:
        return None


def _normalized_header(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise EngineeringValidationError("Die Textdatei konnte nicht dekodiert werden.")


def _csv_records(content: bytes) -> tuple[list[dict[str, str]], list[str]]:
    text = _decode_text(content)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    original_headers = [str(header or "").strip() for header in (reader.fieldnames or [])]
    if not original_headers:
        raise EngineeringValidationError("Die CSV-Datei enthält keine Kopfzeile.")
    records: list[dict[str, str]] = []
    for row in reader:
        records.append(
            {
                _normalized_header(key): str(value or "").strip()
                for key, value in row.items()
                if key is not None
            }
        )
    return records, original_headers


def _xlsx_rows(content: bytes) -> list[list[str]]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as error:
        raise EngineeringValidationError("Die XLSX-Datei ist beschädigt oder ungültig.") from error
    with archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root:
                shared.append("".join(text.text or "" for text in item.iter() if text.tag.endswith("}t")))
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        sheet = next((item for item in workbook.iter() if item.tag.endswith("}sheet")), None)
        if sheet is None:
            raise EngineeringValidationError("Die XLSX-Datei enthält kein Arbeitsblatt.")
        relation_id = next((value for key, value in sheet.attrib.items() if key.endswith("}id")), None)
        relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target = next(
            (item.attrib.get("Target") for item in relationships if item.attrib.get("Id") == relation_id),
            None,
        )
        if not target:
            raise EngineeringValidationError("Das erste XLSX-Arbeitsblatt konnte nicht gelesen werden.")
        sheet_path = "xl/" + target.lstrip("/").removeprefix("xl/")
        root = ElementTree.fromstring(archive.read(sheet_path))
        rows: list[list[str]] = []
        for row in (item for item in root.iter() if item.tag.endswith("}row")):
            values: dict[int, str] = {}
            for cell in (item for item in row if item.tag.endswith("}c")):
                reference = cell.attrib.get("r", "A1")
                letters = re.match(r"[A-Z]+", reference)
                column = 0
                for char in letters.group(0) if letters else "A":
                    column = column * 26 + ord(char) - 64
                cell_type = cell.attrib.get("t")
                value_node = next((item for item in cell.iter() if item.tag.endswith("}v")), None)
                inline_text = "".join(
                    item.text or "" for item in cell.iter() if item.tag.endswith("}t")
                )
                raw = inline_text if cell_type == "inlineStr" else (value_node.text or "" if value_node is not None else "")
                if cell_type == "s" and raw:
                    raw = shared[int(raw)]
                values[column - 1] = raw
            if values:
                rows.append([values.get(index, "") for index in range(max(values) + 1)])
        return rows


def _xlsx_records(content: bytes) -> tuple[list[dict[str, str]], list[str]]:
    rows = _xlsx_rows(content)
    if not rows:
        raise EngineeringValidationError("Das XLSX-Arbeitsblatt ist leer.")
    headers = [str(value).strip() for value in rows[0]]
    normalized = [_normalized_header(value) for value in headers]
    records = [
        {header: str(row[index] if index < len(row) else "").strip() for index, header in enumerate(normalized) if header}
        for row in rows[1:]
    ]
    return records, headers


def _scalar(value: Any) -> str:
    if value is None or isinstance(value, (dict, list, tuple)):
        return ""
    return str(value).strip()


def _first_named_value(item: dict[str, Any]) -> str:
    for key in ("name", "short_name", "short-name", "display_name", "id", "identifier"):
        value = _scalar(item.get(key))
        if value:
            return value
    return ""


def _flatten_mapping(item: dict[str, Any], prefix: str = "") -> dict[str, str]:
    record: dict[str, str] = {}
    for key, value in item.items():
        normalized = _normalized_header(f"{prefix}_{key}" if prefix else key)
        if isinstance(value, dict):
            record.update(_flatten_mapping(value, normalized))
        elif isinstance(value, list):
            continue
        else:
            record[normalized] = _scalar(value)
    return record


def _record_from_collection_item(collection: str, item: dict[str, Any]) -> dict[str, str]:
    record = _flatten_mapping(item)
    normalized_collection = _normalized_header(collection)
    name = _first_named_value(item)
    if not name:
        return record
    if normalized_collection in {"hardware", "hardware_nodes", "nodes", "devices", "ecus", "gateways", "assets"}:
        record.setdefault("hardware", name)
    elif normalized_collection in {"functions", "services", "runnables"}:
        record.setdefault("function", name)
    elif normalized_collection in {"interfaces", "ports", "channels", "connectors", "networks", "buses"}:
        record.setdefault("interface", name)
        record.setdefault("interface_type", record.get("protocol", "") or record.get("technology", "") or name)
    elif normalized_collection in {"messages", "frames", "pdus", "telegrams", "packets"}:
        record.setdefault("message", name)
    elif normalized_collection in {"signals", "data_elements", "variables"}:
        record.setdefault("signal", name)
    return record


def _records_from_structured_data(data: Any) -> tuple[list[dict[str, str]], list[str]]:
    records: list[dict[str, str]] = []

    def visit(value: Any, collection: str = "") -> None:
        if isinstance(value, dict):
            if collection:
                records.append(_record_from_collection_item(collection, value))
            else:
                scalar_fields = _flatten_mapping(value)
                object_aliases = (
                    alias
                    for field, aliases in FIELD_ALIASES.items()
                    if field != "domain"
                    for alias in aliases
                )
                if any(key in scalar_fields for key in object_aliases):
                    records.append(scalar_fields)
            for key, nested in value.items():
                if isinstance(nested, list):
                    for item in nested:
                        visit(item, str(key))
        elif isinstance(value, list):
            for item in value:
                visit(item, collection)

    visit(data)
    defaults: dict[str, str] = {}
    for field in ("hardware", "function", "interface", "interface_type", "message"):
        defaults[field] = next((record[field] for record in records if record.get(field)), "")
    for record in records:
        if record.get("hardware") or record.get("interface") or record.get("message") or record.get("signal"):
            for field in ("hardware", "function", "interface", "interface_type"):
                if defaults.get(field):
                    record.setdefault(field, defaults[field])
        if record.get("signal") and defaults.get("message"):
            record.setdefault("message", defaults["message"])
    headers = sorted({key for record in records for key in record})
    return records, headers


def _json_records(content: bytes) -> tuple[list[dict[str, str]], list[str]]:
    try:
        data = json.loads(_decode_text(content))
    except json.JSONDecodeError as error:
        raise EngineeringValidationError("Die JSON-Datei ist beschädigt oder ungültig.") from error
    return _records_from_structured_data(data)


def _jsonl_records(content: bytes) -> tuple[list[dict[str, str]], list[str]]:
    records: list[dict[str, str]] = []
    for line_number, line in enumerate(_decode_text(content).splitlines(), start=1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as error:
            raise EngineeringValidationError(f"JSONL-Zeile {line_number} ist ungültig.") from error
        line_records, _headers = _records_from_structured_data(data)
        records.extend(line_records)
    headers = sorted({key for record in records for key in record})
    return records, headers


def _yaml_records(content: bytes) -> tuple[list[dict[str, str]], list[str]]:
    try:
        data = yaml.safe_load(_decode_text(content))
    except yaml.YAMLError as error:
        raise EngineeringValidationError("Die YAML-Datei ist beschädigt oder ungültig.") from error
    return _records_from_structured_data(data)


def _text_trace_records(content: bytes) -> tuple[list[dict[str, str]], list[str]]:
    records: list[dict[str, str]] = []
    explicit_id = re.compile(r"\b(?:CAN[_ -]?ID|FRAME[_ -]?ID|ID)\s*[:=]\s*(0x[0-9a-fA-F]+|[0-9a-fA-F]{3,8})\b")
    vector_like = re.compile(r"\b(0x[0-9a-fA-F]+|[0-9a-fA-F]{3,8})x?\s+(?:Rx|Tx|d|D)\b")
    dlc_pattern = re.compile(r"\b(?:DLC|LEN|LENGTH)\s*[:=]?\s*(\d{1,2})\b", re.IGNORECASE)
    for index, line in enumerate(_decode_text(content).splitlines(), start=1):
        match = explicit_id.search(line) or vector_like.search(line)
        if not match:
            continue
        frame_id = match.group(1)
        dlc = dlc_pattern.search(line)
        records.append(
            {
                "hardware": "Imported Trace Source",
                "function": "Trace Kommunikation",
                "interface": "Trace Interface",
                "interface_type": "CAN",
                "message": f"TraceFrame_{frame_id.removeprefix('0x').upper()}",
                "message_id_hex": frame_id if frame_id.lower().startswith("0x") else f"0x{frame_id}",
                "direction": "tx",
                "dlc": dlc.group(1) if dlc else "",
                "domain": "generic",
                "source_line": str(index),
            }
        )
    if not records:
        raise EngineeringValidationError("Die Trace-Datei enthält keine erkennbaren CAN-/Bus-Frames.")
    return records, ["hardware", "function", "interface", "interface_type", "message", "message_id_hex", "direction", "dlc"]


def _value(row: dict[str, str], field: str) -> str:
    return next((row.get(alias, "") for alias in FIELD_ALIASES[field] if row.get(alias)), "")


def _device_type(value: str) -> str:
    aliases = {
        "ecu": "ECU",
        "gateway": "Gateway",
        "sensor": "SensorController",
        "actuator": "ActuatorController",
        "aktor": "ActuatorController",
    }
    if value in DEVICE_TYPES:
        return value
    return aliases.get(value.lower(), "GenericDevice")


def _interface_type(value: str) -> str:
    aliases = {
        "can": "CAN",
        "can_fd": "CAN_FD",
        "can fd": "CAN_FD",
        "ethernet": "Ethernet",
        "automotive_ethernet": "Ethernet",
        "flexray": "FlexRay",
        "lin": "LIN",
    }
    if value in INTERFACE_TYPES:
        return value
    return aliases.get(value.lower(), "Other")


def _dbc_device_type(name: str) -> str:
    return "Gateway" if "gateway" in name.lower() else "ECU"


def _direction(value: str) -> str | None:
    normalized = value.strip().lower()
    return normalized if normalized in {"tx", "rx", "bidirectional"} else None


def _byte_order(value: str) -> str | None:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"little_endian", "little", "intel", "1"}:
        return "little_endian"
    if normalized in {"big_endian", "big", "motorola", "0"}:
        return "big_endian"
    return None


def _tabular_plan(records: list[dict[str, str]], headers: list[str]) -> dict[str, Any]:
    hardware: dict[str, dict[str, Any]] = {}
    functions: dict[str, dict[str, Any]] = {}
    interfaces: dict[str, dict[str, Any]] = {}
    messages: dict[str, dict[str, Any]] = {}
    signals: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for index, row in enumerate(records, start=2):
        domain = _value(row, "domain") or "generic"
        hardware_name = _value(row, "hardware") or "Imported Hardware"
        function_name = _value(row, "function") or f"{hardware_name} Kommunikation"
        interface_name = _value(row, "interface") or f"{hardware_name} Interface"
        message_name = _value(row, "message")
        signal_name = _value(row, "signal")
        if not message_name and not signal_name and not any(row.values()):
            continue
        if signal_name and not message_name:
            message_name = "Imported Message"
            warnings.append(f"Zeile {index}: Signal wurde der Standardnachricht zugeordnet.")
        hardware_key = f"hardware:{_slug(hardware_name)}"
        function_key = f"{hardware_key}/function:{_slug(function_name)}"
        interface_key = f"{function_key}/interface:{_slug(interface_name)}"
        hardware.setdefault(hardware_key, {"key": hardware_key, "name": hardware_name, "domain": domain, "device_type": _device_type(_value(row, "device_type"))})
        functions.setdefault(function_key, {"key": function_key, "name": function_name, "domain": domain, "hardware_key": hardware_key})
        interfaces.setdefault(interface_key, {"key": interface_key, "name": interface_name, "domain": domain, "function_key": function_key, "interface_type": _interface_type(_value(row, "interface_type"))})
        if message_name:
            message_key = f"{interface_key}/message:{_slug(message_name)}"
            messages.setdefault(message_key, {"key": message_key, "name": message_name, "domain": domain, "interface_key": interface_key, "message_id_hex": _value(row, "message_id_hex") or None, "direction": _direction(_value(row, "direction")), "cycle_ms": _number(_value(row, "cycle_ms")), "dlc": _number(_value(row, "dlc"), integer=True)})
            if signal_name:
                signal_key = f"{message_key}/signal:{_slug(signal_name)}"
                signals.setdefault(signal_key, {"key": signal_key, "name": signal_name, "domain": domain, "message_key": message_key, "display_name": signal_name, "start_bit": _number(_value(row, "start_bit"), integer=True), "length_bits": _number(_value(row, "length_bits"), integer=True), "byte_order": _byte_order(_value(row, "byte_order")), "data_type": _value(row, "data_type") or None, "factor": _number(_value(row, "factor")), "offset_value": _number(_value(row, "offset_value")), "unit": _value(row, "unit") or None, "min_value": _number(_value(row, "min_value")), "max_value": _number(_value(row, "max_value"))})
    normalized_headers = {_normalized_header(header): header for header in headers}
    mapping = {
        field: normalized_headers[alias]
        for field, aliases in FIELD_ALIASES.items()
        for alias in aliases
        if alias in normalized_headers
    }
    return {"hardware_nodes": list(hardware.values()), "functions": list(functions.values()), "interfaces": list(interfaces.values()), "messages": list(messages.values()), "signals": list(signals.values()), "mapping": mapping, "warnings": warnings}


def _dbc_plan(content: bytes) -> dict[str, Any]:
    text = _decode_text(content)
    nodes = set(re.findall(r"^BU_:\s*(.*)$", text, flags=re.MULTILINE)[0].split()) if re.search(r"^BU_:", text, flags=re.MULTILINE) else set()
    message_pattern = re.compile(r"^BO_\s+(\d+)\s+([^:]+):\s+(\d+)\s+(\S+)", re.MULTILINE)
    signal_pattern = re.compile(r"^\s*SG_\s+(\w+)(?:\s+\w+)?\s*:\s*(\d+)\|(\d+)@(\d)([+-])\s+\(([-+\d.eE]+),([-+\d.eE]+)\)\s+\[([-+\d.eE]+)\|([-+\d.eE]+)\]\s+\"([^\"]*)\"\s*(.*)$", re.MULTILINE)
    messages_raw = list(message_pattern.finditer(text))
    if not messages_raw:
        raise EngineeringValidationError("Die DBC-Datei enthält keine BO_-Nachrichten.")
    plan = {"hardware_nodes": [], "functions": [], "interfaces": [], "messages": [], "signals": [], "mapping": {"message": "BO_", "signal": "SG_"}, "warnings": []}
    for index, match in enumerate(messages_raw):
        sender = match.group(4)
        if sender != "Vector__XXX":
            nodes.add(sender)
        block_end = messages_raw[index + 1].start() if index + 1 < len(messages_raw) else len(text)
        for signal in signal_pattern.finditer(text[match.end():block_end]):
            nodes.update(item.strip() for item in signal.group(11).split(",") if item.strip() and item.strip() != "Vector__XXX")
    if not nodes:
        nodes.add("Imported CAN Network")
    node_keys: dict[str, tuple[str, str, str]] = {}
    for name in sorted(nodes):
        hardware_key = f"hardware:{_slug(name)}"
        function_key = f"{hardware_key}/function:communication"
        interface_key = f"{function_key}/interface:can"
        node_keys[name] = (hardware_key, function_key, interface_key)
        plan["hardware_nodes"].append(
            {"key": hardware_key, "name": name, "domain": "generic", "device_type": _dbc_device_type(name)}
        )
        plan["functions"].append({"key": function_key, "name": f"{name} Kommunikation", "domain": "generic", "hardware_key": hardware_key})
        plan["interfaces"].append({"key": interface_key, "name": f"{name} CAN", "domain": "generic", "function_key": function_key, "interface_type": "CAN"})
    fallback = next(iter(node_keys.values()))
    for index, match in enumerate(messages_raw):
        frame_id, name, dlc, sender = match.groups()
        interface_key = node_keys.get(sender, fallback)[2]
        message_key = f"{interface_key}/message:{frame_id}"
        plan["messages"].append({"key": message_key, "name": name.strip(), "domain": "generic", "interface_key": interface_key, "message_id_hex": hex(int(frame_id)), "direction": "tx", "dlc": int(dlc), "cycle_ms": None})
        block_end = messages_raw[index + 1].start() if index + 1 < len(messages_raw) else len(text)
        for signal in signal_pattern.finditer(text[match.end():block_end]):
            signal_name, start, length, byte_order, sign, factor, offset, minimum, maximum, unit, _receivers = signal.groups()
            plan["signals"].append({"key": f"{message_key}/signal:{_slug(signal_name)}", "name": signal_name, "domain": "generic", "message_key": message_key, "display_name": signal_name, "start_bit": int(start), "length_bits": int(length), "byte_order": "little_endian" if byte_order == "1" else "big_endian", "data_type": "signed" if sign == "-" else "unsigned", "factor": float(factor), "offset_value": float(offset), "unit": unit or None, "min_value": float(minimum), "max_value": float(maximum)})
    return plan


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].upper()


def _xml_name(element: ElementTree.Element) -> str:
    for key in ("SHORT-NAME", "NAME", "Name", "name", "ID", "id"):
        value = element.attrib.get(key)
        if value:
            return str(value).strip()
    direct = next((child for child in element if _xml_local_name(child.tag) in {"SHORT-NAME", "NAME"}), None)
    if direct is not None and direct.text:
        return direct.text.strip()
    nested = next((child for child in element.iter() if child is not element and _xml_local_name(child.tag) in {"SHORT-NAME", "NAME"} and child.text), None)
    return nested.text.strip() if nested is not None and nested.text else ""


def _xml_interface_type(value: str) -> str:
    normalized = value.upper().replace("_", "-")
    if "CAN-FD" in normalized or "CANFD" in normalized:
        return "CAN_FD"
    if "CAN" in normalized:
        return "CAN"
    if "LIN" in normalized:
        return "LIN"
    if "ETHERNET" in normalized or "SOMEIP" in normalized or "DOIP" in normalized:
        return "Ethernet"
    if "FLEXRAY" in normalized:
        return "FlexRay"
    return "Other"


def _xml_device_type(name: str) -> str:
    lowered = name.lower()
    if any(token in lowered for token in ("gateway", "bcm", "zentr", "central")):
        return "Gateway"
    if "sensor" in lowered:
        return "SensorController"
    if "actuator" in lowered or "aktor" in lowered or "stellglied" in lowered:
        return "ActuatorController"
    return "ECU"


def _xml_plan(content: bytes) -> dict[str, Any]:
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as error:
        raise EngineeringValidationError("Die XML/AXML/ARXML-Datei ist beschädigt oder ungültig.") from error

    hardware_names: list[str] = []
    interface_types: list[str] = []
    message_names: list[str] = []
    signal_names: list[str] = []
    for element in root.iter():
        local = _xml_local_name(element.tag)
        name = _xml_name(element)
        if not name:
            continue
        if local in {"ECU", "ECU-INSTANCE", "ECU-INSTANCE-REF", "NODE"} or local.endswith("-ECU-INSTANCE"):
            hardware_names.append(name)
        elif any(token in local for token in ("CLUSTER", "CHANNEL", "CONNECTOR", "CONTROLLER")):
            interface_type = _xml_interface_type(f"{local} {name}")
            if interface_type != "Other":
                interface_types.append(interface_type)
        elif "FRAME" in local or local.endswith("PDU") or "MESSAGE" in local:
            message_names.append(name)
        elif "SIGNAL" in local:
            signal_names.append(name)

    if not hardware_names and (message_names or signal_names or interface_types):
        hardware_names.append("Imported Gateway")
    if not interface_types:
        interface_types.append("CAN")

    plan = {
        "hardware_nodes": [],
        "functions": [],
        "interfaces": [],
        "messages": [],
        "signals": [],
        "mapping": {"hardware": "ECU/NODE", "interface_type": "CLUSTER/CHANNEL", "message": "FRAME/PDU", "signal": "SIGNAL"},
        "warnings": ["XML/AXML/ARXML/FIBEX wurde heuristisch gelesen. Prüfe erkannte Zuordnung vor dem Import."],
    }
    unique_hardware = list(dict.fromkeys(hardware_names))
    unique_interfaces = list(dict.fromkeys(interface_types))
    for name in unique_hardware:
        hardware_key = f"hardware:{_slug(name)}"
        function_key = f"{hardware_key}/function:communication"
        interface_type = unique_interfaces[0]
        interface_key = f"{function_key}/interface:{_slug(interface_type)}"
        plan["hardware_nodes"].append({"key": hardware_key, "name": name, "domain": "automotive", "device_type": _xml_device_type(name)})
        plan["functions"].append({"key": function_key, "name": f"{name} Kommunikation", "domain": "automotive", "hardware_key": hardware_key})
        plan["interfaces"].append({"key": interface_key, "name": f"{name} {interface_type}", "domain": "automotive", "function_key": function_key, "interface_type": interface_type})

    fallback_interface_key = plan["interfaces"][0]["key"]
    unique_messages = list(dict.fromkeys(message_names))
    if signal_names and not unique_messages:
        unique_messages.append("Imported Message")
    for index, name in enumerate(unique_messages, start=1):
        message_key = f"{fallback_interface_key}/message:{_slug(name)}"
        plan["messages"].append({"key": message_key, "name": name, "domain": "automotive", "interface_key": fallback_interface_key, "message_id_hex": hex(index), "direction": "tx", "cycle_ms": None, "dlc": None})

    fallback_message_key = plan["messages"][0]["key"] if plan["messages"] else ""
    for name in dict.fromkeys(signal_names):
        signal_key = f"{fallback_message_key}/signal:{_slug(name)}"
        plan["signals"].append({"key": signal_key, "name": name, "domain": "automotive", "message_key": fallback_message_key, "display_name": name, "start_bit": None, "length_bits": None, "byte_order": None, "data_type": None, "factor": None, "offset_value": None, "unit": None, "min_value": None, "max_value": None})
    return plan


def preview_import(filename: str, content: bytes) -> dict[str, Any]:
    if not content:
        raise EngineeringValidationError("Die Importdatei ist leer.")
    safe_name = PurePath(filename or "import").name
    extension = PurePath(safe_name).suffix.lower()
    if extension == ".dbc":
        plan = _dbc_plan(content)
    elif extension == ".csv":
        plan = _tabular_plan(*_csv_records(content))
    elif extension == ".xlsx":
        try:
            plan = _tabular_plan(*_xlsx_records(content))
        except EngineeringValidationError:
            raise
        except (ElementTree.ParseError, KeyError, IndexError, ValueError) as error:
            raise EngineeringValidationError(
                "Die XLSX-Datei ist beschädigt oder verwendet ein nicht unterstütztes Layout."
            ) from error
    elif extension in {".axml", ".arxml", ".fibex", ".xml"}:
        plan = _xml_plan(content)
    elif extension == ".json":
        plan = _tabular_plan(*_json_records(content))
    elif extension == ".jsonl":
        plan = _tabular_plan(*_jsonl_records(content))
    elif extension in {".yaml", ".yml"}:
        plan = _tabular_plan(*_yaml_records(content))
    elif extension in {".asc", ".trc", ".log", ".txt"}:
        plan = _tabular_plan(*_text_trace_records(content))
    else:
        raise EngineeringValidationError(
            "Unterstützt werden .dbc, .csv, .xlsx, .json, .jsonl, .yaml, .yml, .axml, .arxml, .fibex, .xml, .asc, .trc, .log und .txt."
        )
    plan.update({"import_id": hashlib.sha256(content).hexdigest(), "file_name": safe_name, "format": extension.removeprefix(".")})
    if not plan["hardware_nodes"]:
        raise EngineeringValidationError("Es konnten keine Engineering-Objekte erkannt werden.")
    plan["counts"] = {key: len(plan[key]) for key in ("hardware_nodes", "functions", "interfaces", "messages", "signals")}
    return plan


def _existing(object_type: str, import_id: str, import_key: str) -> dict[str, Any] | None:
    table = ENTITY_SPECS[object_type].table
    with get_connection() as connection:
        return connection.execute(
            f"SELECT * FROM {table} WHERE provenance ->> 'origin' = %s AND provenance ->> 'import_id' = %s AND provenance ->> 'import_key' = %s",
            (IMPORT_ORIGIN, import_id, import_key),
        ).fetchone()


def commit_import(plan: dict[str, Any]) -> dict[str, Any]:
    import_id = str(plan.get("import_id") or "")
    if not re.fullmatch(r"[a-f0-9]{64}", import_id):
        raise EngineeringValidationError("Ungültige Import-ID.")
    with _lock(import_id):
        ids: dict[str, str] = {}
        created = 0
        reused = 0
        provenance_base = {"origin": IMPORT_ORIGIN, "import_id": import_id, "file_name": str(plan.get("file_name") or "import")}

        def persist(object_type: str, item: dict[str, Any], payload: dict[str, Any]) -> str:
            nonlocal created, reused
            import_key = str(item.get("key") or "")
            if not import_key:
                raise EngineeringValidationError("Ein Importobjekt besitzt keinen Schlüssel.")
            existing = _existing(object_type, import_id, import_key)
            if existing:
                reused += 1
                return str(existing["id"])
            result = create_object(object_type, {**payload, "source": "import", "provenance": {**provenance_base, "import_key": import_key}})
            created += 1
            return str(result["id"])

        for item in plan.get("hardware_nodes", []):
            ids[item["key"]] = persist("HardwareNode", item, {"name": item["name"], "domain": item.get("domain") or "generic", "device_type": item.get("device_type") or "GenericDevice"})
        for item in plan.get("functions", []):
            ids[item["key"]] = persist("Function", item, {"name": item["name"], "domain": item.get("domain") or "generic", "hardware_node_id": ids[item["hardware_key"]]})
        for item in plan.get("interfaces", []):
            function_id = ids[item["function_key"]]
            with get_connection() as connection:
                function = get_object("Function", function_id)
            ids[item["key"]] = persist("Interface", item, {"name": item["name"], "domain": item.get("domain") or "generic", "function_id": function_id, "hardware_node_id": str(function["hardware_node_id"]), "interface_type": item.get("interface_type") or "Other"})
        for item in plan.get("messages", []):
            ids[item["key"]] = persist("Message", item, {"name": item["name"], "domain": item.get("domain") or "generic", "interface_id": ids[item["interface_key"]], "message_id_hex": item.get("message_id_hex"), "direction": item.get("direction"), "cycle_ms": item.get("cycle_ms"), "dlc": item.get("dlc")})
        for item in plan.get("signals", []):
            ids[item["key"]] = persist("Signal", item, {"name": item["name"], "domain": item.get("domain") or "generic", "message_id": ids[item["message_key"]], **{key: item.get(key) for key in ("display_name", "start_bit", "length_bits", "byte_order", "data_type", "factor", "offset_value", "unit", "min_value", "max_value")}})
        return {"import_id": import_id, "created": created, "reused": reused, "counts": plan.get("counts", {})}
