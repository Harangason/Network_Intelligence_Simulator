#!/usr/bin/env python3
"""Wrapper around the main communication generator in the project root."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generate_realistic_communication_tool import generate_blf, load_routing_table, write_dbc, write_routing_template  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate BLF + DBC using the main CAN/CAN-FD/CAN-XL profile generator")
    parser.add_argument("--out", default="generated_can_trace.blf")
    parser.add_argument("--dbc", default="generated_can_network.dbc")
    parser.add_argument("--duration", type=float, default=1.0)
    parser.add_argument("--messages", type=int, default=10)
    parser.add_argument("--channels", type=int, choices=range(1, 17), default=2, metavar="1-16")
    parser.add_argument("--routing-table", type=Path, default=None)
    parser.add_argument("--write-routing-template", type=Path, default=None)
    parser.add_argument("--bus", choices=["classic", "fd", "xl"], default="fd")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--nominal-bitrate", type=int, default=500_000)
    parser.add_argument("--data-bitrate", type=int, default=500_000)
    args = parser.parse_args()
    if args.write_routing_template:
        write_routing_template(args.write_routing_template)
        print(f"Wrote routing template to {args.write_routing_template}")
        return

    routing_rows = load_routing_table(args.routing_table, args.channels) if args.routing_table else None
    message_count = len(routing_rows) if routing_rows is not None and args.messages == 10 else args.messages

    messages = generate_blf(
        out_blf=Path(args.out),
        duration_s=args.duration,
        bus_type=args.bus,
        seed=args.seed,
        num_messages=message_count,
        nominal_bitrate=args.nominal_bitrate,
        data_bitrate=args.data_bitrate,
        channel_count=args.channels,
        routing_rows=routing_rows,
    )
    write_dbc(Path(args.dbc), messages, nominal_bitrate=args.nominal_bitrate, data_bitrate=args.data_bitrate)
    print(f"Wrote {args.out} and {args.dbc}")


if __name__ == "__main__":
    main()
