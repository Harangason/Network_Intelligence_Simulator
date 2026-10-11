from finish_structure_owners import *

mapping_script = r'''"""Reconcile structure transitions with current import and entry-point references.

Only repository consumers are observable. An empty list is never permission
to remove an externally published or persisted legacy path.
"""
import ast
import csv
import io
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXCLUDED = ('/.venv/', '/node_modules/', '/test-output/', '/runtime/', '/build/',
            '/before/', '/archive/', '/archives/', '/__pycache__/', '/.next/',
            '/project-scanner/', '/implementation-workloads/')

def inventory(root=ROOT):
    result = subprocess.run(['rg', '--files', '--hidden', 'backend', 'frontend/src', 'scripts', 'docs'],
                            cwd=root, check=True, text=True, capture_output=True)
    return sorted(path.replace('\\', '/') for path in result.stdout.splitlines()
                  if not any(part in '/' + path.replace('\\', '/') for part in EXCLUDED)
                  and Path(path).suffix in {'.py', '.ts', '.tsx', '.mjs', '.json', '.md', '.ps1', '.sh', '.yml', '.yaml'})

def module_name(path):
    if not path.endswith('.py'): return None
    return path[:-3].replace('/', '.').removesuffix('.__init__')

def consumers(root, paths):
    modules = {module_name(p): p for p in paths if p.endswith('.py')}
    # Bare backend ingress names are supported compatibility paths too.
    modules.update({key.removeprefix('backend.'): value for key,value in list(modules.items()) if key.startswith('backend.')})
    reverse = defaultdict(set)
    pathset = set(paths)
    def edge(target, consumer):
        if target in pathset and target != consumer: reverse[target].add(consumer)
    def imported(name, consumer):
        while name:
            if name in modules:
                edge(modules[name], consumer)
                return
            name = name.rpartition('.')[0]
    for path in paths:
        text = (root / path).read_text(encoding='utf-8-sig', errors='replace')
        if path.endswith('.py'):
            try: tree = ast.parse(text)
            except SyntaxError: continue
            package = module_name(path) if path.endswith('/__init__.py') else module_name(path).rpartition('.')[0]
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names: imported(alias.name, path)
                elif isinstance(node, ast.ImportFrom):
                    base = node.module or ''
                    if node.level:
                        prefix = package.split('.')[:len(package.split('.')) - node.level + 1]
                        base = '.'.join([*prefix, base]).strip('.')
                    imported(base, path)
                    for alias in node.names: imported(base + '.' + alias.name, path)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if node.value in modules: imported(node.value, path)
        if path.startswith('frontend/src/'):
            for match in re.finditer(r'(?:from\s*|import\s*\()\s*[\'\"]([^\'\"]+)', text):
                value = match.group(1)
                if value.startswith('@/'): base = root / 'frontend/src' / value[2:]
                elif value.startswith('.'): base = root / Path(path).parent / value
                else: continue
                for suffix in ['', '.ts', '.tsx', '.mjs', '.json', '/index.ts', '/index.tsx']:
                    candidate = Path(str(base) + suffix).resolve()
                    if candidate.is_relative_to(root): edge(candidate.relative_to(root).as_posix(), path)
        for match in re.finditer(r'[A-Za-z0-9_@.\-]+(?:[/\\][A-Za-z0-9_@.\[\]\-]+)+\.(?:py|tsx?|mjs|json|md|ps1|sh)', text):
            value = match.group().replace('\\', '/')
            edge(value, path)
            candidate = (root / Path(path).parent / value).resolve()
            if candidate.is_relative_to(root): edge(candidate.relative_to(root).as_posix(), path)
    return reverse

def reconcile(root=ROOT):
    mapping = root / 'docs/migrations/structure_mapping.csv'
    existing = list(csv.DictReader(mapping.read_text(encoding='utf-8-sig').splitlines()))
    paths = inventory(root)
    reverse = consumers(root, paths)
    accounted = {row['source_path'] for row in existing} | {row['target_path'] for row in existing}
    for path in paths:
        if path not in accounted:
            existing.append(dict(source_path=path, target_path=path, action='canonical-owner' if '/nis/' in path or '/features/' in path else 'unchanged'))
    for row in existing:
        source, target = row['source_path'], row['target_path']
        refs = sorted(reverse.get(source, set()))
        owner = module_name(target) or str(Path(target).parent).replace('\\', '/')
        row['responsibility'] = 'Canonical module owner: ' + owner
        row['owner'] = owner
        row['consumers'] = json.dumps(refs, ensure_ascii=False)
        row['canonical_consumers'] = json.dumps(sorted(reverse.get(target, set())), ensure_ascii=False)
        row['consumer_scan'] = 'Python AST (including relative and literal dynamic imports), TypeScript imports, literal paths and documentation links; external/persisted consumers not observable'
        row['data_impact'] = row.get('data_impact') or 'No schema or stored identity change'
        row['verification'] = 'backend/tests/test_structure_architecture.py; backend/tests/test_structure_completion.py; full release receipt linked in completion report'
        row['status'] = 'RETAINED_COMPATIBLE' if row['action'] == 'move-with-forwarding-entry' else 'CANONICAL_PRESENT' if (root / target).is_file() else 'HISTORICAL_REFERENCE'
        row['removal_criterion'] = (f'Owner {owner} must migrate repository consumers {json.dumps(refs)}; inventory persisted module/CLI references and supported external callers for {source}; prove alias/import and behavior regressions plus full release PASS before removal. No retirement deadline authorized.'
                                    if row['action'] == 'move-with-forwarding-entry' else 'Not a removable compatibility wrapper')
    fields = ['source_path','target_path','action','responsibility','consumers','data_impact','verification','status',
              'owner','canonical_consumers','consumer_scan','removal_criterion']
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows(sorted(existing, key=lambda row: (row['source_path'], row['target_path'])))
    return output.getvalue()

if __name__ == '__main__':
    (ROOT / 'docs/migrations/structure_mapping.csv').write_text(reconcile(), encoding='utf-8', newline='\n')
'''
write('scripts/migrations/structure_mapping.py', mapping_script)

tests = '''"""Regression guards for the completed migration responsibilities."""
import ast
import csv
import importlib.util
import json
from pathlib import Path
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
from backend.nis.communication.core.physical import validate_physical_realization

ROOT = Path(__file__).resolve().parents[2]

def load_script(relative):
    spec = importlib.util.spec_from_file_location('structure_' + Path(relative).stem.replace('-', '_'), ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def technology_branches(source):
    """Detect concrete protocol comparisons inside generic timing services."""
    names = {'CAN', 'CAN_CLASSIC', 'CAN_FD', 'CANFD', 'LIN', 'ETHERNET', 'I2C', 'SPI'}
    return [node.lineno for node in ast.walk(ast.parse(source)) if isinstance(node, (ast.If, ast.IfExp))
            and any(isinstance(value, ast.Constant) and value.value in names for value in ast.walk(node.test))]

def test_timing_dispatch_has_no_concrete_protocol_rules():
    for path in ['backend/nis/engineering/capacity/calculators.py', 'backend/nis/communication/core/components.py']:
        source = (ROOT / path).read_text(encoding='utf-8')
        tree = ast.parse(source)
        scope = next((node for node in tree.body if getattr(node, 'name', '') == 'TechnologyTimingModel'), None)
        assert not technology_branches(ast.unparse(scope) if scope else source), path
        assert not any(isinstance(node, ast.ImportFrom) and (node.module or '').startswith('backend.nis.engineering')
                       for node in ast.walk(scope or tree)), path
    # Prove the guard detects the former misplaced rule and a new inline default.
    assert technology_branches("if protocol == 'CAN_FD':\\n    bits = 64 * 8")
    assert technology_branches("limit = 8 if protocol == 'LIN' else None")

def test_runtime_arbitration_and_phy_rules_have_technology_owners():
    scheduler = (ROOT / 'backend/nis/simulation/runtime/event_scheduler.py').read_text()
    assert 'can_id' not in scheduler
    physical = (ROOT / 'backend/nis/communication/core/physical.py').read_text()
    assert not technology_branches(physical)
    assert '100BASE_TX' not in physical and 'RS485_2W' not in physical
    for key in ['can', 'can_fd', 'ethernet', 'lin', 'i2c', 'spi']:
        implementation = DEFAULT_TECHNOLOGY_REGISTRY.timing_implementation(key)
        assert implementation.__name__ == f'backend.nis.communication.technologies.{key}.timing'

def test_frontend_technology_data_is_exact_backend_projection():
    generator = load_script('scripts/build/project-vocabulary.py')
    actual = json.loads((ROOT / 'frontend/src/features/communication/lib/technology-projection.json').read_text(encoding='utf-8'))
    assert actual == generator.technology_projection(ROOT)
    assert {profile['id'] for profile in actual['technologies']} == {p['id'] for p in DEFAULT_TECHNOLOGY_REGISTRY.profiles()}

def test_mapping_covers_current_application_and_every_transition():
    mapping = load_script('scripts/migrations/structure_mapping.py')
    rows = list(csv.DictReader((ROOT / 'docs/migrations/structure_mapping.csv').read_text(encoding='utf-8').splitlines()))
    covered = {r['source_path'] for r in rows} | {r['target_path'] for r in rows}
    assert set(mapping.inventory()) <= covered
    for row in rows:
        assert row['owner'] and isinstance(json.loads(row['consumers']), list)
        if row['action'] == 'move-with-forwarding-entry':
            assert row['source_path'] in row['removal_criterion']
            assert row['owner'] in row['removal_criterion']
            assert (ROOT / row['target_path']).is_file()
    for path in ['scripts/build/project-vocabulary.py', 'scripts/tests/test_release_frontend_discovery.py',
                 'frontend/src/app/api/simulations/[id]/artifacts/[format]/route.ts']:
        assert path in covered

def test_technology_entry_documents_match_actual_capabilities():
    for profile in DEFAULT_TECHNOLOGY_REGISTRY.profiles():
        document = ROOT / 'backend/nis/communication/technologies' / profile['id'] / 'README.md'
        text = document.read_text(encoding='utf-8')
        assert profile['id'] in text and profile['implementation_status'] in text
        assert 'profile.json' in text and 'Tests' in text
'''
write('backend/tests/test_structure_completion.py', tests)

techroot = ROOT / 'backend/nis/communication/technologies'
for profile_path in sorted(techroot.glob('*/profile.json')):
    profile = json.loads(profile_path.read_text(encoding='utf-8'))
    key = profile['id']
    files = [p.name for p in profile_path.parent.glob('*.py') if p.name not in {'__init__.py', 'definition.py'}]
    formats = [p.stem.removeprefix('generate_') for p in (profile_path.parent / 'formats').glob('generate_*.py')]
    test_map = {'can': ['test_can_dispatcher.py', 'test_capacity_can_schedule.py'], 'can_fd': ['test_capacity_can_schedule.py', 'test_technology_standard_defaults.py'],
                'ethernet': ['test_ethernet_fifo_schedule.py'], 'lin': ['test_lin_schedule.py', 'test_lin_analysis_implementation.py'],
                'i2c': ['test_serial_parameter_validity.py'], 'spi': ['test_serial_parameter_validity.py'],
                'flexray': ['test_unverified_technology_capacity.py']}
    tests_for_key = test_map.get(key, ['test_technology_registry_metadata.py', 'test_technology_standard_defaults.py'])
    capability = profile.get('capacity_evidence') or {}
    text = f'''# {profile['label']} (`{key}`)

## Verantwortung und Vertrag

`profile.json` ist die maßgebliche Definition für Identität, Varianten, Parameter,
Ratenmodell und Fähigkeiten; `definition.py` lädt sie. Die zentrale Registry
registriert dieses Profil genau einmal. `implementation_status`: **{profile['implementation_status']}**.
Kapazitätsnachweis laut Profil: **{capability.get('status', 'nicht angegeben')}**.
Ein Profil, Export oder ein Bitratenvorschlag ist kein funktionaler Timingnachweis.
Fehlende Modelle bleiben ausdrücklich unverifiziert; fremde Technologien werden
nicht als Ersatz verwendet.

## Öffentliche Schnittstellen

```python
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
profile = DEFAULT_TECHNOLOGY_REGISTRY.profile("{key}")
review = DEFAULT_TECHNOLOGY_REGISTRY.parameter_defaults_review("{key}")
```

Direkte Implementierungen: {', '.join('`' + name + '`' for name in sorted(files)) or 'keine zusätzlichen ausführbaren Technologiealgorithmen'}.
Native Formatadapter: {', '.join('`' + name + '`' for name in sorted(formats)) or 'keine Adapter in diesem Paket'}.
`identity.json`, `review.json` und `physical.json` sind optionale, technologieeigene
Ergänzungen. Generische Timing-, PHY- und Simulationseinstiege delegieren an diese
Eigentümer; die Frontendprojektion entsteht durch `scripts/build/project-vocabulary.py`.

## Tests und Grenzen

Relevante Tests unter `backend/tests`: {', '.join('`' + name + '`' for name in tests_for_key)};
zusätzlich `test_structure_architecture.py` und `test_structure_completion.py`.
SQL-Prüfungen laufen ausschließlich über `scripts/run-isolated-tests.py`.
Die Tests belegen ihren beschriebenen Umfang; sie zertifizieren keine Hardware,
keine Safetyfunktion und keine nicht implementierte Technologievariante.

## Erweiterungen

Neue technische Regeln und Adapter gehören in dieses Paket. Profiländerungen
erfordern Registry-, Parameter-, Projektlade- und Projektionstests. Branchenvorlagen
referenzieren die Technologie und erhalten keine eigene Implementierung.
Siehe [gemeinsamer Einstieg](../README.md).
'''
    write(profile_path.with_name('README.md').relative_to(ROOT).as_posix(), text)

write('backend/nis/communication/technologies/README.md', '''# Kommunikationstechnologien

Alle 125 vorhandenen Identitäten haben genau einen Ordner mit `profile.json`,
`definition.py` und einer README zum tatsächlichen Unterstützungsumfang.
CAN CC, CAN FD, Ethernet, LIN, I2C und SPI besitzen ausführbare Timingmodelle;
deren Framing, Scheduling und gegebenenfalls Arbitrierung liegen beim Eigentümer.
Andere Profile behalten ihre vorhandenen Fähigkeitszustände.

Neue Technologie: eigenen Ordner und explizites Profil gemäß TechnologyProfile
anlegen, ID in der bestehenden Katalogreihenfolge ergänzen, erforderliche Adapter
registrieren und Fähigkeiten erst nach belastbaren Nachweisen freigeben.
Keine zweite Registry und keine branchenabhängige Kopie anlegen.
`scripts/build/project-vocabulary.py` projiziert die Daten für das Frontend;
`test_structure_completion.py` prüft die Übereinstimmung.

Einstiege: [CAN](can/README.md), [CAN FD](can_fd/README.md),
[Ethernet](ethernet/README.md), [LIN](lin/README.md), [FlexRay](flexray/README.md).
Bestehende Altimporte bleiben durch `backend/nis/compatibility.json` kompatibel.
Verbraucher, Eigentümer und Entfernungskriterien stehen pro Pfad in
`docs/migrations/structure_mapping.csv`. Ein leerer interner Verbraucherscan
beweist keine Abwesenheit externer oder persistierter Verbraucher.
''')
for key, old, new in [
    ('can', '"backend.nis.simulation.runtime.event_scheduler",\n    "backend.nis.engineering.capacity.calculators",', '"backend.nis.communication.technologies.can.arbitration",\n    "backend.nis.communication.technologies.can.timing",\n    "backend.nis.communication.technologies.can.scheduling",\n    "backend.nis.communication.technologies.can_fd.timing",'),
    ('lin', '"backend.nis.engineering.capacity.dimensioning",', '"backend.nis.communication.technologies.lin.scheduling",'),
    ('flexray', '"backend.nis.engineering.capacity.calculators",', '"backend.nis.communication.technologies.flexray.definition",'),
]:
    path = f'backend/nis/communication/technologies/{key}/ownership.py'
    write(path, read(path).replace(old, new).replace('"backend.nis.communication.catalog",', f'"backend.nis.communication.technologies.{key}.definition",'))
apply('architecture-and-documentation')
