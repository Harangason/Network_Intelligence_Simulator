#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Realistischer CAN/CAN-FD BLF Trace Generator

Erzeugt:
- BLF Trace mit 10 Sendern/Empfängern
- 100 zyklische Botschaften
- je 25 Signalen logisch pro Botschaft
- Classic CAN und CAN-FD Unterstützung
- DBC-Datei passend zum Trace
- Rolling/Alive Counter
- CRC-8 über Nutzdaten
- Gateway-Weiterleitung auf zweiten Kanal
- Fehler-/Störszenarien: Dropouts, Jitter, Timeout-Lücken, Bus-Off-Pause,
  DLC-Fehler, Counter-Fehler, CRC-Fehler, Timing-Violations

Installation:
    py -m pip install python-can

Beispiel:
    py generate_realistic_can_blf.py --duration 60 --out realistic_can_trace.blf
    py generate_realistic_can_blf.py --duration 60 --can-fd --out realistic_canfd_trace.blf

Hinweis:
- BLF ist ein Vector-nahes Binärformat. python-can kann BLF schreiben/lesen.
- DBC enthält bei Classic CAN nur die ersten Signale, die in 8 Byte passen.
  Für 25 Signale pro Botschaft nutzt dieser Generator CAN-FD als realistischere Option.
"""
#py generate_realistic_can_blf.py --duration 60 --out realistic_can_trace.blf
#py generate_realistic_can_blf.py --classic-can --duration 60 --out realistic_classic_can_trace.blf
from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import can

try:
    CanMessage = can.Message
    BLFReader = can.BLFReader
    BLFWriter = can.BLFWriter
except AttributeError:
    from can.message import Message as CanMessage
    from can.io.blf import BLFReader, BLFWriter


# -----------------------------
# Datenmodell
# -----------------------------

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
    signals: List[SignalDef] = field(default_factory=list)
    gateway_to_channel: int | None = None


# -----------------------------
# CRC / Packing
# -----------------------------

def crc8_autosar(data: bytes, start_value: int = 0xFF, final_xor: int = 0xFF) -> int:
    """CRC-8 SAE J1850/AUTOSAR-ähnlich: poly 0x1D."""
    crc = start_value
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x1D) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc ^ final_xor


def set_unsigned_le(payload: bytearray, start_bit: int, length: int, value: int) -> None:
    """Setzt ein unsigned little-endian / Intel Signal bitweise."""
    max_value = (1 << length) - 1
    value = int(value) & max_value
    for bit in range(length):
        absolute_bit = start_bit + bit
        byte_index = absolute_bit // 8
        bit_index = absolute_bit % 8
        if value & (1 << bit):
            payload[byte_index] |= 1 << bit_index
        else:
            payload[byte_index] &= ~(1 << bit_index)


def triangle_wave(t_s: float, period_s: float, minimum: int, maximum: int) -> int:
    if period_s <= 0:
        return minimum
    phase = (t_s % period_s) / period_s
    if phase < 0.5:
        y = phase * 2.0
    else:
        y = (1.0 - phase) * 2.0
    return int(minimum + y * (maximum - minimum))


# -----------------------------
# Netzwerkdefinition
# -----------------------------

def build_messages(num_messages: int = 100, can_fd: bool = True, seed: int = 42) -> List[MessageDef]:
    random.seed(seed)

    senders = [f"ECU_{i:02d}" for i in range(1, 11)]
    receivers = [f"ECU_{i:02d}" for i in range(1, 11)]
    cycle_pool = [10, 20, 50, 100]

    messages: List[MessageDef] = []

    # CAN-FD: 25 Signale + Counter + CRC passen in 64 Byte.
    # Classic CAN: 8 Byte, deshalb werden nur so viele Signale physisch codiert,
    # wie in 8 Byte passen. Metadaten bleiben als Kommentar/Name erhalten.
    dlc = 64 if can_fd else 8

    for i in range(num_messages):
        sender = senders[i % len(senders)]
        rx_candidates = [r for r in receivers if r != sender]
        msg_receivers = random.sample(rx_candidates, k=2)
        cycle_ms = cycle_pool[i % len(cycle_pool)]
        channel = 0 if i < num_messages // 2 else 1
        frame_id = 0x100 + i

        msg = MessageDef(
            name=f"MSG_{i:03d}_{sender}_TO_{msg_receivers[0]}",
            frame_id=frame_id,
            sender=sender,
            receivers=msg_receivers,
            cycle_ms=cycle_ms,
            channel=channel,
            dlc=dlc,
            is_fd=can_fd,
            gateway_to_channel=(1 - channel) if i % 10 == 0 else None,
        )

        # Layout: Byte 0 CRC, Byte 1 Counter/Mux/Status, ab Byte 2 Nutzsignale.
        msg.signals.append(SignalDef("CRC8", 0, 8, 1, 0, 0, 255, "", "crc"))
        msg.signals.append(SignalDef("AliveCounter", 8, 4, 1, 0, 0, 15, "", "counter"))
        msg.signals.append(SignalDef("MuxState", 12, 4, 1, 0, 0, 15, "", "mux"))

        bit = 16
        for s in range(25):
            # 12-bit Signale sind typisch kompakt und erlauben viele Signale in CAN-FD.
            length = 12 if can_fd else 8
            if bit + length > dlc * 8:
                # Classic-CAN physisch voll. Rest wäre in echter Architektur auf Folgeframes verteilt.
                break
            msg.signals.append(
                SignalDef(
                    name=f"SIG_{i:03d}_{s:02d}",
                    start_bit=bit,
                    length=length,
                    factor=0.1,
                    offset=0.0,
                    minimum=0,
                    maximum=(1 << length) - 1,
                    unit=random.choice(["km/h", "rpm", "deg", "Nm", "V", "A", "%", "C"]),
                    kind="normal",
                )
            )
            bit += length

        messages.append(msg)

    return messages


# -----------------------------
# Nutzdaten erzeugen
# -----------------------------

def encode_message_payload(
    msg: MessageDef,
    timestamp_s: float,
    alive_counter: int,
    inject_crc_error: bool = False,
    inject_counter_error: bool = False,
    inject_dlc_error: bool = False,
) -> bytes:
    payload_len = msg.dlc
    if inject_dlc_error and payload_len > 8:
        payload_len = 32
    elif inject_dlc_error:
        payload_len = 7

    payload = bytearray(payload_len)

    counter_value = (alive_counter + (3 if inject_counter_error else 0)) & 0xF
    mux_value = int((timestamp_s * 10) % 16) & 0xF

    for sig in msg.signals:
        if sig.start_bit + sig.length > payload_len * 8:
            continue
        if sig.kind == "crc":
            continue
        if sig.kind == "counter":
            value = counter_value
        elif sig.kind == "mux":
            value = mux_value
        else:
            # Deterministisch, aber lebendig: Dreieck + leichte Störung.
            sig_index = int(sig.name.split("_")[-1]) if sig.name.split("_")[-1].isdigit() else 0
            base = triangle_wave(
                timestamp_s + sig_index * 0.07,
                period_s=1.0 + (sig_index % 9) * 0.4,
                minimum=sig.minimum,
                maximum=sig.maximum,
            )
            noise = random.randint(-3, 3)
            value = max(sig.minimum, min(sig.maximum, base + noise))
        set_unsigned_le(payload, sig.start_bit, sig.length, value)

    crc_value = crc8_autosar(bytes(payload[1:]))
    if inject_crc_error:
        crc_value ^= 0x55
    set_unsigned_le(payload, 0, 8, crc_value)
    return bytes(payload)


# -----------------------------
# BLF Trace erzeugen
# -----------------------------

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
    can_fd: bool,
    seed: int,
    num_messages: int = 100,
) -> List[MessageDef]:
    random.seed(seed)
    messages = build_messages(num_messages=num_messages, can_fd=can_fd, seed=seed)

    alive: Dict[int, int] = {m.frame_id: 0 for m in messages}
    events = sorted(iter_scheduled_events(messages, duration_s), key=lambda x: x[0])

    # Störszenarien: realistische, seltene Fehler
    dropout_probability = 0.0015
    crc_error_probability = 0.0010
    counter_error_probability = 0.0010
    dlc_error_probability = 0.0005
    timing_violation_probability = 0.0010

    bus_off_start = duration_s * 0.55
    bus_off_end = bus_off_start + 0.25
    bus_off_channel = 1

    with BLFWriter(str(out_blf)) as writer:
        for timestamp_s, msg in events:
            # Bus-Off Pause auf einem Kanal
            if msg.channel == bus_off_channel and bus_off_start <= timestamp_s <= bus_off_end:
                continue

            # Dropout / Lost frame
            if random.random() < dropout_probability:
                alive[msg.frame_id] = (alive[msg.frame_id] + 1) & 0xF
                continue

            if random.random() < timing_violation_probability:
                # zu frühe oder zu späte Botschaft
                timestamp_s += random.choice([-1, 1]) * random.uniform(0.003, 0.015)
                timestamp_s = max(0.0, timestamp_s)

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
            )

            can_msg = CanMessage(
                timestamp=timestamp_s,
                arbitration_id=msg.frame_id,
                is_extended_id=False,
                is_fd=msg.is_fd,
                bitrate_switch=msg.is_fd,
                error_state_indicator=False,
                dlc=len(data),
                data=data,
                channel=msg.channel,
            )
            writer.on_message_received(can_msg)

            # Gateway: jedes 10. Signal wird auf anderen Kanal gespiegelt,
            # mit neuer ID und realistischem Gateway-Delay.
            if msg.gateway_to_channel is not None:
                gw_data = bytearray(data)
                if len(gw_data) > 1:
                    gw_data[1] ^= 0x80  # Gateway-Statusbit simuliert
                gw_msg = CanMessage(
                    timestamp=timestamp_s + random.uniform(0.001, 0.004),
                    arbitration_id=0x500 + (msg.frame_id & 0xFF),
                    is_extended_id=False,
                    is_fd=msg.is_fd,
                    bitrate_switch=msg.is_fd,
                    error_state_indicator=False,
                    dlc=len(gw_data),
                    data=bytes(gw_data),
                    channel=msg.gateway_to_channel,
                )
                writer.on_message_received(gw_msg)

            alive[msg.frame_id] = (alive[msg.frame_id] + 1) & 0xF

    return messages


# -----------------------------
# DBC schreiben
# -----------------------------

def write_dbc(path: Path, messages: List[MessageDef]) -> None:
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
        fd = ' CAN-FD' if msg.is_fd else ' Classic-CAN'
        lines.append(f'CM_ BO_ {msg.frame_id} "Cycle={msg.cycle_ms}ms; Channel=CAN{msg.channel};{fd};{gw}";')
        lines.append('')

    path.write_text('\n'.join(lines), encoding='utf-8')


# -----------------------------
# ASC optional als Debug
# -----------------------------

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


def main() -> None:
    parser = argparse.ArgumentParser(description="Realistischer CAN/CAN-FD BLF Generator")
    parser.add_argument("--out", default="realistic_can_trace.blf", help="Ausgabe-BLF")
    parser.add_argument("--dbc", default="realistic_can_network.dbc", help="Ausgabe-DBC")
    parser.add_argument("--duration", type=float, default=60.0, help="Trace-Laufzeit in Sekunden")
    parser.add_argument("--messages", type=int, default=100, help="Anzahl Botschaften")
    parser.add_argument("--seed", type=int, default=42, help="Zufalls-Seed")
    parser.add_argument("--classic-can", action="store_true", help="Classic CAN statt CAN-FD erzeugen")
    args = parser.parse_args()

    can_fd = not args.classic_can
    out_blf = Path(args.out).resolve()
    out_dbc = Path(args.dbc).resolve()

    messages = generate_blf(
        out_blf=out_blf,
        duration_s=args.duration,
        can_fd=can_fd,
        seed=args.seed,
        num_messages=args.messages,
    )
    write_dbc(out_dbc, messages)

    count, first, last = validate_blf(out_blf)

    print("Fertig.")
    print(f"BLF: {out_blf}")
    print(f"DBC: {out_dbc}")
    print(f"Frames: {count}")
    print(f"Zeitbereich: {first:.6f}s bis {last:.6f}s")
    print(f"Modus: {'CAN-FD' if can_fd else 'Classic CAN'}")
    print("Hinweis: Für 25 Signale pro Botschaft ist CAN-FD realistisch. Classic CAN begrenzt physisch auf 8 Byte.")


if __name__ == "__main__":
    main()
