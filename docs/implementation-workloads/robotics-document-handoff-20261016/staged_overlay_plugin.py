"""Preparation-only test overlay; release tests always run canonical files."""
from pathlib import Path
import importlib.util
import sys

BASE = Path(__file__).parent / 'staged'
for relative in (
    'backend/nis/agent/context/limits.py',
    'backend/nis/agent/orchestration/project_intake.py',
    'backend/nis/agent/tools/run_status.py',
    'backend/nis/agent/tools/wizard_generation.py',
    'backend/nis/agent/tools/api.py',
):
    name = relative[:-3].replace('/', '.')
    spec = importlib.util.spec_from_file_location(name, BASE / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    parent, attribute = name.rsplit('.', 1)
    if parent in sys.modules:
        setattr(sys.modules[parent], attribute, module)
