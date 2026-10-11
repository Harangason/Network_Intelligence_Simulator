"""Move historical export presets to technology owners, preserving old API data."""
import ast
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.nis.industries.legacy_projection.registry import TechnologyRegistry

writes = {}
registry = TechnologyRegistry()
for generator in registry.generators:
    entries = generator.generate()
    module = sys.modules[type(generator).__module__]
    relative = Path(module.__file__).relative_to(ROOT).as_posix()
    text = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(text)
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "generate")
    lines = text.splitlines(keepends=True)
    replacement = ('    def generate(self) -> dict[str, TechnologyProfile]:\n'
                   '        from backend.nis.industries.legacy_projection.generator_base import legacy_profiles\n'
                   f'        return legacy_profiles({tuple(entries)!r})\n')
    writes[relative] = ''.join(lines[:method.lineno - 1]) + replacement + ''.join(lines[method.end_lineno:])
    for key, profile in entries.items():
        target = f"backend/nis/communication/technologies/{key}/legacy_export_preset.json"
        writes[target] = json.dumps({"purpose": "Historical export API preset; not a validated project default",
                                    "legacy_id": key, "profile": profile.to_dict()}, indent=2) + '\n'
path = ROOT / 'docs/implementation-workloads/project-structure-migration-20261003/industry-projection-plan.json'
path.write_text(json.dumps({'writes': writes}, indent=2), encoding='utf-8')
subprocess.run([sys.executable, str(ROOT / 'work/structure_guard.py'), '--plan', str(path)], check=True)
for relative, content in writes.items():
    target = ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding='utf-8')
print(json.dumps({'technology_presets': len(registry.builtin), 'industry_consumers': len(registry.generators)}))
