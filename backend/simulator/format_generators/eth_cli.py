#!/usr/bin/env python3
"""Shared CLI helpers for Ethernet format generator scripts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from common_trace import build_ethernet_trace

Writer = Callable[[Path, list, argparse.Namespace], None]


def run_eth_writer(default_out: str, description: str, writer: Writer) -> None:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--out", default=default_out, help="Output file")
    parser.add_argument("--duration", type=float, default=1.0, help="Trace duration in seconds")
    parser.add_argument("--messages", type=int, default=8, help="Number of Ethernet services/events")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()
    frames = build_ethernet_trace(duration=args.duration, messages=args.messages, seed=args.seed)
    writer(Path(args.out), frames, args)
    print(f"Wrote {args.out} with {len(frames)} Ethernet frames.")
