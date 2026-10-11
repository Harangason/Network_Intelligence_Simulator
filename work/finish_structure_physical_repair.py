from finish_structure_owners import *

path = 'backend/nis/communication/core/physical.py'
source = read(path)
start = source.index('        if unresolved_modbus:')
end = source.index('        profile, expected_pairs', start)
source = source[:start] + source[end:]
phases = ['validate_duplex', 'validate_variant', 'validate_medium', 'validate_access', 'validate_phy_selection', 'validate_resources']
for index, name in enumerate(phases, 1):
    source = source.replace(f'physical_rule_{index}', name)
write(path, source)
for path in sorted((ROOT / 'backend/nis/communication/technologies').glob('*/physical.py')):
    source = path.read_text(encoding='utf-8')
    if path.parent.name in {'modbus_rtu', 'modbus_ascii'}:
        at = source.index('\n', source.index('def physical_rule_1(')) + 1
        source = source[:at] + '''    if unresolved_modbus:
        finding('REVIEW','MODBUS_SERIAL_PHY_UNKNOWN','Actual RS4852W/4W or RS232 must be selected; RTU does not imply RS485.')
    supplied_duplex = {'FULL':'FULL_DUPLEX','HALF':'HALF_DUPLEX'}.get(data.get('duplex'),data.get('duplex'))
''' + source[at:]
    for index, name in enumerate(phases, 1):
        source = source.replace(f'physical_rule_{index}', name)
    write(path.relative_to(ROOT).as_posix(), source)
apply('physical-hook-repair')
