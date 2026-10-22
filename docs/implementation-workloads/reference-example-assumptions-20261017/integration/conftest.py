"""Test-process-only source overlay; SQL still uses the disposable launcher.

This staging test intentionally does not prove applied production code, native
Qwen, registry registration, or an actual original-document simulation.
"""
from pathlib import Path
import importlib.util
import sys

pytest_plugins = ['backend.tests.conftest']

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]

# The peer's staging loader supplies the real exported TS measurement catalog
# for the bridge that cannot yet be applied during the previous source freeze.
peer = HERE.parent / 'root/conftest.py'
exec(compile(peer.read_text(encoding='utf-8'), str(peer), 'exec'), {'__file__': str(peer)})

for package, relative in [
    ('backend.nis.agent.orchestration.local_reasoner', 'backend/nis/agent/orchestration/local_reasoner.py'),
    ('backend.nis.agent.tools.project_draft', 'backend/nis/agent/tools/project_draft.py'),
    ('backend.nis.agent.tools.structured_project_draft', 'backend/nis/agent/tools/structured_project_draft.py'),
]:
    module = __import__(package, fromlist=['_'])
    path = HERE / 'staged' / relative
    exec(compile(path.read_text(encoding='utf-8'), str(path), 'exec'), module.__dict__)

fixture_path = HERE.parent / 'root/staged/backend/tests/test_reference_design.py'
spec = importlib.util.spec_from_file_location('backend.tests.test_reference_design', fixture_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
