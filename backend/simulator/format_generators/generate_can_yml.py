"""Compatibility entrypoint; owner backend.nis.communication.technologies.can.formats.generate_can_yml."""
import importlib
import sys
from pathlib import Path
sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if p.name == "backend").parent))
if __name__ == "__main__":
    import runpy
    runpy.run_module('backend.nis.communication.technologies.can.formats.generate_can_yml', run_name="__main__")
else:
    sys.modules[__name__] = importlib.import_module('backend.nis.communication.technologies.can.formats.generate_can_yml')
