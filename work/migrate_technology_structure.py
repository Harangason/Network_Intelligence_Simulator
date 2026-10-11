"""Stage/apply canonical technology ownership without changing profile semantics."""
import ast
import csv
import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/implementation-workloads/project-structure-migration-20261003'
STAGE = ROOT / 'work/structure-stage'
sys.path.insert(0, str(ROOT))
os.environ['NIS_DISABLE_GENERATED_TECHNOLOGIES'] = '1'

def module(path):
    parts = Path(path).with_suffix('').parts
    return '.'.join(parts[:-1] if parts[-1] == '__init__' else parts)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def main():
    command = sys.argv[1]
    if command == 'plan':
        old = importlib.import_module('backend.communication.technologies.catalog')
        from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY
        profiles = old.technology_definitions()
        (OUT / 'technology-definitions-before.json').write_text(json.dumps(profiles, indent=2), encoding='utf-8')
        (OUT / 'technology-registry-before.json').write_text(json.dumps(DEFAULT_TECHNOLOGY_REGISTRY.list_all(), indent=2), encoding='utf-8')
        mappings = {}
        source = ROOT / 'backend/communication'
        services = {'onboarding', 'sources', 'licensing', 'native_review_support'}
        for path in source.rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            rel = path.relative_to(source).as_posix()
            target = 'backend/nis/communication/' + rel
            if rel.startswith('technologies/core/'):
                target = 'backend/nis/communication/' + rel[len('technologies/'):]
                if rel == 'technologies/core/registry.py':
                    target = 'backend/nis/communication/registry.py'
            elif rel.startswith('technologies/') and '/' not in rel[len('technologies/'):]:
                if path.stem in services:
                    target = 'backend/nis/communication/services/' + path.name
                elif path.name == 'source_metadata.json':
                    target = 'backend/nis/communication/services/' + path.name
                elif path.stem == 'catalog':
                    target = 'backend/nis/communication/catalog.py'
                elif path.stem != '__init__' and path.suffix == '.py':
                    target = f'backend/nis/communication/technologies/{path.stem}/rules.py'
            mappings[path.relative_to(ROOT).as_posix()] = target
        # The singleton is assembled at communication root, not in technology folders.
        mappings['backend/communication/technologies/__init__.py'] = 'backend/nis/communication/__init__.py'
        mappings.pop('backend/communication/__init__.py', None)
        aliases = {module(s): module(t) for s, t in mappings.items() if s.endswith('.py')}
        aliases['backend.communication'] = 'backend.nis.communication'
        aliases['backend.communication.technologies.core'] = 'backend.nis.communication.core'
        # Technology module public paths now point to each package's rules implementation.
        def remap(value):
            for prefix in sorted(aliases, key=len, reverse=True):
                if value == prefix or value.startswith(prefix + '.'):
                    return aliases[prefix] + value[len(prefix):]
            return value
        inventory = json.loads((OUT / 'inventory-before.json').read_text(encoding='utf-8'))
        candidates = [ROOT / r['path'] for r in inventory['files'] if r['path'].endswith('.py')
                      and (r['path'].startswith(('backend/', 'scripts/'))
                           or r['path'] == 'generate_realistic_communication_tool.py')
                      and not r['path'].startswith('backend/backend/')]
        writes = {}
        def stage(relative, data):
            writes[relative] = data.encode('utf-8') if isinstance(data, str) else data
        for relative, target in mappings.items():
            if not relative.endswith('.py'):
                stage(target, (ROOT / relative).read_bytes())
        for path in candidates:
            rel = path.relative_to(ROOT).as_posix()
            text = path.read_text(encoding='utf-8-sig')
            if rel == 'backend/communication/technologies/catalog.py':
                continue
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            lines = text.splitlines(keepends=True)
            edits = []
            package = module(rel) if path.name == '__init__.py' else module(rel).rsplit('.', 1)[0]
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level:
                    prefix = package.split('.')[:len(package.split('.')) - node.level + 1]
                    resolved = '.'.join(prefix + ([node.module] if node.module else []))
                    if not resolved.startswith('backend.'):
                        continue
                    names = ', '.join(a.name + (' as ' + a.asname if a.asname else '') for a in node.names)
                    # Packages importing a moved child need the child's exact new owner.
                    child_moved = len(node.names) == 1 and resolved + '.' + node.names[0].name in aliases
                    if child_moved:
                        child = remap(resolved + '.' + node.names[0].name)
                        parent, leaf = child.rsplit('.', 1)
                        name = node.names[0]
                        replacement = f'from {parent} import {leaf} as {name.asname or name.name}'
                    else:
                        replacement = f'from {remap(resolved)} import {names}'
                    # Preserve compound line content and comments around the import.
                    start = sum(len(x) for x in lines[:node.lineno - 1]) + node.col_offset
                    end = sum(len(x) for x in lines[:node.end_lineno - 1]) + node.end_col_offset
                    edits.append((start, end, replacement))
            for start, end, replacement in sorted(edits, reverse=True):
                text = text[:start] + replacement + text[end:]
            # Absolute imports and module provenance string literals follow the same mapping.
            import re
            pattern = re.compile(r'backend\.communication(?:\.[A-Za-z_][A-Za-z_0-9]*)*')
            text = pattern.sub(lambda m: remap(m.group()), text)
            target = mappings.get(rel, rel)
            if rel == 'backend/communication/technologies/onboarding.py':
                text = text.replace('return Path(__file__).resolve().parents[3] / "technologies" / "generated"',
                    'from backend.app.config import PROJECT_ROOT\n    return PROJECT_ROOT / "technologies" / "generated"')
            if rel == 'backend/communication/technologies/core/__init__.py':
                text = text.replace('from backend.nis.communication.registry import BindingResolver, GeneratorResolver, TechnologyRegistry', '')
                text += '\ndef __getattr__(name):\n    if name in ("BindingResolver", "GeneratorResolver", "TechnologyRegistry"):\n        from backend.nis.communication import registry\n        return getattr(registry, name)\n    raise AttributeError(name)\n'
            if target != rel or text != path.read_text(encoding='utf-8-sig'):
                stage(target, text)
            if target != rel and path.suffix == '.py':
                stage(rel, f'"""Compatibility import; canonical owner: {module(target)}."""\n'
                      f'import importlib as _importlib\nimport sys as _sys\n'
                      f'_sys.modules[__name__] = _importlib.import_module({module(target)!r})\n')
            elif target != rel:
                stage(target, path.read_bytes())
        # Replace technical catalog content with registered package-owned definitions.
        public_constants = ('CAN_FD_DATA_LENGTHS', 'DDS_POLICY_ENTITIES', 'DIRECT_IO_TECHNOLOGIES',
                            'LOCAL_EVIDENCE_FIELDS', 'REVIEW_RATE_PROPOSALS', 'PARAMETER_UI_ALIASES',
                            'PARAMETER_CORE_ALIASES', 'RESERVED_PARAMETER_NAMES')
        import pprint
        catalog = '"""Projection over canonical package-owned technology definitions."""\nfrom copy import deepcopy\nfrom typing import Any\nfrom importlib import import_module\n'
        for name in public_constants:
            catalog += f'{name} = {pprint.pformat(getattr(old, name), width=110, sort_dicts=False)}\n'
        catalog += '\nTECHNOLOGY_IDS = ' + repr(tuple(p['id'] for p in profiles)) + '\n'
        catalog += '''\ndef technology_definitions():
    return [deepcopy(import_module(f"backend.nis.communication.technologies.{key}.definition").PROFILE)
            for key in TECHNOLOGY_IDS]
'''
        oldtree = ast.parse(Path(old.__file__).read_text(encoding='utf-8'))
        review = next(n for n in oldtree.body if isinstance(n, ast.FunctionDef) and n.name == '_parameter_defaults_review')
        catalog += '\n' + ast.get_source_segment(Path(old.__file__).read_text(encoding='utf-8'), review) + '\n'
        stage('backend/nis/communication/catalog.py', catalog)
        stage('backend/communication/technologies/catalog.py', '"""Compatibility projection; no technical definitions."""\nimport sys\nfrom backend.nis.communication import catalog\nsys.modules[__name__] = catalog\n')
        # Industry model choices are templates, independent from transport profile ownership.
        stage('backend/nis/industries/models.py', '"""Industry template choices; reference technology identities only."""\nMODEL_TYPES = ' + pprint.pformat(old.MODEL_TYPES, width=110) + '\n')
        catalog += '\nfrom backend.nis.industries.models import MODEL_TYPES\n'
        stage('backend/nis/communication/catalog.py', catalog)
        for profile in profiles:
            key = profile['id']
            stage(f'backend/nis/communication/technologies/{key}/definition.py',
                  f'"""Canonical {key} profile: preserved verified parameters and capabilities."""\n'
                  'import json\nfrom pathlib import Path\n'
                  "PROFILE = json.loads(Path(__file__).with_name('profile.json').read_text(encoding='utf-8'))\n")
            stage(f'backend/nis/communication/technologies/{key}/profile.json', json.dumps(profile, indent=2, ensure_ascii=False) + '\n')
            stage(f'backend/nis/communication/technologies/{key}/__init__.py',
                  f'"""{key} technology package; unsupported capabilities remain explicit."""\n')
        for folder in ('backend/nis/communication/services', 'backend/nis/communication/technologies', 'backend/nis/industries'):
            stage(folder + '/__init__.py', '"""Canonical NIS responsibility package."""\n')
        stage('backend/nis/compatibility.json', json.dumps(aliases, indent=2) + '\n')
        stage('backend/nis/compatibility.py', '''"""Finite legacy module aliases; no duplicate execution or registration.

Remove an alias after all supported CLI, persisted-module and external consumers
have migrated. Canonical internal code imports backend.nis directly.
"""
import importlib
import importlib.abc
import importlib.util
import json
import sys
from pathlib import Path

ALIASES = json.loads(Path(__file__).with_name('compatibility.json').read_text(encoding='utf-8'))

class AliasLoader(importlib.abc.Loader):
    def __init__(self, target):
        self.target = target
    def create_module(self, spec):
        return importlib.import_module(self.target)
    def exec_module(self, module):
        pass

class LegacyImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        canonical = ALIASES.get(fullname)
        if canonical is None:
            return None
        actual = importlib.util.find_spec(canonical)
        return importlib.util.spec_from_loader(fullname, AliasLoader(canonical),
                                              is_package=actual.submodule_search_locations is not None)

def install():
    if not any(isinstance(finder, LegacyImports) for finder in sys.meta_path):
        sys.meta_path.insert(0, LegacyImports())
''')
        stage('backend/__init__.py', '"""Network Simulator backend; finite legacy import compatibility."""\n'
              'from .nis.compatibility import install\ninstall()\n')
        manifest_path = 'scripts/write-build-info.py'
        manifest = writes.get(manifest_path, (ROOT / manifest_path).read_bytes()).decode('utf-8')
        manifest = manifest.replace('root.joinpath("backend/communication/technologies").rglob("*.json")',
                                    'root.joinpath("backend/nis").rglob("*.json")')
        stage(manifest_path, manifest)
        identity_tests = 'scripts/tests/test_release_identity.py'
        identity = writes.get(identity_tests, (ROOT / identity_tests).read_bytes()).decode('utf-8')
        identity = identity.replace('backend/communication/technologies/source_metadata.json',
                                    'backend/nis/communication/services/source_metadata.json')
        stage(identity_tests, identity)
        # Import namespace must remain cheap: catalog inspection is explicitly requested.
        stage('backend/nis/__init__.py', '"""Canonical Network Simulator application namespace."""\n'
              'def __getattr__(name):\n    if name in ("CAPABILITIES", "architecture_catalog"):\n'
              '        from . import catalog\n        return getattr(catalog, name)\n    raise AttributeError(name)\n')
        for relative, data in writes.items():
            if relative.endswith('.py'):
                compile(data.decode('utf-8'), relative, 'exec')
            target = STAGE / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        plan = {'writes': {r: digest(data) for r, data in writes.items()}, 'mappings': mappings}
        (OUT / 'technology-migration-plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
        work = json.loads((OUT / 'workload.json').read_text())
        work['revision_before'] = {r: digest((ROOT / r).read_bytes()) if (ROOT / r).is_file() else None for r in writes}
        work['completion_status'] = 'PLANNING'
        (OUT / 'workload.json').write_text(json.dumps(work, indent=2), encoding='utf-8')
        print(json.dumps({'writes': len(writes), 'profiles': len(profiles), 'moved_files': len(mappings)}))
    elif command == 'apply':
        plan = json.loads((OUT / 'technology-migration-plan.json').read_text())
        guard = ROOT.parent  # guard is read-only and external to the project.
        check = subprocess.run([sys.executable, 'F:/CodexOrdner/skills/lokaler-implementierungs-agent/scripts/implementation_guard.py',
                                'before-apply', '--workload', str(OUT / 'workload.json')], check=True)
        backup = OUT / 'before/technology'
        for relative, expected in plan['writes'].items():
            staged = STAGE / relative
            if digest(staged.read_bytes()) != expected:
                raise ValueError('Staging changed: ' + relative)
            target = (ROOT / relative).resolve()
            if not target.is_relative_to(ROOT):
                raise ValueError('Outside workspace: ' + relative)
            if target.is_file():
                saved = backup / relative
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staged, target)
        work = json.loads((OUT / 'workload.json').read_text())
        work['completion_status'] = 'IMPLEMENTING'
        work['files_changed'] = list(plan['writes'])
        (OUT / 'workload.json').write_text(json.dumps(work, indent=2), encoding='utf-8')
        print(json.dumps({'applied': len(plan['writes']), 'backup': str(backup)}))
    else:
        raise SystemExit('plan or apply required')

if __name__ == '__main__':
    main()
