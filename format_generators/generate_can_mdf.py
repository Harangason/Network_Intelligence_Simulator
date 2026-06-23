#!/usr/bin/env python3
import argparse
from pathlib import Path

from mdf_writer import write_mdf


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ASAM MDF 3.x summary from the CAN trace model")
    parser.add_argument("--out", default="generated_can_summary.mdf")
    parser.add_argument("--duration", type=float, default=1.0)
    parser.add_argument("--messages", type=int, default=10)
    parser.add_argument("--channels", type=int, choices=range(1, 17), default=2, metavar="1-16")
    parser.add_argument("--bus", choices=["classic", "fd", "xl"], default="fd")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    write_mdf(Path(args.out), "3.30", args.duration, args.messages, args.channels, args.bus, args.seed)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
