"""Inventory-backed responsibility map and staged backend relocation."""
import ast
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/implementation-workloads/project-structure-migration-20261003'
STAGE = ROOT / 'work/backend-structure-stage'
inventory = json.loads((OUT / 'inventory-before.json').read_text())
technology = json.loads((OUT / 'technology-migration-plan.json').read_text())['mappings']

def owner(source):
    p = Path(source)
    name = p.stem
    if source in technology:
        return technology[source]
    if source.startswith('backend/engineering/'):
        rel = source[len('backend/engineering/'):]
        first = rel.split('/')[0]
        if first == 'agent_tools': return 'backend/nis/agent/tools/' + rel[len('agent_tools/'):]
        if first == 'core': return 'backend/nis/domain/core/' + rel[len('core/'):]
        if first == 'workflow': return 'backend/nis/workflow/services/' + rel[len('workflow/'):]
        if name == 'lin_schedule': return 'backend/nis/communication/technologies/lin/timing.py'
        if first in {'intelligence', 'reasoning', 'semantic_intelligence'}:
            return 'backend/nis/intelligence/engineering/' + rel
        if '/' not in rel:
            if name == 'api': return 'backend/nis/interfaces/http/engineering.py'
            if name in {'db', 'repository', 'schema'}: return 'backend/nis/infrastructure/persistence/' + p.name
            if name in {'models', 'addressing', 'device_classification'}:
                return 'backend/nis/domain/' + ('vocabulary.py' if name == 'models' else p.name)
            projects = {'project_bundle', 'project_context', 'project_refresh'}
            signals = {'signal_audit', 'signal_behavior_service', 'signal_integrity_service', 'signal_integrity',
                       'message_bindings', 'message_packing'}
            network = {'bus_migration', 'bus_settings', 'network_assignment', 'network_crossings', 'network_naming',
                       'network_scene', 'physical_ports', 'physical_segments', 'topology_removal', 'topology_sync',
                       'frame_device'}
            structure = {'structure', 'structure_rules', 'structure_transfer', 'system_clusters', 'system_merge',
                         'system_ownership', 'spatial_architecture', 'spatial_zoning', 'zoning_service'}
            requirements = {'requirement_expansion', 'generation_rule_manager', 'generation_experience'}
            if name in projects: return 'backend/nis/engineering/projects/' + p.name
            if name in signals: return 'backend/nis/engineering/signals/' + p.name
            if name in network: return 'backend/nis/engineering/network/' + p.name
            if name in structure: return 'backend/nis/engineering/structure/' + p.name
            if name in requirements: return 'backend/nis/engineering/requirements/' + p.name
            if name.startswith('communication_') or name in {'confirmed_routes', 'device_communication', 'wizard_communication'}:
                return 'backend/nis/engineering/communication/' + p.name
        return 'backend/nis/engineering/' + rel
    if source.startswith('backend/app/'):
        if name == 'config': return 'backend/nis/infrastructure/paths.py'
        if name in {'api', 'trace_import'}: return 'backend/nis/interfaces/http/' + ('simulation.py' if name == 'api' else p.name)
        if name in {'saved_storage', 'trace_storage'}: return 'backend/nis/infrastructure/storage/' + p.name
        if name.startswith('trace_'): return 'backend/nis/traces/' + p.name
        if name in {'simulation_service', 'job_service', 'port_load', 'e2e_assurance', 'runtime_analysis'}:
            return 'backend/nis/simulation/' + ('service.py' if name == 'simulation_service' else p.name)
        return 'backend/nis/app/' + p.name
    for old, new in [('agent_core', 'agent'), ('knowledge', 'knowledge'), ('intelligence', 'intelligence'),
                     ('workflow', 'workflow'), ('simulator_engineering_mcp', 'interfaces/mcp')]:
        prefix = 'backend/' + old + '/'
        if source.startswith(prefix): return 'backend/nis/' + new + '/' + source[len(prefix):]
    if source.startswith('backend/specializations/industries/'):
        rel = source[len('backend/specializations/industries/'):]
        if '/' in rel:
            industry, tail = rel.split('/', 1)
            return f'backend/nis/industries/{industry}/' + ('manifest.py' if tail == '__init__.py' else tail)
        return 'backend/nis/industries/' + ('catalog.py' if name == '__init__' else p.name)
    if source.startswith('backend/specializations/technologies/'):
        rel = source[len('backend/specializations/technologies/'):]
        if '/' in rel:
            family, tail = rel.split('/', 1)
            if family in {'can', 'ethernet', 'lin', 'flexray'}:
                return f'backend/nis/communication/technologies/{family}/' + ('ownership.py' if tail == '__init__.py' else tail)
            industry = {'embedded_io': 'embedded_systems', 'wireless_iot': 'iot_wireless'}.get(family, family)
            return f'backend/nis/industries/{industry}/' + ('technology_refs.py' if tail == '__init__.py' else tail)
        return 'backend/nis/communication/ownership.py'
    if source.startswith('backend/specializations/'):
        return 'backend/nis/specializations/' + source[len('backend/specializations/'):]
    if source.startswith('backend/simulator/'):
        rel = source[len('backend/simulator/'):]
        if rel.startswith('physic_lib/Industries/'):
            tail = rel[len('physic_lib/Industries/'):]
            names = {'Aerospace': 'aerospace', 'Automotive': 'automotive', 'BuildingAutomation': 'building_automation',
                     'EmbeddedSystems': 'embedded_systems', 'Energy': 'energy', 'Generic': 'generic_networking',
                     'IndustrialAutomation': 'industrial_automation', 'Marine': 'marine', 'Rail': 'rail', 'RoboticsROS': 'robotics_ros'}
            first, *rest = tail.split('/')
            if first in names:
                return 'backend/nis/industries/' + names[first] + '/templates/' + '/'.join(rest)
            return 'backend/nis/industries/legacy_projection/' + tail
        if rel.startswith('physic_lib/'):
            return 'backend/nis/physics/' + rel[len('physic_lib/'):].replace('PhysicalAI/', 'physical_ai/').replace('Samples/', 'samples/').replace('Config/', 'config/')
        if rel.startswith('format_generators/'):
            if name.startswith('generate_can_') or name in {'can_cli', 'can_format_writers'}:
                return 'backend/nis/communication/technologies/can/formats/' + p.name
            if name.startswith('generate_eth_') or name in {'eth_cli', 'eth_format_writers'}:
                return 'backend/nis/communication/technologies/ethernet/formats/' + p.name
            return 'backend/nis/traces/formats/' + p.name
        if name == 'ethernet_transport': return 'backend/nis/communication/technologies/ethernet/transport.py'
        if name == 'event_scheduler': return 'backend/nis/simulation/runtime/event_scheduler.py'
        if name in {'universal_trace', 'trace_realism'}: return 'backend/nis/traces/' + p.name
        if name == 'standalone_cli': return 'backend/nis/interfaces/cli/standalone.py'
        if name == 'generate_realistic_communication_tool': return 'backend/nis/simulation/communication_generator.py'
        return 'backend/nis/simulation/' + rel
    return source

def module(path):
    parts = Path(path).with_suffix('').parts
    return '.'.join(parts[:-1] if parts[-1] == '__init__' else parts)

def main():
    mappings = {r['path']: owner(r['path']) for r in inventory['files']
                if r['path'].endswith('.py') and r['path'].startswith('backend/')
                and not r['path'].startswith(('backend/tests/', 'backend/backend/', 'backend/nis/', 'backend/communication/'))}
    mappings = {s: t for s, t in mappings.items() if s != t}
    aliases = {module(s): module(t) for s, t in mappings.items()}
    aliases.update({'backend.simulator': 'backend.nis.simulation', 'backend.engineering': 'backend.nis.engineering',
                    'backend.simulator.format_generators': 'backend.nis.traces.formats',
                    'backend.simulator.physic_lib': 'backend.nis.physics'})
    flat = {module(s).removeprefix('backend.simulator.'): module(t) for s, t in mappings.items()
            if s.startswith('backend/simulator/')}
    combined = dict(aliases, **flat)
    def remap(name):
        for prefix in sorted(combined, key=len, reverse=True):
            if name == prefix or name.startswith(prefix + '.'):
                return combined[prefix] + name[len(prefix):]
        return name
    candidates = {r['path'] for r in inventory['files'] if r['path'].endswith('.py')}
    candidates.update(json.loads((OUT / 'technology-migration-plan.json').read_text())['writes'])
    writes = {}
    path_specials = []
    for source in sorted(candidates):
        path = ROOT / source
        if not path.is_file() or path.suffix != '.py' or source.startswith(('backend/backend/', 'docs/', 'tool-checker/')):
            continue
        text = path.read_text(encoding='utf-8-sig')
        try: tree = ast.parse(text)
        except SyntaxError: continue
        lines = text.splitlines(keepends=True)
        edits = []
        for node in ast.walk(tree):
            replacement = None
            if isinstance(node, ast.ImportFrom) and node.module and not node.level:
                pieces = []
                for alias in node.names:
                    child = node.module + '.' + alias.name
                    if child in combined:
                        parent, name = remap(child).rsplit('.', 1)
                        pieces.append(f'from {parent} import {name} as {alias.asname or alias.name}')
                    else:
                        pieces.append(f'from {remap(node.module)} import {alias.name}' + (' as ' + alias.asname if alias.asname else ''))
                if remap(node.module) != node.module or any(node.module + '.' + a.name in combined for a in node.names):
                    replacement = ('\n' + ' ' * node.col_offset).join(pieces)
            elif isinstance(node, ast.Import):
                pieces = []
                changed = False
                for alias in node.names:
                    target = remap(alias.name)
                    changed |= target != alias.name
                    # Flat imports must retain their original local variable name.
                    bound = alias.asname or (alias.name if '.' not in alias.name else None)
                    pieces.append('import ' + target + (' as ' + bound if bound else ''))
                if changed: replacement = ('\n' + ' ' * node.col_offset).join(pieces)
            if replacement:
                start = sum(len(x) for x in lines[:node.lineno - 1]) + node.col_offset
                end = sum(len(x) for x in lines[:node.end_lineno - 1]) + node.end_col_offset
                edits.append((start, end, replacement))
        for start, end, replacement in sorted(edits, reverse=True):
            text = text[:start] + replacement + text[end:]
        pattern = re.compile(r'backend\.(?:app|engineering|agent_core|intelligence|knowledge|workflow|specializations|simulator_engineering_mcp|simulator)(?:\.[A-Za-z_][A-Za-z_0-9]*)*')
        text = pattern.sub(lambda m: remap(m.group()), text)
        target = mappings.get(source, source)
        if source == 'backend/app/config.py':
            text = text.replace('return Path(module_file).resolve().parents[1]',
                'resolved = Path(module_file).resolve()\n    return next((parent for parent in resolved.parents if parent.name == "backend"), resolved.parents[1])')
        if source == 'backend/app/runtime_config.py':
            text = text.replace('ROOT = Path(__file__).resolve().parents[2]',
                'from backend.nis.infrastructure.paths import PROJECT_ROOT as ROOT')
        if source == 'backend/engineering/agent_tools/inventory_quantities.py':
            text = text.replace('VOCABULARY = json.loads((Path(__file__).resolve().parents[3] /',
                'from backend.nis.infrastructure.paths import PROJECT_ROOT\n\nVOCABULARY = json.loads((PROJECT_ROOT /')
        if source == 'backend/engineering/agent_tools/wizard_generation.py':
            text = text.replace("script = Path(__file__).resolve().parents[3] / 'frontend'",
                "from backend.nis.infrastructure.paths import PROJECT_ROOT\n    script = PROJECT_ROOT / 'frontend'")
        if source == 'backend/simulator/format_generators/common_trace.py':
            text = text.replace('PROJECT_ROOT = Path(__file__).resolve().parents[1]',
                'from backend.nis.infrastructure.paths import PROJECT_ROOT')
        if source == 'backend/simulator/format_generators/generate_can_blf.py':
            text = text.replace('ROOT = Path(__file__).resolve().parents[1]',
                'from backend.nis.infrastructure.paths import PROJECT_ROOT as ROOT')
        if source == 'backend/simulator/generate_realistic_communication_tool.py':
            text = text.replace('generator_dir = Path(__file__).resolve().parent / "format_generators"',
                'from backend.nis.infrastructure.paths import BACKEND_ROOT\n    generator_dir = BACKEND_ROOT / "simulator" / "format_generators"')
        if source == 'backend/intelligence/__init__.py':
            text += '\n' + (ROOT / 'backend/nis/intelligence/__init__.py').read_text(encoding='utf-8').replace('"""Deterministic intelligence, analytics and machine learning."""', '')
        if target != source and '__file__' in text:
            path_specials.append({'source': source, 'target': target, 'lines': [line for line in text.splitlines() if '__file__' in line]})
        if text != path.read_text(encoding='utf-8-sig') or target != source:
            compile(text, target, 'exec')
            writes[target] = text
        if target != source:
            writes[source] = f'"""Compatibility only; owner {module(target)}."""\nimport importlib\nimport sys\nsys.modules[__name__] = importlib.import_module({module(target)!r})\n'
    for target, text in writes.items():
        path = STAGE / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode('utf-8'))
    # Add all legacy names to the finite import map without a second runtime.
    compat = json.loads((ROOT / 'backend/nis/compatibility.json').read_text())
    compat.update(aliases)
    writes['backend/nis/compatibility.json'] = json.dumps(compat, indent=2) + '\n'
    writes['backend/nis/compatibility.py'] = (ROOT / 'backend/nis/compatibility.py').read_text().replace(
        '    def exec_module(self, module):',
        '    def get_code(self, fullname):\n        spec = importlib.util.find_spec(self.target)\n        return spec.loader.get_code(self.target)\n    def exec_module(self, module):')
    manifest_path = 'scripts/write-build-info.py'
    writes[manifest_path] = writes.get(manifest_path, (ROOT / manifest_path).read_text()).replace(
        '"backend/app/build-info.json"', '"backend/nis/app/build-info.json"')
    for target in ('backend/nis/compatibility.json', 'backend/nis/compatibility.py', manifest_path):
        path = STAGE / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(writes[target].encode('utf-8'))
    plan = {'mappings': mappings, 'aliases': aliases, 'flat_aliases': flat,
            'writes': {k: hashlib.sha256(v.encode()).hexdigest() for k, v in writes.items()},
            'file_location_dependencies': path_specials}
    (OUT / 'backend-migration-plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    destination = ROOT / 'docs/migrations/structure_mapping.csv'
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=['source_path', 'target_path', 'action', 'responsibility', 'consumers', 'data_impact', 'verification', 'status'])
        writer.writeheader()
        for row in inventory['files']:
            source = row['path']; target = owner(source) if source.endswith('.py') else source
            data = Path(source).suffix.lower() in {'.db', '.sqlite', '.sqlite3'}
            writer.writerow({'source_path': source, 'target_path': target,
                'action': 'data_inventory' if data else ('move_with_compatibility' if target != source else 'unchanged'),
                'responsibility': target.split('/')[2] if target.startswith('backend/nis/') else source.split('/')[0],
                'consumers': 'import graph: inventory-before.json',
                'data_impact': 'SQLite classification and coherent snapshot required' if data else 'identity/schema preserved',
                'verification': 'release gate and architecture checks',
                'status': 'PENDING_DATA_REVIEW' if data else ('TECHNOLOGY_IMPLEMENTED' if source in technology else 'PLANNED')})
    print(json.dumps({'planned_moves': len(mappings), 'staged_writes': len(writes), 'location_dependencies': path_specials}, indent=2))

if __name__ == '__main__':
    main()
