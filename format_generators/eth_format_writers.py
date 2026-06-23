#!/usr/bin/env python3
"""Writers for Ethernet oriented trace formats."""

from __future__ import annotations

import struct
from pathlib import Path

from common_trace import EthernetFrame, build_udp_ipv4_ethernet_packet


def pad4(data: bytes) -> bytes:
    return data + (b"\x00" * ((4 - len(data) % 4) % 4))


def write_pcap(path: Path, frames: list[EthernetFrame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        # Little-endian PCAP, Ethernet link type.
        handle.write(struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        for frame in frames:
            packet = build_udp_ipv4_ethernet_packet(frame)
            ts_sec = int(frame.timestamp)
            ts_usec = int((frame.timestamp - ts_sec) * 1_000_000)
            handle.write(struct.pack("<IIII", ts_sec, ts_usec, len(packet), len(packet)))
            handle.write(packet)


def pcapng_block(block_type: int, body: bytes) -> bytes:
    padded = pad4(body)
    total_len = 12 + len(padded)
    return struct.pack("<II", block_type, total_len) + padded + struct.pack("<I", total_len)


def write_pcapng(path: Path, frames: list[EthernetFrame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        # Section Header Block.
        shb_body = struct.pack("<IHHq", 0x1A2B3C4D, 1, 0, -1)
        handle.write(pcapng_block(0x0A0D0D0A, shb_body))
        # Interface Description Block: Ethernet, snaplen 65535.
        idb_body = struct.pack("<HHI", 1, 0, 65535)
        handle.write(pcapng_block(0x00000001, idb_body))
        # Enhanced Packet Blocks.
        for frame in frames:
            packet = build_udp_ipv4_ethernet_packet(frame)
            ts_us = int(frame.timestamp * 1_000_000)
            body = struct.pack("<IIIII", 0, ts_us >> 32, ts_us & 0xFFFFFFFF, len(packet), len(packet)) + packet
            handle.write(pcapng_block(0x00000006, body))
