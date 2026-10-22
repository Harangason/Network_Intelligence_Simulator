"""Staging-only loader: exercise the pending patch in an isolated test process.

No repository application file is changed. This file is not delivered or copied
into backend/tests. The catalogue below reads the actual existing TS exports;
it substitutes only the not-yet-applied integration bridge during the freeze.
"""
import json
from pathlib import Path
import shutil
import subprocess

from backend.nis.agent.orchestration import project_intake
from backend.nis.agent.tools import wizard_generation
from backend.nis.communication import catalog as communication_catalog


ROOT = Path(__file__).resolve().parents[4]
STAGED = Path(__file__).parent / 'staged/backend/nis/agent/orchestration/project_intake.py'
exec(compile(STAGED.read_text(encoding='utf-8'), str(STAGED), 'exec'), project_intake.__dict__)
role_staged = Path(__file__).parent / 'qualification-stage/staged/backend/nis/communication/catalog.py'
if role_staged.is_file():
    # Replace the one owned pure function in the isolated process; a wholesale
    # module reload would break the catalog's canonical relative resource paths.
    import ast
    tree = ast.parse(role_staged.read_text(encoding='utf-8'))
    node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == 'parameter_value_role')
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(role_staged), 'exec'), communication_catalog.__dict__)


def _catalog_from_existing_exports(prompt):
    """Run the actual staged Node bridge, not a substitute catalog."""
    if not hasattr(_catalog_from_existing_exports, 'snapshots'):
        _catalog_from_existing_exports.snapshots = {}
    if prompt not in _catalog_from_existing_exports.snapshots:
        node = shutil.which('node') or 'C:/Program Files/nodejs/node.exe'
        out = Path(__file__).parent
        completed = subprocess.run([node, '--experimental-strip-types', '--import', (out / 'staged-loader.mjs').as_uri(),
                                   str(out / 'staged/frontend/scripts/extract-wizard-specification.mjs')],
                                   cwd=ROOT, check=False, capture_output=True, text=True, encoding='utf-8',
                                   input=json.dumps({'prompt': prompt, 'operation': 'reference-catalog'}))
        assert completed.returncode == 0, completed.stderr
        _catalog_from_existing_exports.snapshots[prompt] = json.loads(completed.stdout)
    return json.loads(json.dumps(_catalog_from_existing_exports.snapshots[prompt]))


wizard_generation.reference_design_catalog = _catalog_from_existing_exports
