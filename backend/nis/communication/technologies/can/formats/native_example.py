"""Existing CAN native example generation and mutable format records.

This preserves the standalone demonstration API; validated project generation
continues through the canonical registry and uses no demonstration defaults.
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
import can
from backend.nis.traces.trace_support import route_label
from backend.nis.traces.trace_realism import external_signal_records, physical_raw_value, signal_specs_for_message
from backend.nis.communication.technologies.can.encoding import crc8_autosar, get_unsigned_le, verify_payload_crc, set_unsigned_le_strict as set_unsigned_le
from backend.nis.communication.technologies.can.formats.trace_model import ROUTE_INFO_START_BYTE, ROUTE_INFO_LENGTH
from backend.nis.industries.automotive.templates.trace_example import trace_example

DEFAULT_ROUTING_ROWS = [{key:row[key] for key in ('sender','receiver','cycle_ms','channel','gateway_to_channel','frame_id','name')} for row in trace_example()['DEFAULT_ROUTING_ROWS']]
try:
    CanMessage, BLFReader, BLFWriter = can.Message, can.BLFReader, can.BLFWriter
except AttributeError:
    from can.message import Message as CanMessage
    from can.io.blf import BLFReader, BLFWriter

@dataclass
class SignalDef:
    name: str
    start_bit: int
    length: int
    factor: float
    offset: float
    minimum: int
    maximum: int
    unit: str
    kind: str  # normal | counter | crc | mux | diag


@dataclass
class MessageDef:
    name: str
    frame_id: int
    sender: str
    receivers: List[str]
    cycle_ms: int
    channel: int
    dlc: int
    is_fd: bool
    bus_type: str = "classic"  # classic | fd | xl
    signals: List[SignalDef] = field(default_factory=list)
    gateway_to_channel: int | None = None
    kind: str = "data"  # data | response
    response_for: int | None = None


def add_data_signals(msg: MessageDef, can_fd: bool, external_signals: List[Dict[str, Any]] | None = None) -> None:
    external_records = external_signal_records(external_signals)
    if external_records:
        for record in external_records:
            msg.signals.append(
                SignalDef(
                    name=record["name"],
                    start_bit=record["start_bit"],
                    length=record["length"],
                    factor=record["factor"],
                    offset=record["offset"],
                    minimum=record["minimum"],
                    maximum=record["maximum"],
                    unit=record["unit"],
                    kind=record["kind"],
                )
            )
        return

    # Layout: Byte 0 CRC, Byte 1 Counter/Mux/Status, ab Byte 2 Nutzsignale.
    msg.signals.append(SignalDef("CRC8", 0, 8, 1, 0, 0, 255, "", "crc"))
    msg.signals.append(SignalDef("AliveCounter", 8, 4, 1, 0, 0, 15, "", "counter"))
    msg.signals.append(SignalDef("MuxState", 12, 4, 1, 0, 0, 15, "", "mux"))

    bit = 16
    signal_count = 12 if can_fd else 6
    length = 12 if can_fd else 8
    receiver = msg.receivers[0] if msg.receivers else ""
    signal_specs = signal_specs_for_message(msg.sender, receiver, msg.name, signal_count, length)
    for spec in signal_specs:
        # 12-bit Signale sind typisch kompakt und erlauben viele Signale in CAN-FD.
        if bit + length > msg.dlc * 8:
            break
        msg.signals.append(
            SignalDef(
                name=spec.name,
                start_bit=bit,
                length=length,
                factor=spec.factor,
                offset=spec.offset,
                minimum=spec.minimum,
                maximum=spec.maximum,
                unit=spec.unit,
                kind=spec.kind,
            )
        )
        bit += length

    if can_fd:
        for idx in range(ROUTE_INFO_LENGTH):
            start_bit = (ROUTE_INFO_START_BYTE + idx) * 8
            if start_bit + 8 > msg.dlc * 8:
                break
            msg.signals.append(
                SignalDef(
                    name=f"RouteInfoChar_{idx:02d}",
                    start_bit=start_bit,
                    length=8,
                    factor=1,
                    offset=0,
                    minimum=0,
                    maximum=255,
                    unit="ascii",
                    kind="route_info",
                )
            )


def add_response_signals(msg: MessageDef) -> None:
    msg.signals.extend(
        [
            SignalDef("CRC8", 0, 8, 1, 0, 0, 255, "", "crc"),
            SignalDef("ResponseCounter", 8, 4, 1, 0, 0, 15, "", "counter"),
            SignalDef("AckState", 12, 4, 1, 0, 0, 15, "", "ack"),
            SignalDef("ReceivedFrameId", 16, 11, 1, 0, 0, 2047, "", "diag"),
            SignalDef("ReceivedCounter", 27, 4, 1, 0, 0, 15, "", "diag"),
            SignalDef("ChecksumOk", 31, 1, 1, 0, 0, 1, "", "diag"),
            SignalDef("PayloadLength", 32, 8, 1, 0, 0, 64, "byte", "diag"),
            SignalDef("ErrorCode", 40, 8, 1, 0, 0, 255, "", "diag"),
            SignalDef("ProcessingTimeUs", 48, 16, 1, 0, 0, 65535, "us", "diag"),
        ]
    )

    if msg.dlc > 8:
        msg.signals.extend(
            [
                SignalDef("ResponseSequence", 64, 16, 1, 0, 0, 65535, "", "diag"),
                SignalDef("ReceivedCrc", 80, 8, 1, 0, 0, 255, "", "diag"),
                SignalDef("CalculatedCrc", 88, 8, 1, 0, 0, 255, "", "diag"),
            ]
        )


def build_messages(
    num_messages: int = 100,
    bus_type: str = "fd",
    seed: int = 42,
    channel_count: int = 2,
    routing_rows: List[Dict[str, object]] | None = None,
) -> List[MessageDef]:
    random.seed(seed)
    can_fd_storage = bus_type in {"fd", "xl"}
    channel_count = max(1, min(16, channel_count))
    routing_rows = routing_rows or [
        normalized_routing_row(row, index, channel_count)
        for index, row in enumerate(DEFAULT_ROUTING_ROWS)
    ]

    messages: List[MessageDef] = []

    # CAN-FD: Signale + Counter + CRC passen in 64 Byte.
    # Classic CAN: 8 Byte, deshalb werden nur so viele Signale physisch codiert,
    # wie in 8 Byte passen. Metadaten bleiben als Kommentar/Name erhalten.
    # CAN XL wird hier logisch simuliert, aber als CAN-FD-kompatibler BLF gespeichert,
    # weil die installierte python-can/BLF-Version kein natives CAN-XL-Objekt anbietet.
    dlc = 64 if can_fd_storage else 8

    for i in range(num_messages):
        route = routing_rows[i % len(routing_rows)]
        sender = str(route["sender"])
        receiver = str(route["receiver"])
        cycle_ms = int(route["cycle_ms"])
        channel = int(route["channel"])
        gateway_to_channel = route["gateway_to_channel"]
        frame_id = int(route["frame_id"]) + (i // len(routing_rows)) * 0x20
        base_name = str(route["name"])

        msg = MessageDef(
            name=f"DATA_{i:03d}_{base_name}",
            frame_id=frame_id,
            sender=sender,
            receivers=[receiver],
            cycle_ms=cycle_ms,
            channel=channel,
            dlc=dlc,
            is_fd=can_fd_storage,
            bus_type=bus_type,
            gateway_to_channel=int(gateway_to_channel) if gateway_to_channel is not None else None,
            kind="data",
        )
        add_data_signals(msg, can_fd_storage, external_signals=route.get("signals"))
        messages.append(msg)

        response_dlc = 16 if can_fd_storage else 8
        response_msg = MessageDef(
            name=f"RESP_{i:03d}_{receiver}_TO_{sender}",
            frame_id=0x600 + i,
            sender=receiver,
            receivers=[sender],
            cycle_ms=cycle_ms,
            channel=channel,
            dlc=response_dlc,
            is_fd=can_fd_storage,
            bus_type=bus_type,
            kind="response",
            response_for=frame_id,
        )
        add_response_signals(response_msg)
        messages.append(response_msg)

    return messages


def encode_message_payload(
    msg: MessageDef,
    timestamp_s: float,
    alive_counter: int,
    inject_crc_error: bool = False,
    inject_counter_error: bool = False,
    inject_dlc_error: bool = False,
    filter_bank: Any | None = None,
) -> bytes:
    payload_len = msg.dlc
    if inject_dlc_error and payload_len > 8:
        payload_len = 32
    elif inject_dlc_error:
        payload_len = 7

    payload = bytearray(
        ((msg.frame_id + int(timestamp_s * 1000.0) + alive_counter * 31 + idx * 17) & 0xFF)
        for idx in range(payload_len)
    )

    counter_value = (alive_counter + (3 if inject_counter_error else 0)) & 0xF
    mux_value = int((timestamp_s * 10) % 16) & 0xF

    physical_index = 0
    for sig in msg.signals:
        if sig.start_bit + sig.length > payload_len * 8:
            continue
        if sig.kind == "crc":
            continue
        if sig.kind == "counter":
            value = counter_value
        elif sig.kind == "mux":
            value = mux_value
        elif sig.kind == "route_info":
            continue
        else:
            value = physical_raw_value(
                signal_name=sig.name,
                factor=sig.factor,
                offset=sig.offset,
                minimum=sig.minimum,
                maximum=sig.maximum,
                timestamp_s=timestamp_s,
                frame_id=msg.frame_id,
                signal_index=physical_index,
            )
            if filter_bank is not None:
                value = filter_bank.filter_value(
                    signal_name=sig.name,
                    sender=msg.sender,
                    receiver=msg.receivers[0] if msg.receivers else None,
                    role=None,
                    timestamp_s=timestamp_s,
                    measurement=value,
                    minimum=sig.minimum,
                    maximum=sig.maximum,
                )
            physical_index += 1
        set_unsigned_le(payload, sig.start_bit, sig.length, value)

    has_route_info = any(sig.kind == "route_info" for sig in msg.signals)
    if has_route_info and msg.is_fd and msg.receivers:
        route_bytes = route_label(msg.sender, msg.receivers[0]).encode("ascii", errors="replace")
        route_field = route_bytes[:ROUTE_INFO_LENGTH].ljust(ROUTE_INFO_LENGTH, b"\x00")
        start = ROUTE_INFO_START_BYTE
        end = min(start + ROUTE_INFO_LENGTH, len(payload))
        payload[start:end] = route_field[: end - start]

    has_payload_crc = any(sig.kind == "crc" or sig.name.lower() in {"crc", "crc8", "checksum"} for sig in msg.signals)
    if has_payload_crc:
        crc_value = crc8_autosar(bytes(payload[1:]))
        if inject_crc_error:
            crc_value ^= 0x55
        set_unsigned_le(payload, 0, 8, crc_value)
    return bytes(payload)


def encode_response_payload(
    response_msg: MessageDef,
    request_msg: MessageDef,
    request_payload: bytes,
    response_counter: int,
    processing_time_us: int,
    response_sequence: int,
) -> bytes:
    payload = bytearray(
        ((response_msg.frame_id + response_counter * 19 + idx * 23) & 0xFF)
        for idx in range(response_msg.dlc)
    )

    has_request_crc = any(sig.kind == "crc" or sig.name.lower() in {"crc", "crc8", "checksum"} for sig in request_msg.signals)
    has_request_counter = any("counter" in sig.kind.lower() or "counter" in sig.name.lower() for sig in request_msg.signals)
    received_crc = request_payload[0] if request_payload else 0
    calculated_crc = crc8_autosar(request_payload[1:]) if len(request_payload) >= 2 else 0
    checksum_ok = int((not has_request_crc) or (received_crc == calculated_crc and len(request_payload) >= 2))
    dlc_ok = int(len(request_payload) == request_msg.dlc)
    received_counter = get_unsigned_le(request_payload, 8, 4) if len(request_payload) > 1 else 0
    expected_counter = response_counter & 0xF
    counter_ok = int((not has_request_counter) or received_counter == expected_counter)

    error_code = 0
    if not checksum_ok:
        error_code |= 0x01
    if not dlc_ok:
        error_code |= 0x02
    if not counter_ok:
        error_code |= 0x04

    # 1 = Daten korrekt empfangen, 2 = CRC-Fehler, 3 = DLC-Fehler, 4 = Counter-Fehler.
    if error_code == 0:
        ack_state = 1
    elif error_code & 0x01:
        ack_state = 2
    elif error_code & 0x02:
        ack_state = 3
    else:
        ack_state = 4

    set_unsigned_le(payload, 8, 4, response_counter)
    set_unsigned_le(payload, 12, 4, ack_state)
    set_unsigned_le(payload, 16, 11, request_msg.frame_id)
    set_unsigned_le(payload, 27, 4, received_counter)
    set_unsigned_le(payload, 31, 1, checksum_ok)
    set_unsigned_le(payload, 32, 8, len(request_payload))
    set_unsigned_le(payload, 40, 8, error_code)
    set_unsigned_le(payload, 48, 16, processing_time_us)

    if response_msg.dlc > 8:
        set_unsigned_le(payload, 64, 16, response_sequence)
        set_unsigned_le(payload, 80, 8, received_crc)
        set_unsigned_le(payload, 88, 8, calculated_crc)

    set_unsigned_le(payload, 0, 8, crc8_autosar(bytes(payload[1:])))
    return bytes(payload)


def iter_scheduled_events(messages: List[MessageDef], duration_s: float) -> Iterable[Tuple[float, MessageDef]]:
    for msg in messages:
        t = 0.0
        while t <= duration_s:
            # kleiner normaler Scheduler-Jitter im Mikro-/Millisekundenbereich
            jitter_s = random.uniform(-0.0004, 0.0008)
            yield max(0.0, t + jitter_s), msg
            t += msg.cycle_ms / 1000.0


def generate_blf(
    out_blf: Path,
    duration_s: float,
    bus_type: str,
    seed: int,
    num_messages: int = 100,
    nominal_bitrate: int | None = None,
    data_bitrate: int | None = None,
    channel_count: int = 2,
    routing_rows: List[Dict[str, object]] | None = None,
    start_utc: float | None = None,
    filter_bank: Any | None = None,
) -> List[MessageDef]:
    random.seed(seed)
    channel_count = max(1, min(16, channel_count))
    messages = build_messages(
        num_messages=num_messages,
        bus_type=bus_type,
        seed=seed,
        channel_count=channel_count,
        routing_rows=routing_rows,
    )
    trace_start_utc = datetime.now(timezone.utc).timestamp() if start_utc is None else start_utc

    data_messages = [m for m in messages if m.kind == "data"]
    response_by_request = {m.response_for: m for m in messages if m.kind == "response"}

    alive: Dict[int, int] = {m.frame_id: 0 for m in messages}
    events = sorted(iter_scheduled_events(data_messages, duration_s), key=lambda x: x[0])

    # Störszenarien: realistische, seltene Fehler
    dropout_probability = 0.0015
    crc_error_probability = 0.0010
    counter_error_probability = 0.0010
    dlc_error_probability = 0.0005
    timing_violation_probability = 0.0010

    bus_off_start = duration_s * 0.55
    bus_off_end = bus_off_start + 0.25
    bus_off_channel = 1 if channel_count > 1 else None

    recorded_messages = []
    can_fd_storage = bus_type in {"fd", "xl"}

    def append_control_frame(rel_time_s: float, channel: int, arbitration_id: int, sender: str, receiver: str, payload_text: str) -> None:
        payload = bytearray(64 if can_fd_storage else 8)
        encoded = payload_text.encode("ascii", errors="replace")[: len(payload) - 1]
        payload[1 : 1 + len(encoded)] = encoded
        payload[0] = crc8_autosar(bytes(payload[1:]))
        recorded_messages.append(
            CanMessage(
                timestamp=trace_start_utc + rel_time_s,
                arbitration_id=arbitration_id,
                is_extended_id=False,
                is_fd=can_fd_storage,
                bitrate_switch=can_fd_storage,
                error_state_indicator=False,
                dlc=len(payload),
                data=bytes(payload),
                channel=channel,
                is_rx=False,
            )
        )

    routed_messages = [msg for msg in data_messages if msg.gateway_to_channel is not None]
    for index, msg in enumerate(routed_messages[:8]):
        base = 0.002 + index * 0.006
        append_control_frame(base, msg.channel, 0x080 + index, msg.sender, "CENTRAL_GATEWAY", f"NM_WAKE {msg.sender}")
        append_control_frame(base + 0.0015, msg.channel, 0x0A0 + index, "CENTRAL_GATEWAY", msg.receivers[0], f"ROUTE_OPEN {msg.sender}->{msg.receivers[0]}")
        append_control_frame(base + 0.0030, msg.channel, 0x0C0 + index, msg.sender, msg.receivers[0], f"CONNECT {msg.sender}->{msg.receivers[0]}")
        append_control_frame(base + 0.0045, msg.channel, 0x0E0 + index, msg.receivers[0], msg.sender, f"ACK CONNECT {msg.receivers[0]}")

    for timestamp_s, msg in events:
        absolute_timestamp_s = trace_start_utc + timestamp_s

        # Bus-Off Pause auf einem Kanal
        if bus_off_channel is not None and msg.channel == bus_off_channel and bus_off_start <= timestamp_s <= bus_off_end:
            continue

        # Dropout / Lost frame
        if random.random() < dropout_probability:
            alive[msg.frame_id] = (alive[msg.frame_id] + 1) & 0xF
            continue

        if random.random() < timing_violation_probability:
            # zu frühe oder zu späte Botschaft
            timestamp_s += random.choice([-1, 1]) * random.uniform(0.003, 0.015)
            timestamp_s = max(0.0, timestamp_s)
            absolute_timestamp_s = trace_start_utc + timestamp_s

        inject_crc = random.random() < crc_error_probability
        inject_counter = random.random() < counter_error_probability
        inject_dlc = random.random() < dlc_error_probability

        data = encode_message_payload(
            msg,
            timestamp_s,
            alive[msg.frame_id],
            inject_crc_error=inject_crc,
            inject_counter_error=inject_counter,
            inject_dlc_error=inject_dlc,
            filter_bank=filter_bank,
        )

        can_msg = CanMessage(
            timestamp=absolute_timestamp_s,
            arbitration_id=msg.frame_id,
            is_extended_id=False,
            is_fd=msg.is_fd,
            bitrate_switch=msg.is_fd,
            error_state_indicator=False,
            dlc=len(data),
            data=data,
            channel=msg.channel,
            is_rx=False,
        )
        recorded_messages.append(can_msg)

        response_msg = response_by_request.get(msg.frame_id)
        if response_msg is not None:
            processing_time_us = random.randint(350, 1800)
            response_data = encode_response_payload(
                response_msg=response_msg,
                request_msg=msg,
                request_payload=data,
                response_counter=alive[msg.frame_id],
                processing_time_us=processing_time_us,
                response_sequence=alive[response_msg.frame_id],
            )
            response_can_msg = CanMessage(
                timestamp=absolute_timestamp_s + processing_time_us / 1_000_000.0,
                arbitration_id=response_msg.frame_id,
                is_extended_id=False,
                is_fd=response_msg.is_fd,
                bitrate_switch=response_msg.is_fd,
                error_state_indicator=False,
                dlc=len(response_data),
                data=response_data,
                channel=response_msg.channel,
                is_rx=True,
            )
            recorded_messages.append(response_can_msg)
            alive[response_msg.frame_id] = (alive[response_msg.frame_id] + 1) & 0xF

        # Gateway: jedes 10. Signal wird auf anderen Kanal gespiegelt,
        # mit neuer ID und realistischem Gateway-Delay.
        if msg.gateway_to_channel is not None:
            gw_data = bytearray(data)
            if any(sig.kind == "route_info" for sig in msg.signals) and len(gw_data) > 1:
                gw_data[1] ^= 0x80  # Gateway-Statusbit simuliert
            gw_msg = CanMessage(
                timestamp=absolute_timestamp_s + random.uniform(0.001, 0.004),
                arbitration_id=0x500 + (msg.frame_id & 0xFF),
                is_extended_id=False,
                is_fd=msg.is_fd,
                bitrate_switch=msg.is_fd,
                error_state_indicator=False,
                dlc=len(gw_data),
                data=bytes(gw_data),
                channel=msg.gateway_to_channel,
                is_rx=False,
            )
            recorded_messages.append(gw_msg)

        alive[msg.frame_id] = (alive[msg.frame_id] + 1) & 0xF

    with BLFWriter(str(out_blf)) as writer:
        for can_msg in sorted(recorded_messages, key=lambda item: item.timestamp):
            writer.on_message_received(can_msg)

    return messages


def write_dbc(
    path: Path,
    messages: List[MessageDef],
    nominal_bitrate: int | None = None,
    data_bitrate: int | None = None,
) -> None:
    nodes = sorted({m.sender for m in messages} | {r for m in messages for r in m.receivers})

    lines: List[str] = []
    lines.append('VERSION "Realistic CAN Trace Generator"')
    lines.append('')
    lines.append('NS_ :')
    lines.append('\tNS_DESC_')
    lines.append('\tCM_')
    lines.append('\tBA_DEF_')
    lines.append('\tBA_')
    lines.append('\tVAL_')
    lines.append('')
    lines.append('BS_:')
    lines.append('')
    lines.append('BU_: ' + ' '.join(nodes))
    lines.append('')

    for msg in messages:
        lines.append(f'BO_ {msg.frame_id} {msg.name}: {msg.dlc} {msg.sender}')
        for sig in msg.signals:
            receivers = ','.join(msg.receivers)
            endian = '1'  # Intel/little endian
            signed = '+'
            lines.append(
                f' SG_ {sig.name} : {sig.start_bit}|{sig.length}@{endian}{signed} '
                f'({sig.factor},{sig.offset}) [{sig.minimum}|{sig.maximum}] "{sig.unit}" {receivers}'
            )
        gw = f' Gateway to CAN{msg.gateway_to_channel}' if msg.gateway_to_channel is not None else ''
        if msg.bus_type == "xl":
            bus_label = " CAN-XL"
        elif msg.bus_type == "fd":
            bus_label = " CAN-FD"
        else:
            bus_label = " Classic-CAN"
        nominal_info = f' NominalBitrate={nominal_bitrate // 1000}kbit/s;' if nominal_bitrate else ''
        data_info = f' DataBitrate={data_bitrate // 1000}kbit/s;' if msg.bus_type in {"fd", "xl"} and data_bitrate else ''
        xl_info = ' NativeCanXl=false; StoredAs=CAN-FD-compatible-BLF;' if msg.bus_type == "xl" else ''
        if msg.kind == "response":
            relation = f' ResponseFor=0x{msg.response_for:X}; ACK/NACK with CRC, DLC and counter check;'
        else:
            route = route_label(msg.sender, msg.receivers[0]) if msg.receivers else msg.sender
            if any(sig.kind == "route_info" for sig in msg.signals):
                relation = (
                    f' Data request; receiver answers with response frame; '
                    f"PayloadRouteInfo='{route}' in bytes {ROUTE_INFO_START_BYTE}-"
                    f'{ROUTE_INFO_START_BYTE + ROUTE_INFO_LENGTH - 1};'
                )
            elif msg.is_fd:
                relation = (
                    f' Data request; receiver answers with response frame; '
                    f"ExternalSignalLayout=preserved; PayloadRouteInfo not injected;"
                )
            else:
                relation = (
                    f' Data request; receiver answers with response frame; '
                    f"PayloadRouteInfo='{route}' only in DBC comment because Classic CAN payload is 8 bytes;"
                )
        lines.append(
            f'CM_ BO_ {msg.frame_id} "Cycle={msg.cycle_ms}ms; Channel=CAN{msg.channel};'
            f'{bus_label};{nominal_info}{data_info}{xl_info} {relation}{gw}";'
        )
        lines.append('')

    path.write_text('\n'.join(lines), encoding='utf-8')


def validate_blf(path: Path) -> Tuple[int, float, float]:
    count = 0
    first = math.inf
    last = 0.0
    with BLFReader(str(path)) as reader:
        for msg in reader:
            count += 1
            first = min(first, msg.timestamp)
            last = max(last, msg.timestamp)
    return count, first if first != math.inf else 0.0, last

from backend.nis.communication.technologies.can.formats.routing import normalized_routing_row
