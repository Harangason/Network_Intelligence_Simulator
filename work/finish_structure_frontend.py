"""Guarded registry-derived frontend identity and parameter projections."""
from finish_structure_owners import *
import re

techroot = 'backend/nis/communication/technologies/'
registry_path = 'backend/nis/communication/registry.py'
registry = read(registry_path)
node = next(n for n in ast.parse(registry).body if isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'BUILTIN_PROFILE_ALIASES')
aliases = ast.literal_eval(node.value)
for key, value in aliases.items():
    write(techroot + key + '/identity.json', json.dumps({'aliases': value}, indent=2) + '\n')
lines = registry.splitlines()
lines[node.lineno - 1:node.end_lineno] = [
    'from backend.nis.communication.catalog import TECHNOLOGY_IDS, technology_identity',
    'BUILTIN_PROFILE_ALIASES = {key: tuple(identity["aliases"]) for key in TECHNOLOGY_IDS',
    '                           if (identity := technology_identity(key)).get("aliases")}']
write(registry_path, '\n'.join(lines) + '\n')
catalog_path = 'backend/nis/communication/catalog.py'
catalog = read(catalog_path)
pos = catalog.index('def technology_review(')
catalog = catalog[:pos] + '''def technology_identity(technology_id):
    path = Path(__file__).parent / 'technologies' / technology_id / 'identity.json'
    return loads(path.read_text(encoding='utf-8')) if path.is_file() else {}

''' + catalog[pos:]
write(catalog_path, catalog)

# One owner for configurable planning defaults, separately from protocol limits.
planning = 'backend/nis/engineering/network/bus_settings.py'
source = read(planning)
n = next(n for n in ast.parse(source).body if isinstance(n, ast.Assign)
         and n.targets[0].id == 'DEFAULT_BUS_PARTICIPANT_LIMITS')
limits = ast.literal_eval(n.value)
write('backend/nis/engineering/network/planning-defaults.json', json.dumps(limits, indent=2) + '\n')
lines = source.splitlines()
lines[n.lineno - 1:n.end_lineno] = ["from pathlib import Path", "DEFAULT_BUS_PARTICIPANT_LIMITS = json.loads(Path(__file__).with_name('planning-defaults.json').read_text(encoding='utf-8'))"]
write(planning, '\n'.join(lines) + '\n')

builder = '''"""Generate offline frontend projections from authoritative NIS owners."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]

def technology_projection(root=ROOT):
    technology_root = root / 'backend/nis/communication/technologies'
    technologies = []
    inputs = {}
    for source in sorted(technology_root.glob('*/profile.json')):
        profile = json.loads(source.read_text(encoding='utf-8'))
        identity_path, review_path = source.with_name('identity.json'), source.with_name('review.json')
        identity = json.loads(identity_path.read_text()) if identity_path.is_file() else {}
        review = json.loads(review_path.read_text(encoding='utf-8')) if review_path.is_file() else {}
        proposal = review.get('rate_proposal') or profile.get('parameter_proposals') or {}
        for path in [source, identity_path, review_path]:
            if path.is_file():
                inputs[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        technologies.append({'id': profile['id'], 'label': profile['label'],
            'aliases': list(dict.fromkeys([*identity.get('aliases', []), profile['label'], *profile.get('aliases', [])])),
            'max_payload_bytes': profile.get('max_payload_bytes'),
            'rate_proposal_bps': proposal.get('default_bps') or proposal.get('candidate'),
            'rate_proposal_status': 'REVIEW_REQUIRED', 'default_stack': profile.get('default_stack', [])})
    planning = root / 'backend/nis/engineering/network/planning-defaults.json'
    inputs[planning.relative_to(root).as_posix()] = hashlib.sha256(planning.read_bytes()).hexdigest()
    return {'schema_version': 1, 'source_sha256': hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest(),
            'technologies': technologies, 'planning_limits': json.loads(planning.read_text())}

def project(root=ROOT):
    source = root / 'backend/nis/domain/inventory-vocabulary.json'
    (root / 'frontend/src/features/agent/lib/inventory-vocabulary.json').write_bytes(source.read_bytes())
    target = root / 'frontend/src/features/communication/lib/technology-projection.json'
    target.write_text(json.dumps(technology_projection(root), ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')

if __name__ == '__main__':
    project()
'''
write('scripts/build/project-vocabulary.py', builder)
# Generate against staged owner metadata without importing application code.
projected = []
inputs = {}
for source in sorted((ROOT / techroot).glob('*/profile.json')):
    profile = json.loads(source.read_text())
    identity_rel = source.with_name('identity.json').relative_to(ROOT).as_posix()
    identity_text = WRITES.get(identity_rel, read(identity_rel) if (ROOT / identity_rel).is_file() else None)
    review_path = source.with_name('review.json')
    identity = json.loads(identity_text) if identity_text else {}
    review = json.loads(review_path.read_text(encoding='utf-8')) if review_path.is_file() else {}
    proposal = review.get('rate_proposal') or profile.get('parameter_proposals') or {}
    for path in [source, source.with_name('identity.json'), review_path]:
        relative = path.relative_to(ROOT).as_posix()
        data = WRITES[relative].encode('utf-8') if relative in WRITES else path.read_bytes() if path.is_file() else None
        if data is not None:
            inputs[relative] = hashlib.sha256(data).hexdigest()
    projected.append({'id': profile['id'], 'label': profile['label'],
        'aliases': list(dict.fromkeys([*identity.get('aliases', []), profile['label'], *profile.get('aliases', [])])),
        'max_payload_bytes': profile.get('max_payload_bytes'),
        'rate_proposal_bps': proposal.get('default_bps') or proposal.get('candidate'),
        'rate_proposal_status': 'REVIEW_REQUIRED', 'default_stack': profile.get('default_stack', [])})
relative = 'backend/nis/engineering/network/planning-defaults.json'
inputs[relative] = hashlib.sha256(WRITES[relative].encode()).hexdigest()
projection = {'schema_version': 1, 'source_sha256': hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest(),
              'technologies': projected, 'planning_limits': limits}
write('frontend/src/features/communication/lib/technology-projection.json', json.dumps(projection, ensure_ascii=False, indent=2) + '\n')

write('frontend/src/features/communication/lib/bus-technology.ts', '''import type { BusType } from "../../network/lib/topology";
import projection from './technology-projection.json' with { type: 'json' };

// Editor choices are UI capabilities; aliases and technical values are generated.
export const editorBusTypes = ['can', 'can_fd', 'can_xl', 'lin', 'automotive_ethernet', 'flexray',
  'i2c', 'spi', 'uart', 'modbus_rtu', 'modbus_tcp', 'gpio', 'pwm', 'adc', 'dac'] as const;
const token = (value: string) => value.trim().toLowerCase().replace(/[- /]+/g, '_');
const identities = new Map(projection.technologies.flatMap(item =>
  [item.id, ...item.aliases].map(alias => [token(alias), item.id] as const)));

/** Resolve a confirmed technology. A network name carries no technology evidence. */
export function routingBusType(protocol?: string | null, _networkId?: string | null): BusType | null {
  if (!protocol?.trim()) return null;
  const canonical = identities.get(token(protocol));
  if (!canonical) return null;
  const editorKey = canonical === 'ethernet' ? 'automotive_ethernet' : canonical;
  return editorBusTypes.includes(editorKey as BusType) ? editorKey as BusType : null;
}
''')
path = 'frontend/src/features/communication/lib/bus-settings.ts'
s = read(path)
start, end = s.index('export const DEFAULT_BUS_PARTICIPANT_LIMITS'), s.index('export const BUS_SETTING_LABELS')
s = "import projection from './technology-projection.json' with { type: 'json' };\n" + s[:start] + 'export const DEFAULT_BUS_PARTICIPANT_LIMITS: Record<string, number> = projection.planning_limits;\n' + s[end:]
write(path, s)

# Remove the independent technical display catalogue. UI scenario/style fields
# remain local; rates and payload proposals come from the generated contract.
path = 'frontend/src/features/network/lib/topology.ts'
s = read(path)
s = "import projection from '../../communication/lib/technology-projection.json' with { type: 'json' };\nimport { editorBusTypes } from '../../communication/lib/bus-technology';\n" + s
start, end = s.index('export const busProfiles:'), s.index('function catalogTechnologyLabel')
old = s[start:end]
colors = {key: color for key, color in re.findall(r'(\w+): \{[^\n]+color: "([^"]+)"', old)}
ui = {key: {'color': color} for key, color in colors.items()}
new = '''const busStyles: Record<string, {color: string}> = ''' + json.dumps(ui, indent=2) + ''';
function projectedBusProfile(key: string): BusProfile {
  const canonical = key === 'automotive_ethernet' ? 'ethernet' : key === 'ros2_dds' ? 'ros2' : key;
  const definition = projection.technologies.find(item => item.id === canonical);
  return { label: definition?.label ?? catalogTechnologyLabel(key),
    bitrate: definition?.rate_proposal_bps ?? null, cycleMs: 10,
    payload: definition?.max_payload_bytes ?? 64, color: busStyles[key]?.color ?? '#75a9e8' };
}
export const busProfiles = Object.fromEntries(editorBusTypes.map(key => [key, projectedBusProfile(key)])) as Record<BusType, BusProfile>;
const catalogBusProfiles = Object.fromEntries(projection.technologies.map(item => [item.id, projectedBusProfile(item.id)]));

'''
s = s[:start] + new + s[end:]
write(path, s)

path = 'frontend/src/features/simulation/ui/simulation-wizard.tsx'
s = read(path)
s = s.replace('const key = routingSegmentKey(sourceId, targetId, bus, route.id);',
              'if (!bus) { keys.add(`${route.id}:TECHNOLOGY_UNRESOLVED`); continue; }\n      const key = routingSegmentKey(sourceId, targetId, bus, route.id);')
s = s.replace('if (linkedSegments.has(routingSegmentKey(sourceId, targetId, bus, route.id))) continue;',
              'if (!bus) return []; // Never create a partially substituted route.\n      if (linkedSegments.has(routingSegmentKey(sourceId, targetId, bus, route.id))) continue;')
s = s.replace('  return { checking, suggestions };', '''  const unresolved = useMemo(() => routes.filter(routeCanSuggestNetworkChange).filter(route =>
    !routingBus(route.source.protocol, route.source.network_id) || route.destinations.some(destination =>
      !routingBus(destination.protocol ?? route.source.protocol, destination.network_id))), [routes]);
  return { checking, suggestions, unresolved };''')
s = s.replace('suggestions: routingNetworkSuggestions,', 'suggestions: routingNetworkSuggestions,\n    unresolved: unresolvedRoutingTechnologies,')
s = s.replace('{routingLoadError ? (', '''{unresolvedRoutingTechnologies.length > 0 && <p role="alert" className="net-route-suggestions-error">
                Für {unresolvedRoutingTechnologies.map(route => `${route.route_code} (${route.source.protocol || 'Technologie fehlt'})`).join(', ')} ist die Buszuordnung offen.
                Bitte die bestätigte Technologie und den physischen Pfad im Routing prüfen; diese Vorschläge können nicht übernommen werden.
              </p>}
              {routingLoadError ? (''')
write(path, s)
apply('frontend-registry')
