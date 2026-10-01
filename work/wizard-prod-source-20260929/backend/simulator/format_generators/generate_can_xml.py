#!/usr/bin/env python3
from pathlib import Path

from can_cli import run_can_writer
from can_format_writers import write_xml_trace


def writer(path: Path, messages, frames, args) -> None:
    write_xml_trace(path, frames)


if __name__ == "__main__":
    run_can_writer("generated_can_trace.xml", "Generate a generic XML CAN trace", writer)
