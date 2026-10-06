
# Direct file entrypoints resolve the installed/source package independently of cwd.
import sys as _cli_sys
from pathlib import Path as _CliPath
_cli_backend = next(p for p in _CliPath(__file__).resolve().parents if p.name == "backend")
_cli_sys.path.insert(0, str(_cli_backend.parent))
#!/usr/bin/env python3
from pathlib import Path

from backend.nis.communication.technologies.can.formats.can_cli import run_can_writer
from backend.nis.communication.technologies.can.formats.can_format_writers import write_arxml


def writer(path: Path, messages, frames, args) -> None:
    write_arxml(path, messages)


if __name__ == "__main__":
    run_can_writer("generated_can_system.arxml", "Generate an AUTOSAR ARXML-style CAN system description", writer)
