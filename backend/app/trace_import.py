"""Read-only trace adapters. Uploads never create engineering objects or evidence."""
from __future__ import annotations

import csv
import io
import itertools
import json
import math
import mmap
import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request

MAX_BYTES = 500 * 1024 * 1024
MAX_EVENTS = 2000
FORMATS = ("csv", "json", "jsonl", "asc", "blf", "log", "trc", "pcap", "pcapng", "mdf", "mf4")
trace_import_api = Blueprint("trace_import", __name__)


def read_json(text: str):
    def reject_constant(value):
        raise ValueError(f"Ungültige JSON-Zahl: {value}")
    return json.loads(text, parse_constant=reject_constant)


def detect_format(data: bytes, filename: str) -> str:
    data = data[:65536]
    if data.startswith(b"MDF     "):
        return "mf4" if data[8:12].startswith(b"4") else "mdf"
    if data.startswith(b"LOGG"):
        return "blf"
    if data[:4] in (b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4", b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d"):
        return "pcap"
    if data.startswith(b"\x0a\x0d\x0d\x0a"):
        return "pcapng"
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix in ("mdf", "mf4", "blf", "pcap", "pcapng"):
        raise ValueError(f"{suffix.upper()}: Dateisignatur fehlt oder ist beschädigt.")
    if suffix in ("asc", "log", "trc"):
        return suffix
    if suffix in ("csv", "json", "jsonl"):
        return suffix
    text = data.decode("utf-8-sig", errors="replace").lstrip()
    if text.startswith(("{", "[")):
        try:
            read_json(text)
            return "json"
        except json.JSONDecodeError:
            return "jsonl"
    if suffix in FORMATS:
        return suffix
    raise ValueError("Unbekanntes Trace-Format. Unterstützt: " + ", ".join(FORMATS))


def text_records(data: bytes, fmt: str, source_path=None):
    if source_path:
        yield from file_text_records(source_path, fmt)
        return
    text = data.decode("utf-8-sig")
    if fmt == "json":
        doc = read_json(text)
        rows = doc if isinstance(doc, list) else doc.get("events", [doc]) if isinstance(doc, dict) else None
        if not isinstance(rows, list):
            raise ValueError("JSON benötigt ein Ereignisarray oder ein Ereignisobjekt.")
        yield from rows
    elif fmt == "jsonl":
        for line in text.splitlines():
            if line.strip():
                yield read_json(line)
    else:
        reader = csv.DictReader(io.StringIO(text), strict=True)
        if not reader.fieldnames or not {"timestamp_s", "time_s", "timestamp", "t"}.intersection(reader.fieldnames):
            raise ValueError("CSV benötigt eine Zeitspalte in Sekunden (z. B. time_s).")
        for row in reader:
            if None in row or None in row.values():
                raise ValueError("CSV: Spaltenzahl stimmt nicht.")
            for key in ("signals", "ethernet"):
                if row.get(key):
                    row[key] = read_json(row[key])
            yield row


def file_text_records(path, fmt):
    """Read only the preview, without decoding the entire uploaded file."""
    with open(path, encoding="utf-8-sig") as source:
        if fmt == "csv":
            reader = csv.DictReader(source, strict=True)
            if not reader.fieldnames or not {"timestamp_s", "time_s", "timestamp", "t"}.intersection(reader.fieldnames):
                raise ValueError("CSV benötigt eine Zeitspalte in Sekunden (z. B. time_s).")
            for row in reader:
                if None in row or None in row.values():
                    raise ValueError("CSV: Spaltenzahl stimmt nicht.")
                for key in ("signals", "ethernet"):
                    if row.get(key):
                        row[key] = read_json(row[key])
                yield row
        elif fmt == "jsonl":
            for line in source:
                if line.strip():
                    yield read_json(line)
        else:
            import ijson
            # Detect an array or the supported events wrapper using parser tokens.
            binary = source.buffer
            start = 3 if binary.read(3) == b"\xef\xbb\xbf" else 0
            binary.seek(start)
            tokens = ijson.parse(binary, use_float=True)
            first = next(tokens, None)
            if first and first[1] == "start_array":
                prefix = "item"
            elif first and first[1] == "start_map":
                prefix = ""
                for key, kind, value in tokens:
                    if key == "events" and kind == "start_array":
                        prefix = "events.item"
                        break
            else:
                raise ValueError("JSON benötigt ein Ereignisarray oder ein Ereignisobjekt.")
            binary.seek(start)
            yield from ijson.items(binary, prefix, use_float=True)


def can_records(data: bytes, fmt: str, source_path=None):
    import can
    readers = {"asc": can.ASCReader, "blf": can.BLFReader, "log": can.CanutilsLogReader, "trc": can.TRCReader, "mf4": can.MF4Reader}
    if source_path:
        stream = open(source_path, "rb") if fmt in ("blf", "mf4") else open(source_path, encoding="utf-8-sig", errors="replace")
    elif fmt in ("blf", "mf4"):
        stream = io.BytesIO(data)
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("cp1252")
        stream = io.StringIO(text)
    with readers[fmt](stream) as reader:
        for msg in reader:
            yield {"timestamp": msg.timestamp, "source": f"CAN {msg.channel}",
                   "technology": f"{'CAN FD' if msg.is_fd else 'CAN'} · {msg.channel}",
                   "message": f"0x{msg.arbitration_id:08X}" if msg.is_extended_id else f"0x{msg.arbitration_id:03X}",
                   "payload_hex": bytes(msg.data).hex(" "), "status": "Rx" if msg.is_rx else "Tx",
                   "finding": "CAN error frame" if msg.is_error_frame else "Remote frame" if msg.is_remote_frame else "",
                   "dlc": msg.dlc, "extended_id": msg.is_extended_id, "signals": [],
                   "channel": msg.channel, "data_length": len(msg.data), "is_fd": msg.is_fd,
                   "bitrate_switch": msg.bitrate_switch,
                   "protocols": {"can": {"arbitration_id": msg.arbitration_id}}, "time_basis": "source"}


def capture_records(data: bytes, fmt: str):
    import dpkt
    import struct
    if fmt == "pcap":
        endian = "<" if data[:4] in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1") else ">"
        if len(data) < 24:
            raise ValueError("PCAP: abgeschnittener Dateiheader.")
        offset = 24
        while offset < len(data):
            if len(data) - offset < 16:
                raise ValueError("PCAP: abgeschnittener Paketheader.")
            captured, original = struct.unpack_from(endian + "II", data, offset + 8)
            if captured > original or offset + 16 + captured > len(data):
                raise ValueError("PCAP: abgeschnittene oder ungültige Paketdaten.")
            offset += 16 + captured
    # dpkt's PCAPNG reader assumes one interface. Reject other layouts explicitly.
    if fmt == "pcapng":
        offset, endian, interfaces, sections = 0, "<", 0, 0
        while offset < len(data):
            if len(data) - offset < 12:
                raise ValueError("PCAPNG: abgeschnittener Block.")
            if data[offset:offset + 4] == b"\x0a\x0d\x0d\x0a":
                endian = "<" if data[offset + 8:offset + 12] == b"\x4d\x3c\x2b\x1a" else ">"
                sections += 1
            kind, length = struct.unpack_from(endian + "II", data, offset)
            if length < 12 or length % 4 or offset + length > len(data) or struct.unpack_from(endian + "I", data, offset + length - 4)[0] != length:
                raise ValueError("PCAPNG: ungültige Blocklänge.")
            interfaces += kind == 1
            if kind == 6:
                if length < 32:
                    raise ValueError("PCAPNG: abgeschnittener Paketheader.")
                interface, _, _, captured, original = struct.unpack_from(endian + "IIIII", data, offset + 8)
                if interface != 0 or not interfaces or captured > original or 32 + ((captured + 3) // 4) * 4 > length:
                    raise ValueError("PCAPNG: ungültige Schnittstelle oder Paketlänge.")
            if sections > 1 or interfaces > 1 or kind in (2, 3):
                raise ValueError("PCAPNG: unterstützt wird eine Section mit einer Schnittstelle und Enhanced Packet Blocks. Capture bitte je Schnittstelle exportieren.")
            offset += length
    reader = (dpkt.pcapng.Reader if fmt == "pcapng" else dpkt.pcap.Reader)(io.BytesIO(data) if isinstance(data, bytes) else data)
    linktype = reader.datalink()
    for timestamp, packet in reader:
        event = {"timestamp": float(timestamp), "technology": f"PCAP linktype {linktype}",
                 "message": f"Packet {linktype}", "payload_hex": packet.hex(" "), "signals": [],
                 "data_length": len(packet), "linktype": linktype, "time_basis": "unix", "protocols": {}}
        if linktype == 1:
            try:
                ethernet = dpkt.ethernet.Ethernet(packet)
                event.update(source=ethernet.src.hex(":"), destination=ethernet.dst.hex(":"),
                             technology="Ethernet", message=f"EtherType 0x{ethernet.type:04X}")
                event["protocols"]["ethernet"] = {"ethertype": f"0x{ethernet.type:04X}"}
                import socket
                ip = ethernet.data
                if isinstance(ip, (dpkt.ip.IP, dpkt.ip6.IP6)):
                    family = socket.AF_INET if isinstance(ip, dpkt.ip.IP) else socket.AF_INET6
                    event["protocols"]["ip"] = {"version": 4 if family == socket.AF_INET else 6,
                        "source": socket.inet_ntop(family, ip.src), "destination": socket.inet_ntop(family, ip.dst)}
                    transport = ip.data
                    if isinstance(transport, (dpkt.tcp.TCP, dpkt.udp.UDP)):
                        event["protocols"]["transport"] = {"name": "TCP" if isinstance(transport, dpkt.tcp.TCP) else "UDP",
                            "source_port": transport.sport, "destination_port": transport.dport}
                        if isinstance(transport, dpkt.tcp.TCP):
                            event["protocols"]["transport"].update(flags=transport.flags, sequence=transport.seq, acknowledgement=transport.ack)
            except (dpkt.UnpackError, ValueError):
                event["finding"] = "Ethernet-Header unvollständig; Rohbytes erhalten."
        yield event


def mdf_records(data: bytes, warnings: list[str], source_path=None):
    from asammdf import MDF
    # Stream channels in bounded chunks; retain original channel timestamps.
    # Session storage need not be time-sorted and never merges different clocks.
    with MDF(source_path or io.BytesIO(data)) as mdf:
        channels = 0
        bus_groups = [group for group in mdf.groups if getattr(group.channel_group, "flags", 0) & 2]
        if bus_groups:
            warnings.append("MDF-Busaufzeichnung: CAN/CAN-FD-Rohdaten; andere Busobjekte nicht übernommen. Signaldecodierung benötigt eine passende Datenbank.")
            bus_records = can_records(data, "mf4", source_path)
            try:
                for event in bus_records:
                    event["timestamp"] -= mdf.header.start_time.timestamp()
                    yield event
            finally:
                bus_records.close()
        for group_index, group in enumerate(mdf.groups):
            if getattr(group.channel_group, "flags", 0) & 2:
                continue
            for channel_index, channel in enumerate(group.channels):
                if channel_index == mdf.masters_db.get(group_index):
                    continue
                channels += 1
                if channels > 256:
                    raise ValueError("MDF-Import unterstützt maximal 256 Messkanäle; Datei bitte aufteilen.")
                offset = 0
                while True:
                    signal = mdf.get(group=group_index, index=channel_index, record_offset=offset, record_count=2000)
                    if signal.samples.dtype.names or signal.samples.ndim != 1:
                        warnings.append(f"MDF-Kanal {channel.name}: strukturierte/Array-Daten nicht als Skalarsignal importiert.")
                        break
                    if not len(signal.samples):
                        break
                    for timestamp, sample in zip(signal.timestamps, signal.samples):
                        value = sample.item()
                        if isinstance(value, bytes):
                            value = value.decode("utf-8", errors="replace")
                        if not isinstance(value, (str, int, float, bool)) or isinstance(value, float) and not math.isfinite(value):
                            value = None
                        yield {"timestamp": float(timestamp), "technology": f"MDF group {group_index}",
                               "source": signal.name, "message": signal.name,
                               "signals": [{"signal": signal.name, "signal_id": f"mdf:{group_index}:{channel_index}",
                                            "value": value, "unit": signal.unit, "quality": "measured" if value is not None else "invalid"}]}
                    offset += len(signal.samples)
                    if len(signal.samples) < 2000:
                        break


def normalize_record(event, index):
    if not isinstance(event, dict):
        raise ValueError(f"Ereignis {index + 1}: ein Objekt wird erwartet.")
    raw = next((event[key] for key in ("timestamp_s", "time_s", "timestamp", "t") if key in event), None)
    event.setdefault("source_record_index", index)
    event.setdefault("source_timestamp", raw)
    if raw is None:
        event["time_status"] = "unavailable"
        event["timestamp"] = None
        return event
    if isinstance(raw, bool):
        raise ValueError(f"Ereignis {index + 1}: Zeitstempel fehlt.")
    timestamp = float(raw)
    if not math.isfinite(timestamp) or timestamp < 0:
        raise ValueError(f"Ereignis {index + 1}: ungültiger Zeitstempel.")
    event["timestamp"] = timestamp
    return event


def import_trace(data: bytes, filename: str, source_path=None) -> dict:
    if len(data) > MAX_BYTES:
        raise ValueError("Trace-Import: maximal 500 MiB.")
    if not data:
        raise ValueError("Die Trace-Datei ist leer.")
    fmt = detect_format(data, filename)
    warnings = []
    if fmt in ("csv", "json", "jsonl"):
        records = text_records(data, fmt, source_path)
    elif fmt in ("asc", "blf", "log", "trc"):
        records = can_records(data, fmt, source_path)
        warnings.append("CAN/CAN-FD-Frames; andere Busobjekte und Kommentare werden nicht übernommen. Signaldecodierung benötigt eine passende Datenbank (z. B. DBC).")
    elif fmt in ("pcap", "pcapng"):
        records = capture_records(data, fmt)
        warnings.append("Paket-Rohbytes und Ethernet-Adressen; keine anwendungsspezifische Signaldecodierung.")
    else:
        records = mdf_records(data, warnings, source_path)
    try:
        events = list(itertools.islice(records, MAX_EVENTS + 1))
    finally:
        records.close()
    truncated = len(events) > MAX_EVENTS
    events = events[:MAX_EVENTS]
    if not events:
        raise ValueError("Keine unterstützten Ereignisse oder skalaren Messkanäle in der Datei gefunden.")
    events = [normalize_record(event, index) for index, event in enumerate(events)]
    # Unknown time does not imply zero or an ordering relative to other clocks.
    if all(event["timestamp"] is not None for event in events) and len({str(event.get("time_basis", "source")) for event in events}) == 1:
        events.sort(key=lambda event: event["timestamp"])
    if truncated:
        warnings.append(f"Vorschau auf {MAX_EVENTS} Ereignisse begrenzt; Datei nicht vollständig analysiert.")
    return {"format": fmt, "events": events, "truncated": truncated, "warnings": warnings,
            "analysis_only": True, "imported_events": len(events)}


@trace_import_api.post("/trace-import")
def upload_trace():
    request.max_content_length = MAX_BYTES
    try:
        with tempfile.TemporaryDirectory(prefix="nis-trace-") as directory:
            path = Path(directory) / "upload.trace"
            size = 0
            with path.open("wb") as target:
                while chunk := request.stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        from werkzeug.exceptions import RequestEntityTooLarge
                        raise RequestEntityTooLarge()
                    target.write(chunk)
            if not size:
                raise ValueError("Die Trace-Datei ist leer.")
            with path.open("rb") as source, mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as data:
                from .trace_sessions import persist_import
                return jsonify(persist_import(data, request.args.get("filename", ""), path))
    except ImportError:
        return jsonify(error="Trace-Adapter fehlt im Backend. Runtime-Abhängigkeiten installieren und Backend neu starten."), 503
    except Exception as exc:
        from werkzeug.exceptions import RequestEntityTooLarge
        if isinstance(exc, RequestEntityTooLarge):
            return jsonify(error="Trace-Import: maximal 500 MiB."), 413
        # Third-party parsers use several exception types; do not return a partial session.
        return jsonify(error=f"Trace konnte nicht eingelesen werden: {str(exc)[:300]}"), 422

@trace_import_api.get('/trace-import/<session_id>')
def get_import_window(session_id):
    from .trace_sessions import session_window
    try:
        return jsonify(session_window(session_id, cursor=int(request.args.get('cursor', 0)),
            limit=int(request.args.get('limit', 500)), start_s=float(request.args.get('start_s', 0)),
            end_s=float(request.args.get('end_s', 1e15)), query=request.args.get('q', '')))
    except FileNotFoundError:
        return jsonify(error='Trace-Session im aktiven Projekt nicht gefunden.'), 404
    except ValueError as exc:
        return jsonify(error=str(exc)), 422
