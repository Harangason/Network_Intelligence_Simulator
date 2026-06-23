#!/usr/bin/env python3
"""Optional MDF/MF4 writer using asammdf when available."""

from __future__ import annotations

from pathlib import Path

from common_trace import build_can_trace, get_unsigned_le


def write_mdf(
    path: Path,
    version: str,
    duration: float,
    messages: int,
    channels: int,
    bus: str,
    seed: int,
    routing_rows=None,
) -> None:
    try:
        from asammdf import MDF, Signal
        import numpy as np
    except ImportError as exc:
        raise SystemExit(
            "MDF/MF4 export requires the optional package 'asammdf'. "
            "Install it in the Python environment used by this script, then rerun."
        ) from exc

    _message_defs, frames = build_can_trace(
        duration=duration,
        messages=messages,
        channels=channels,
        bus_type=bus,
        seed=seed,
        routing_rows=routing_rows,
    )
    if not frames:
        raise SystemExit("No frames generated.")

    start = frames[0].timestamp
    times = np.array([frame.timestamp - start for frame in frames], dtype=float)
    ids = np.array([frame.arbitration_id for frame in frames], dtype=np.uint32)
    ch = np.array([frame.channel for frame in frames], dtype=np.uint16)
    dlc = np.array([frame.dlc for frame in frames], dtype=np.uint8)
    crc_ok = np.array([1 if frame.data and frame.data[0] else 0 for frame in frames], dtype=np.uint8)
    alive = np.array([get_unsigned_le(frame.data, 8, 4) if len(frame.data) > 1 else 0 for frame in frames], dtype=np.uint8)

    mdf = MDF(version=version)
    mdf.append(
        [
            Signal(ids, times, name="CAN_ID", unit=""),
            Signal(ch, times, name="CAN_Channel", unit=""),
            Signal(dlc, times, name="CAN_DLC", unit="byte"),
            Signal(alive, times, name="AliveCounter", unit=""),
            Signal(crc_ok, times, name="CRC8_Present", unit=""),
        ],
        comment="Generated realistic CAN trace summary. Use DBC/BLF for full frame payload decoding.",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    mdf.save(path, overwrite=True)
