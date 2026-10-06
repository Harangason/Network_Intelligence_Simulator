
# Direct file entrypoints resolve the installed/source package independently of cwd.
import sys as _cli_sys
from pathlib import Path as _CliPath
_cli_backend = next(p for p in _CliPath(__file__).resolve().parents if p.name == "backend")
_cli_sys.path.insert(0, str(_cli_backend.parent))
#!/usr/bin/env python3
from pathlib import Path

from backend.nis.communication.technologies.ethernet.formats.eth_cli import run_eth_writer
from backend.nis.communication.technologies.ethernet.formats.eth_format_writers import write_pcap


def writer(path: Path, frames, args) -> None:
    write_pcap(path, frames)


if __name__ == "__main__":
    run_eth_writer("generated_someip_trace.pcap", "Generate Ethernet/IP/UDP/SOME-IP PCAP", writer)
