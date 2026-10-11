#!/usr/bin/env python3
"""Writers for CAN oriented exchange and trace formats."""

from __future__ import annotations

import csv
import json
import hashlib
import math
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from backend.nis.communication.technologies.can.formats.trace_model import CanFrame, MessageDef, ROUTE_INFO_LENGTH, ROUTE_INFO_START_BYTE
from backend.nis.traces.trace_support import iso_utc, route_label, write_text


def write_project_can_artifacts(out_dir: Path, config: dict, routes: list[dict], events: list[dict], formats: list[str]):
    """Export the frozen canonical model and actual scheduled CAN transmissions.

    One project DBC contains all CAN/CAN-FD definitions in the frozen run scope;
    the BLF channel map retains physical network identity and original wire IDs.
    This adapter never invokes the standalone example traffic generator.
    """
    selected = set(formats) & {"blf", "dbc"}
    if not selected:
        return [], {}
    import can
    import cantools
    from cantools.database.can import Database, Message, Signal, Node
    from cantools.database.conversion import BaseConversion
    from cantools.database.can.formats.dbc.dbc_specifics import DbcSpecifics
    from cantools.database.can.formats.dbc.dbc_attribute import DbcAttribute
    from cantools.database.can.formats.dbc.dbc_attribute_definition import DbcAttributeDefinition
    from collections import OrderedDict
    from copy import deepcopy
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    from backend.nis.simulation.model_based_simulation import integer_signal_signed

    model = config.get("engineering_model") or {}
    messages = {str(item["id"]): item for item in model.get("messages") or []}
    signals = {}
    for signal in model.get("signals") or []:
        signals.setdefault(str(signal["message_id"]), []).append(signal)
    can_routes = [route for route in routes
                  if selected.intersection(registry.profile(route["technology"]).get("native_formats") or [])
                  and route["technology"] in {"can", "can_fd"}]
    if not can_routes:
        return [], {"generator": "canonical-can-export-v1", "frames": 0, "networks": []}
    networks = sorted({route["network"] for route in can_routes})
    channels = {network: index for index, network in enumerate(networks)}
    definitions = {network: {} for network in networks}
    bitrate_switch = {route['network']: bool(route.get('network_metadata', {}).get('can_fd_brs', False)) for route in can_routes}
    identifiers = {}
    used_names = {}
    frame_format = DbcAttributeDefinition('VFrameFormat', default_value=0, kind='BO_', type_name='ENUM',
        choices=['StandardCAN', 'ExtendedCAN', 'StandardCAN_FD', 'ExtendedCAN_FD'])

    def name(value, identity, namespace):
        key = (namespace, identity)
        if key not in identifiers:
            candidate = re.sub(r"[^A-Za-z0-9_]", "_", str(value)) or "NIS"
            if candidate[0].isdigit():
                candidate = "NIS_" + candidate
            candidate = candidate[:32]
            used = used_names.setdefault(namespace, set())
            if candidate in used:
                candidate = candidate[:23] + "_" + hashlib.sha256(identity.encode()).hexdigest()[:8]
            used.add(candidate)
            identifiers[key] = candidate
        return identifiers[key]

    def number(raw, field):
        if raw.get(field) is None or isinstance(raw[field], bool) or not math.isfinite(float(raw[field])):
            raise ValueError(f"CAN_EXPORT_ENCODING_MISSING: {raw.get('name')} / {field}")
        return float(raw[field])

    def integer(raw, field):
        value = number(raw, field)
        if not value.is_integer():
            raise ValueError(f"CAN_EXPORT_ENCODING_INVALID: {raw.get('name')} / {field} must be an integer")
        return int(value)

    for route in can_routes:
        refs = route["metadata"].get("message_ids") or []
        if len(refs) != 1 or str(refs[0]) not in messages:
            raise ValueError(f"CAN_EXPORT_MESSAGE_BINDING: {route['id']} requires one canonical message")
        identity = str(refs[0])
        raw = messages[identity]
        network = route["network"]
        source = name(route["sender"]["hardware_name"], route["sender"]["hardware_id"], "nodes")
        receivers = [name(item["hardware_name"], item["hardware_id"], "nodes") for item in route["receivers"]]
        if identity in definitions[network]:
            definition = definitions[network][identity]
            if definition.senders != [source]:
                raise ValueError(f"CAN_EXPORT_SENDER_CONFLICT: {identity} on {network}")
            for signal in definition.signals:
                signal.receivers = sorted(set(signal.receivers + receivers))
            continue
        raw_id = raw.get("message_id_hex")
        if raw_id is None:
            raise ValueError(f"CAN_EXPORT_ID_MISSING: {identity}")
        frame_id = int(str(raw_id), 16 if str(raw_id).lower().startswith("0x") else 10)
        extended = (raw.get("configuration") or {}).get("is_extended_frame", frame_id > 0x7ff)
        if not isinstance(extended, bool) or not 0 <= frame_id <= (0x1fffffff if extended else 0x7ff):
            raise ValueError(f"CAN_EXPORT_ID_INVALID: {identity}")
        if any(item.frame_id == frame_id and item.is_extended_frame == extended for item in definitions[network].values()):
            raise ValueError(f"CAN_EXPORT_ID_COLLISION: {frame_id} on {network}")
        length = integer(raw, "dlc")
        is_fd = route["technology"] == "can_fd"
        if length < 0 or length > (64 if is_fd else 8):
            raise ValueError(f"CAN_EXPORT_DLC_INVALID: {identity}")
        encoded = []
        for signal in signals.get(identity, []):
            start = integer(signal, "start_bit")
            bits = integer(signal, "length_bits")
            order = signal.get("byte_order")
            if order not in {"little_endian", "big_endian"}:
                raise ValueError(f"CAN_EXPORT_BYTE_ORDER_INVALID: {signal['id']}")
            # The existing model's aligned big-endian start denotes the first
            # byte's bit 0. DBC Motorola denotes that byte's most significant bit.
            if order == "big_endian":
                if start % 8 or bits % 8:
                    raise ValueError(f"CAN_EXPORT_ENCODING_UNSUPPORTED: {signal['id']} requires aligned big-endian encoding")
                start += 7
            kind = str(signal.get("data_type") or "").lower()
            if not (kind in {"signed", "unsigned", "bool", "boolean", "enum"} or re.fullmatch(r"(?:u?int|sint)\d*", kind)):
                raise ValueError(f"CAN_EXPORT_DATA_TYPE_UNSUPPORTED: {signal['id']}")
            factor = number(signal, "factor")
            if factor <= 0 or bits < 1 or bits > 64 or start < 0:
                raise ValueError(f"CAN_EXPORT_ENCODING_INVALID: {signal['id']}")
            choices = (signal.get("data") or {}).get("enum") or (signal.get("configuration") or {}).get("enum")
            encoded.append(Signal(name(signal['name'], str(signal['id']), identity), start, bits,
                byte_order=order, is_signed=integer_signal_signed(kind),
                conversion=BaseConversion.factory(scale=factor, offset=number(signal, "offset_value"),
                    choices={int(value): label for label, value in choices.items()} if choices else None),
                minimum=signal.get("min_value"), maximum=signal.get("max_value"), unit=signal.get("unit"),
                receivers=receivers, comment=f"CanonicalSignal={signal['id']}"))
        definition = Message(frame_id, name(raw['name'], identity, "messages"), length, encoded,
            is_extended_frame=extended, is_fd=is_fd, senders=[source], strict=True,
            dbc_specifics=DbcSpecifics(attributes=OrderedDict([
                ('VFrameFormat', DbcAttribute((2 if is_fd else 0) + int(extended), frame_format))])),
            comment=f"CanonicalMessage={identity}; Network={network}; Technology={route['technology']}")
        definitions[network][identity] = definition

    # Validate every database before creating any artifact. No invalid layouts,
    # duplicate IDs or truncated encodings can masquerade as an export success.
    project_definitions = {}
    definition_networks = {}
    for network, items in definitions.items():
        nodes = sorted({node for item in items.values() for node in item.senders}
                       | {node for item in items.values() for signal in item.signals for node in signal.receivers})
        database = Database(messages=list(items.values()), nodes=[Node(node) for node in nodes], strict=True,
            dbc_specifics=DbcSpecifics(attribute_definitions=OrderedDict([('VFrameFormat', frame_format)])))
        text = database.as_dbc_string()
        cantools.database.load_string(text, database_format="dbc", strict=True)
        if 'dbc' not in selected:
            continue
        for identity, definition in items.items():
            wire_key = (definition.frame_id, definition.is_extended_frame)
            if wire_key in project_definitions:
                previous_identity, previous = project_definitions[wire_key]
                if (previous_identity != identity or previous.is_fd != definition.is_fd
                        or previous.senders != definition.senders):
                    raise ValueError(
                        f"CAN_EXPORT_PROJECT_ID_COLLISION: {definition.frame_id:#x} identifies different "
                        f"definitions on {', '.join(definition_networks[wire_key])} and {network}. "
                        "A single unambiguous DBC requires unique canonical CAN identifiers; "
                        "wire identifiers are never renumbered by export.")
                for previous_signal, signal in zip(previous.signals, definition.signals):
                    previous_signal.receivers = sorted(set(previous_signal.receivers + signal.receivers))
                definition_networks[wire_key].append(network)
            else:
                project_definitions[wire_key] = (identity, deepcopy(definition))
                definition_networks[wire_key] = [network]
    project_messages = []
    for wire_key, (identity, definition) in project_definitions.items():
        definition.comment = (f"CanonicalMessage={identity}; Networks={','.join(definition_networks[wire_key])}; "
                              f"Technology={'can_fd' if definition.is_fd else 'can'}")
        project_messages.append(definition)
    project_dbc = None
    if 'dbc' in selected:
        nodes = sorted({node for item in project_messages for node in item.senders}
                       | {node for item in project_messages for signal in item.signals for node in signal.receivers})
        project_database = Database(messages=project_messages, nodes=[Node(node) for node in nodes], strict=True,
            dbc_specifics=DbcSpecifics(attribute_definitions=OrderedDict([('VFrameFormat', frame_format)])))
        project_dbc = project_database.as_dbc_string()
        cantools.database.load_string(project_dbc, database_format="dbc", strict=True)
    frames = []
    mapping = []
    for event in events:
        if event.get("network") not in channels or event.get("technology") not in {"can", "can_fd"}:
            continue
        refs = event.get("message_ids") or []
        if len(refs) != 1 or str(refs[0]) not in definitions[event['network']]:
            raise ValueError(f"CAN_EXPORT_EVENT_BINDING: {event.get('event_id')}")
        definition = definitions[event['network']][str(refs[0])]
        payload = bytes.fromhex(event['payload_hex'])
        if len(payload) != definition.length or event.get('arbitration_id') != definition.frame_id:
            raise ValueError(f"CAN_EXPORT_EVENT_ENCODING_MISMATCH: {event.get('event_id')}")
        captured = event.get('status') != 'dropped' and not event.get('shared_transmission_observation')
        tx = float(event['timestamp_unix']) - float(event['time_s']) + float(event.get('tx_start_s', event['time_s']))
        if captured:
            frames.append(can.Message(timestamp=tx, arbitration_id=definition.frame_id, is_extended_id=definition.is_extended_frame,
                is_fd=definition.is_fd, bitrate_switch=definition.is_fd and bitrate_switch[event['network']],
                data=payload, channel=channels[event['network']], is_rx=False, check=True))
        mapping.append({'event_id':event.get('event_id'), 'physical_transmission_id':event.get('physical_transmission_id'),
            'route_id':event['route_id'], 'message_id':str(refs[0]), 'network_id':event['network'],
            'channel':channels[event['network']], 'status':event['status'], 'captured':captured, 'tx_timestamp':tx})
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    if 'dbc' in selected:
        path = out_dir / 'can_network.dbc'
        path.write_text(project_dbc, encoding='utf-8', newline='')
        paths.append(path)
    if 'blf' in selected:
        path = out_dir / 'can_trace.blf'
        with can.BLFWriter(str(path)) as writer:
            for frame in sorted(frames, key=lambda item: item.timestamp):
                writer.on_message_received(frame)
        paths.append(path)
    sidecar = out_dir / 'can_export_map.json'
    sidecar.write_text(json.dumps({'channels':channels, 'events':mapping}, ensure_ascii=False), encoding='utf-8')
    paths.append(sidecar)
    return paths, {'generator':'canonical-can-export-v1', 'frames':len(frames), 'networks':networks,
        'messages':len(project_messages) if 'dbc' in selected else sum(len(items) for items in definitions.values()),
        'signals':sum(len(item.signals) for item in project_messages) if 'dbc' in selected else
                  sum(len(item.signals) for items in definitions.values() for item in items.values()),
        'database':'can_network.dbc' if 'dbc' in selected else None,
        'database_layout':'project-single-dbc-v1' if 'dbc' in selected else None, 'map':str(sidecar)}


def hex_payload(data: bytes, sep: str = " ") -> str:
    return sep.join(f"{byte:02X}" for byte in data)


def write_dbc(path: Path, messages: list[MessageDef], nominal_bitrate: int = 500_000, data_bitrate: int | None = None) -> None:
    nodes = sorted({msg.sender for msg in messages} | {msg.receiver for msg in messages})
    lines = [
        'VERSION "Generated realistic CAN database"',
        "",
        "NS_ :",
        "\tNS_DESC_",
        "\tCM_",
        "\tBA_DEF_",
        "\tBA_",
        "\tVAL_",
        "",
        "BS_:",
        "",
        "BU_: " + " ".join(nodes),
        "",
    ]
    for msg in messages:
        lines.append(f"BO_ {msg.frame_id} {msg.name}: {msg.dlc} {msg.sender}")
        for sig in msg.signals:
            lines.append(
                f' SG_ {sig.name} : {sig.start_bit}|{sig.length}@1+ '
                f'({sig.factor},{sig.offset}) [{sig.minimum}|{sig.maximum}] "{sig.unit}" {msg.receiver}'
            )
        bus_label = {"classic": "Classic-CAN", "fd": "CAN-FD", "xl": "CAN-XL"}[msg.bus_type]
        data_info = f"; DataBitrate={data_bitrate // 1000}kbit/s" if msg.bus_type in {"fd", "xl"} and data_bitrate else ""
        xl_info = "; NativeCanXl=false; StoredAs=CAN-FD-compatible-BLF" if msg.bus_type == "xl" else ""
        gateway = f"; Gateway to CAN{msg.gateway_to_channel}" if msg.gateway_to_channel is not None else ""
        if msg.kind == "response":
            relation = f"ResponseFor=0x{msg.response_for:X}; ACK/NACK with CRC, DLC and counter check"
        elif any(sig.kind == "route_info" for sig in msg.signals):
            relation = (
                f"PayloadRouteInfo='{route_label(msg.sender, msg.receiver)}' "
                f"in bytes {ROUTE_INFO_START_BYTE}-{ROUTE_INFO_START_BYTE + ROUTE_INFO_LENGTH - 1}"
            )
        elif msg.bus_type in {"fd", "xl"}:
            relation = "ExternalSignalLayout=preserved; PayloadRouteInfo not injected"
        else:
            relation = f"PayloadRouteInfo='{route_label(msg.sender, msg.receiver)}' only in DBC comment"
        lines.append(
            f'CM_ BO_ {msg.frame_id} "Cycle={msg.cycle_ms}ms; Channel=CAN{msg.channel}; '
            f"{bus_label}; NominalBitrate={nominal_bitrate // 1000}kbit/s{data_info}{xl_info}; {relation}{gateway}\";"
        )
        lines.append("")
    write_text(path, "\n".join(lines))


def write_asc(path: Path, frames: list[CanFrame], trace_start_utc: float | None = None) -> None:
    first = trace_start_utc if trace_start_utc is not None else frames[0].timestamp if frames else 0.0
    lines = [
        f"date {iso_utc(first)}",
        "base hex timestamps absolute",
        "internal events logged",
        "// Generated Vector ASC-style trace",
        "Begin Triggerblock",
    ]
    for frame in frames:
        rel = frame.timestamp - first
        channel = frame.channel + 1
        data = hex_payload(frame.data)
        if frame.is_fd:
            lines.append(
                f"{rel:12.6f} CANFD   {channel} {frame.direction:<2} "
                f"{frame.arbitration_id:X} 1 0 {frame.dlc} {frame.dlc} {data} // {frame.name}"
            )
        else:
            lines.append(
                f"{rel:12.6f} {channel}  {frame.arbitration_id:X}x {frame.direction:<2} d {frame.dlc} {data} // {frame.name}"
            )
    lines.append("End TriggerBlock")
    write_text(path, "\n".join(lines))


def write_trc(path: Path, frames: list[CanFrame], trace_start_utc: float | None = None) -> None:
    first = trace_start_utc if trace_start_utc is not None else frames[0].timestamp if frames else 0.0
    lines = [
        ";$FILEVERSION=2.1",
        f";$STARTTIME={first:.6f}",
        ";$COLUMNS=N,O,T,B,I,d,R,L,D",
        ";",
    ]
    for index, frame in enumerate(frames, start=1):
        rel_ms = (frame.timestamp - first) * 1000.0
        msg_type = "FD" if frame.is_fd else "DT"
        lines.append(
            f"{index:7d}) {rel_ms:12.3f} {msg_type:>2} {frame.channel + 1:2d} "
            f"{frame.arbitration_id:08X} {frame.direction:>2} {frame.dlc:2d} {hex_payload(frame.data)}"
        )
    write_text(path, "\n".join(lines))


def write_csv_trace(path: Path, frames: list[CanFrame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp_utc", "relative_s", "channel", "direction", "id_hex", "name", "sender", "receiver", "dlc", "bus_type", "message_kind", "data_hex"])
        for frame in frames:
            writer.writerow(
                [
                    iso_utc(frame.timestamp),
                    f"{frame.rel_time:.6f}",
                    f"CAN{frame.channel}",
                    frame.direction,
                    f"0x{frame.arbitration_id:X}",
                    frame.name,
                    frame.sender,
                    frame.receiver,
                    frame.dlc,
                    frame.bus_type,
                    frame.message_kind,
                    frame.data.hex(),
                ]
            )


def write_json_trace(path: Path, frames: list[CanFrame]) -> None:
    payload = {
        "format": "realistic-can-trace",
        "frames": [
            {
                "timestamp_utc": iso_utc(frame.timestamp),
                "timestamp_unix": frame.timestamp,
                "relative_s": frame.rel_time,
                "channel": f"CAN{frame.channel}",
                "direction": frame.direction,
                "id": frame.arbitration_id,
                "id_hex": f"0x{frame.arbitration_id:X}",
                "name": frame.name,
                "sender": frame.sender,
                "receiver": frame.receiver,
                "dlc": frame.dlc,
                "bus_type": frame.bus_type,
                "message_kind": frame.message_kind,
                "data_hex": frame.data.hex(),
            }
            for frame in frames
        ],
    }
    write_text(path, json.dumps(payload, indent=2))


def write_log(path: Path, frames: list[CanFrame]) -> None:
    lines = []
    for frame in frames:
        lines.append(
            f"{iso_utc(frame.timestamp)} {frame.direction:<2} CAN{frame.channel} "
            f"0x{frame.arbitration_id:X} {frame.name} {frame.sender}->{frame.receiver} "
            f"DLC={frame.dlc} DATA={hex_payload(frame.data)}"
        )
    write_text(path, "\n".join(lines))


def write_txt(path: Path, frames: list[CanFrame]) -> None:
    lines = ["Realistic CAN trace", ""]
    for frame in frames:
        lines.append(f"{frame.rel_time:10.6f}s CAN{frame.channel} {frame.direction} {frame.name}")
        lines.append(f"  route: {frame.sender} -> {frame.receiver}")
        lines.append(f"  id: 0x{frame.arbitration_id:X}, dlc: {frame.dlc}, payload: {hex_payload(frame.data)}")
    write_text(path, "\n".join(lines))


def write_xml_trace(path: Path, frames: list[CanFrame]) -> None:
    root = ET.Element("canTrace", generatedUtc=iso_utc(frames[0].timestamp) if frames else "")
    for frame in frames:
        item = ET.SubElement(
            root,
            "frame",
            timestampUtc=iso_utc(frame.timestamp),
            relativeS=f"{frame.rel_time:.6f}",
            channel=f"CAN{frame.channel}",
            direction=frame.direction,
            id=f"0x{frame.arbitration_id:X}",
            name=frame.name,
            busType=frame.bus_type,
        )
        ET.SubElement(item, "sender").text = frame.sender
        ET.SubElement(item, "receiver").text = frame.receiver
        ET.SubElement(item, "payload", dlc=str(frame.dlc), encoding="hex").text = frame.data.hex()
    ET.indent(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def write_yaml_trace(path: Path, frames: list[CanFrame]) -> None:
    lines = ["format: realistic-can-trace", "frames:"]
    for frame in frames:
        lines.extend(
            [
                f"  - timestamp_utc: {iso_utc(frame.timestamp)}",
                f"    relative_s: {frame.rel_time:.6f}",
                f"    channel: CAN{frame.channel}",
                f"    direction: {frame.direction}",
                f"    id_hex: '0x{frame.arbitration_id:X}'",
                f"    name: {frame.name}",
                f"    sender: {frame.sender}",
                f"    receiver: {frame.receiver}",
                f"    dlc: {frame.dlc}",
                f"    bus_type: {frame.bus_type}",
                f"    data_hex: '{frame.data.hex()}'",
            ]
        )
    write_text(path, "\n".join(lines))


def write_arxml(path: Path, messages: list[MessageDef]) -> None:
    root = ET.Element("AUTOSAR", {"xmlns": "http://autosar.org/schema/r4.0"})
    packages = ET.SubElement(root, "AR-PACKAGES")
    package = ET.SubElement(packages, "AR-PACKAGE")
    ET.SubElement(package, "SHORT-NAME").text = "GeneratedCanSystem"
    elements = ET.SubElement(package, "ELEMENTS")
    cluster = ET.SubElement(elements, "CAN-CLUSTER")
    ET.SubElement(cluster, "SHORT-NAME").text = "GeneratedCanCluster"
    frames_el = ET.SubElement(cluster, "CAN-FRAMES")
    for msg in messages:
        frame_el = ET.SubElement(frames_el, "CAN-FRAME")
        ET.SubElement(frame_el, "SHORT-NAME").text = msg.name
        ET.SubElement(frame_el, "IDENTIFIER").text = str(msg.frame_id)
        ET.SubElement(frame_el, "FRAME-LENGTH").text = str(msg.dlc)
        ET.SubElement(frame_el, "CAN-ADDRESSING-MODE").text = "STANDARD"
        pdu = ET.SubElement(frame_el, "PDU")
        ET.SubElement(pdu, "SHORT-NAME").text = f"{msg.name}_PDU"
        ET.SubElement(pdu, "SENDER").text = msg.sender
        ET.SubElement(pdu, "RECEIVER").text = msg.receiver
        signals = ET.SubElement(pdu, "I-SIGNALS")
        for sig in msg.signals:
            sig_el = ET.SubElement(signals, "I-SIGNAL")
            ET.SubElement(sig_el, "SHORT-NAME").text = sig.name
            ET.SubElement(sig_el, "START-POSITION").text = str(sig.start_bit)
            ET.SubElement(sig_el, "LENGTH").text = str(sig.length)
    ET.indent(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def write_fibex(path: Path, messages: list[MessageDef]) -> None:
    root = ET.Element("fx:FIBEX", {"xmlns:fx": "http://www.asam.net/xml/fbx"})
    elements = ET.SubElement(root, "fx:ELEMENTS")
    clusters = ET.SubElement(elements, "fx:CLUSTERS")
    cluster = ET.SubElement(clusters, "fx:CAN-CLUSTER", ID="CAN_CLUSTER_1")
    ET.SubElement(cluster, "fx:SHORT-NAME").text = "GeneratedCanCluster"
    frames_el = ET.SubElement(elements, "fx:FRAMES")
    signals_el = ET.SubElement(elements, "fx:SIGNALS")
    for msg in messages:
        frame = ET.SubElement(frames_el, "fx:FRAME", ID=f"FRAME_{msg.frame_id:X}")
        ET.SubElement(frame, "fx:SHORT-NAME").text = msg.name
        ET.SubElement(frame, "fx:BYTE-LENGTH").text = str(msg.dlc)
        ET.SubElement(frame, "fx:IDENTIFIER").text = f"0x{msg.frame_id:X}"
        for sig in msg.signals:
            signal = ET.SubElement(signals_el, "fx:SIGNAL", ID=f"SIG_{msg.frame_id:X}_{sig.name}")
            ET.SubElement(signal, "fx:SHORT-NAME").text = sig.name
            ET.SubElement(signal, "fx:BIT-POSITION").text = str(sig.start_bit)
            ET.SubElement(signal, "fx:BIT-LENGTH").text = str(sig.length)
    ET.indent(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
