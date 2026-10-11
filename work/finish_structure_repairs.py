from finish_structure_owners import *

path = 'backend/nis/communication/technologies/ethernet/scheduling.py'
write(path, read(path).replace('    try:\n', '    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY\n    try:\n', 1))
for key in ['can', 'can_fd', 'lin']:
    path = f'backend/nis/communication/technologies/{key}/timing.py'
    write(path, read(path) + '\nfrom .definition import PROFILE\nSCHEDULE_PAYLOAD_LIMIT = PROFILE["max_payload_bytes"]\n')
path = 'backend/nis/engineering/capacity/dimensioning.py'
source = read(path)
start = source.index('    try:\n        profile_definition', source.index('def bus_schedule'))
end = source.index('    is_ethernet', start)
source = source[:start] + '''    implementation = DEFAULT_TECHNOLOGY_REGISTRY.timing_implementation(protocol)
    limit = getattr(implementation, 'SCHEDULE_PAYLOAD_LIMIT', None)
''' + source[end:]
write(path, source)
path = 'frontend/src/features/communication/lib/bus-technology.test.mjs'
write(path, read(path).replace("routingBusType(null, legacyId), 'lin'", "routingBusType(null, legacyId), null") + '''

test('registry technology identities remain distinct and unresolved protocols stay unresolved', () => {
  for (const [protocol, bus] of [['MODBUS_RTU', 'modbus_rtu'], ['I2C', 'i2c'], ['SPI', 'spi'], ['PWM', 'pwm'], ['GPIO', 'gpio']]) {
    assert.equal(routingBusType(protocol, 'network-can_fd'), bus);
  }
  for (const protocol of [null, undefined, '', 'NMEA2000', 'MATTER', 'unknown-protocol']) {
    assert.equal(routingBusType(protocol, 'network-can_fd'), null);
  }
  assert.equal(routingBusType('CAN FD', 'network-lin'), 'can_fd');
});
''')
apply('targeted-repairs')
