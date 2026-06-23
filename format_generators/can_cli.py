#!/usr/bin/env python3
"""Shared CLI helpers for CAN format generator scripts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from common_trace import MessageDef, build_can_trace, load_routing_table, write_routing_template

Writer = Callable[[Path, list[MessageDef], list, argparse.Namespace], None]


def add_can_args(parser: argparse.ArgumentParser, default_out: str) -> None:
    parser.add_argument("--out", default=default_out, help="Output file")
    parser.add_argument("--duration", type=float, default=1.0, help="Trace duration in seconds")
    parser.add_argument("--messages", type=int, default=10, help="Number of data messages")
    parser.add_argument("--channels", type=int, choices=range(1, 17), default=2, metavar="1-16", help="CAN channels, CAN0..CAN15")
    parser.add_argument("--routing-table", type=Path, default=None, help="CSV routing table with sender,receiver,cycle_ms,channel,gateway_to_channel,frame_id,name")
    parser.add_argument("--write-routing-template", type=Path, default=None, help="Write a routing-table CSV template and exit")
    parser.add_argument("--bus", choices=["classic", "fd", "xl"], default="fd", help="Bus profile")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--nominal-bitrate", type=int, default=500_000, help="Nominal/arbitration bitrate")
    parser.add_argument("--data-bitrate", type=int, default=500_000, help="FD/XL data phase bitrate")


def run_can_writer(default_out: str, description: str, writer: Writer) -> None:
    parser = argparse.ArgumentParser(description=description)
    add_can_args(parser, default_out)
    args = parser.parse_args()
    if args.write_routing_template:
        write_routing_template(args.write_routing_template)
        print(f"Wrote routing template to {args.write_routing_template}")
        return
    routing_rows = load_routing_table(args.routing_table, args.channels) if args.routing_table else None
    messages_count = len(routing_rows) if routing_rows is not None and args.messages == 10 else args.messages
    messages, frames = build_can_trace(
        duration=args.duration,
        messages=messages_count,
        channels=args.channels,
        bus_type=args.bus,
        seed=args.seed,
        routing_rows=routing_rows,
    )
    writer(Path(args.out), messages, frames, args)
    print(f"Wrote {args.out} with {len(frames)} frames on {args.channels} channel(s).")
