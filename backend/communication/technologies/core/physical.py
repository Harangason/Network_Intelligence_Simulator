"""Compatibility import; canonical owner: backend.nis.communication.core.physical."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('backend.nis.communication.core.physical')
