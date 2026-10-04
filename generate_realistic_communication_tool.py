"""Canonical NIS launcher compatibility entrypoint."""
from pathlib import Path as _EntryPath
_entry = _EntryPath(__file__).parent / "scripts/dev/launch-networkis.py"
__file__ = str(_entry)
exec(compile(_entry.read_text(encoding="utf-8"), __file__, "exec"), globals(), globals())
