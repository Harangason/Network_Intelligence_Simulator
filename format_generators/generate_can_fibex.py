#!/usr/bin/env python3
from pathlib import Path

from can_cli import run_can_writer
from can_format_writers import write_fibex


def writer(path: Path, messages, frames, args) -> None:
    write_fibex(path, messages)


if __name__ == "__main__":
    run_can_writer("generated_can_system.fibex.xml", "Generate a FIBEX-style CAN system description", writer)
