#!/usr/bin/env python3
from pathlib import Path

from eth_cli import run_eth_writer
from eth_format_writers import write_pcap


def writer(path: Path, frames, args) -> None:
    write_pcap(path, frames)


if __name__ == "__main__":
    run_eth_writer("generated_someip_trace.pcap", "Generate Ethernet/IP/UDP/SOME-IP PCAP", writer)
