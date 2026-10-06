import assert from 'node:assert/strict';
import test from 'node:test';
import { routingBusType } from './bus-technology.ts';

test('canonical protocol wins over the historic technology in a stable bus ID', () => {
  const legacyId = 'Antriebsstrang_01-IO-abgasnachbehandlung-lin-S01';
  for (const [protocol, bus] of [['CAN', 'can'], ['CAN_FD', 'can_fd'], ['CAN_XL', 'can_xl'], ['LIN', 'lin'], ['ETHERNET', 'automotive_ethernet'], ['FLEXRAY', 'flexray']]) {
    assert.equal(routingBusType(protocol, legacyId), bus);
  }
  assert.equal(routingBusType(null, legacyId), null);
});


test('registry technology identities remain distinct and unresolved protocols stay unresolved', () => {
  for (const [protocol, bus] of [['MODBUS_RTU', 'modbus_rtu'], ['I2C', 'i2c'], ['SPI', 'spi'], ['PWM', 'pwm'], ['GPIO', 'gpio']]) {
    assert.equal(routingBusType(protocol, 'network-can_fd'), bus);
  }
  for (const protocol of [null, undefined, '', 'NMEA2000', 'MATTER', 'unknown-protocol']) {
    assert.equal(routingBusType(protocol, 'network-can_fd'), null);
  }
  assert.equal(routingBusType('CAN FD', 'network-lin'), 'can_fd');
});
