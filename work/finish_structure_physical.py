from finish_structure_owners import *
from dataclasses import asdict
from backend.nis.communication.core import physical as original

path = 'backend/nis/communication/core/physical.py'
source = read(path)
tree = ast.parse(source)
function_node = node_named(source, 'validate_physical_realization')
profile_if = next(n for n in function_node.body if isinstance(n, ast.If) and ast.unparse(n.test) == 'profile is None')
specific = {}
replacements = []
args = 'data, realization, profile, finding, expected_pairs, resolved_access, unresolved_modbus'
returns = '\nreturn profile, expected_pairs, resolved_access, unresolved_modbus'
lookup = {'MODBUS_SERIAL_PHY_EXPLICIT': ['modbus_rtu', 'modbus_ascii'],
          'CCLINK_IE_VARIANT_EXPLICIT': ['cc_link_ie'], 'ETHERCAT_CLASSIC_PHY_EXPLICIT': ['ethercat'],
          'ETHERNET_PHY_EXPLICIT': ['ethernet'], 'SPI_SYNCHRONOUS': ['spi']}
# Resolution runs before findings exist; preserve these two original branches.
for n in function_node.body:
    if isinstance(n, ast.If) and 'profile.id' in ast.unparse(n.test):
        key = next(k for k in lookup if k in ast.unparse(n.test))
        for tech in lookup[key]:
            specific.setdefault(tech, {})['resolve_profile'] = function('resolve_profile', 'data, realization, profile',
                'unresolved_modbus = False\n' + textwrap.dedent(segment(source, n)) + '\nreturn profile, unresolved_modbus')
        replacements.append((n.lineno, n.end_lineno, ''))
resolve_line = next(n.lineno for n in function_node.body if isinstance(n, ast.AnnAssign))
replacements.append((resolve_line, resolve_line - 1, '    profile, unresolved_modbus = _resolve_profile(data, realization, profile)'))

counter = 0
for n in profile_if.orelse:
    if isinstance(n, ast.If) and any(k in ast.unparse(n.test) for k in lookup):
        counter += 1
        phase = f'physical_rule_{counter}'
        key = next(k for k in lookup if k in ast.unparse(n.test))
        code = textwrap.dedent(segment(source, n)) + returns
        for tech in lookup[key]:
            specific.setdefault(tech, {})[phase] = function(phase, args, code)
        replacements.append((n.lineno, n.end_lineno, f"        profile, expected_pairs, resolved_access, unresolved_modbus = _physical_rule('{phase}', {args})"))
    elif isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'expected_pairs' for t in n.targets):
        code = textwrap.dedent(segment(source, n)) + returns
        specific.setdefault('ethernet', {})['expected_pairs'] = function('expected_pairs', args, code)
        replacements.append((n.lineno, n.end_lineno,
            "        expected_pairs = profile.pair_count\n        profile, expected_pairs, resolved_access, unresolved_modbus = _physical_rule('expected_pairs', " + args + ')'))
    elif isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'allowed_topologies' for t in n.targets):
        code = textwrap.dedent(segment(source, n)) + '\nreturn allowed_topologies'
        specific.setdefault('ethernet', {})['allowed_topologies'] = function('allowed_topologies', 'realization, profile', code)
        replacements.append((n.lineno, n.end_lineno, '        allowed_topologies = _allowed_topologies(realization, profile)'))
# The early validation phases originally preceded expected_pairs assignment.
finding_line = next(n for n in function_node.body if isinstance(n, ast.FunctionDef)).end_lineno
replacements.append((finding_line + 1, finding_line, '\n    expected_pairs = profile.pair_count if profile else None'))
for start, end, content in sorted(replacements, key=lambda row: row[0], reverse=True):
    lines = source.splitlines()
    lines[start-1:end] = content.splitlines()
    source = '\n'.join(lines) + '\n'

root = 'backend/nis/communication/technologies/'
aliases = original.PROFILE_ALIASES
for tech, profile in original.PHYSICAL_PROFILES.items():
    metadata = {'profile': asdict(profile), 'aliases': [k for k,v in aliases.items() if v == tech]}
    if tech == 'ethernet': metadata['phy_pairs'] = original.PHY_PAIRS
    write(root + tech + '/physical.json', json.dumps(metadata, indent=2) + '\n')
    content = '''"""Technology-owned PHY definition and preserved realization rules."""
from json import loads
from pathlib import Path
from backend.nis.communication.core.physical import PhysicalLayerProfile, MediumAccessModel

METADATA = loads(Path(__file__).with_name('physical.json').read_text(encoding='utf-8'))
PHY_PAIRS = METADATA.get('phy_pairs', {})
'''
    if tech == 'cc_link_ie':
        content += 'from backend.nis.communication.technologies.ethernet.physical import PHY_PAIRS\n'
    content += '\n' + '\n'.join(specific.get(tech, {}).values())
    write(root + tech + '/physical.py', content)

start = source.index('CAN_ARBITRATION =')
end = source.index('\ndef physical_profile', start)
projection = '''from importlib import import_module
from backend.nis.communication.catalog import TECHNOLOGY_IDS

def _physical_owners():
    from json import loads
    from pathlib import Path
    result = {}
    for key in TECHNOLOGY_IDS:
        path = Path(__file__).parents[1] / 'technologies' / key / 'physical.json'
        if path.is_file():
            result[key] = loads(path.read_text(encoding='utf-8'))
    return result

def _physical_definition(value):
    value = dict(value)
    value['access_model'] = MediumAccessModel(value['access_model'])
    for key in ('required_conductors', 'allowed_topologies'):
        value[key] = tuple(value[key])
    if value.get('arbitration'):
        arbitration = dict(value['arbitration'])
        arbitration['access'] = MediumAccessModel(arbitration['access'])
        value['arbitration'] = ArbitrationModel(**arbitration)
    return PhysicalLayerProfile(**value)

_PHYSICAL_OWNERS = _physical_owners()
PHYSICAL_PROFILES = {key: _physical_definition(value['profile']) for key,value in _PHYSICAL_OWNERS.items()}
PROFILE_ALIASES = {alias: key for key,value in _PHYSICAL_OWNERS.items() for alias in value.get('aliases', [])}
PHY_PAIRS = _PHYSICAL_OWNERS['ethernet']['phy_pairs']
CAN_ARBITRATION = PHYSICAL_PROFILES['can'].arbitration

def _physical_implementation(profile):
    return import_module(f'backend.nis.communication.technologies.{profile.technology_id}.physical') if profile else None

def _resolve_profile(data, realization, profile):
    hook = getattr(_physical_implementation(profile), 'resolve_profile', None)
    return hook(data, realization, profile) if hook else (profile, False)

def _physical_rule(phase, data, realization, profile, finding, expected_pairs, resolved_access, unresolved_modbus):
    hook = getattr(_physical_implementation(profile), phase, None)
    return hook(data, realization, profile, finding, expected_pairs, resolved_access, unresolved_modbus) if hook else (profile, expected_pairs, resolved_access, unresolved_modbus)

def _allowed_topologies(realization, profile):
    hook = getattr(_physical_implementation(profile), 'allowed_topologies', None)
    return hook(realization, profile) if hook else profile.allowed_topologies
'''
write(path, source[:start] + projection + '\n' + source[end:])
apply('physical-owners')
