#!/usr/bin/env python3
"""Shared CLI helpers for Ethernet format generator scripts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from backend.nis.communication.technologies.ethernet.formats.trace_model import build_ethernet_trace

Writer = Callable[[Path, list, argparse.Namespace], None]


def run_eth_writer(default_out: str, description: str, writer: Writer) -> None:
    parser = argparse.ArgumentParser(description=description)
    from backend.nis.infrastructure.paths import EXPORT_ROOT
    parser.add_argument("--out", default=str(EXPORT_ROOT / default_out), help="Output file")
    parser.add_argument("--duration", type=float, default=1.0, help="Trace duration in seconds")
    parser.add_argument("--messages", type=int, default=8, help="Number of Ethernet services/events")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()
    frames = build_ethernet_trace(duration=args.duration, messages=args.messages, seed=args.seed)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    writer(Path(args.out), frames, args)
    print(f"Wrote {args.out} with {len(frames)} Ethernet frames.")
