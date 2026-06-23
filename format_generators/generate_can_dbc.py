#!/usr/bin/env python3
from pathlib import Path

from can_cli import run_can_writer
from can_format_writers import write_dbc


def writer(path: Path, messages, frames, args) -> None:
    write_dbc(path, messages, nominal_bitrate=args.nominal_bitrate, data_bitrate=args.data_bitrate)


if __name__ == "__main__":
    run_can_writer("generated_can_network.dbc", "Generate a DBC database for the CAN trace model", writer)
