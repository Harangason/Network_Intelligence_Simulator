#!/usr/bin/env python3
from pathlib import Path

from can_cli import run_can_writer
from can_format_writers import write_arxml


def writer(path: Path, messages, frames, args) -> None:
    write_arxml(path, messages)


if __name__ == "__main__":
    run_can_writer("generated_can_system.arxml", "Generate an AUTOSAR ARXML-style CAN system description", writer)
