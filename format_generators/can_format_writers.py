#!/usr/bin/env python3
"""Writers for CAN oriented exchange and trace formats."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from common_trace import (
    CanFrame,
    MessageDef,
    ROUTE_INFO_LENGTH,
    ROUTE_INFO_START_BYTE,
    iso_utc,
    route_label,
    write_text,
)


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
        elif msg.dlc >= ROUTE_INFO_START_BYTE + ROUTE_INFO_LENGTH:
            relation = (
                f"PayloadRouteInfo='{route_label(msg.sender, msg.receiver)}' "
                f"in bytes {ROUTE_INFO_START_BYTE}-{ROUTE_INFO_START_BYTE + ROUTE_INFO_LENGTH - 1}"
            )
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
