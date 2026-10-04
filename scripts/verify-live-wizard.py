"""Compatibility entrypoint; implementation is in the responsibility folder."""
from pathlib import Path as _CompatPath
_compat_target = _CompatPath(__file__).parent / 'verification' / 'verify-live-wizard.py'
__file__ = str(_compat_target)
exec(compile(_compat_target.read_text(encoding="utf-8"), __file__, "exec"), globals(), globals())
