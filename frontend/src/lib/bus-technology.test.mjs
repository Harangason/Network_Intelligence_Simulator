import assert from 'node:assert/strict';
import test from 'node:test';
import { routingBusType } from './bus-technology.ts';

test('canonical protocol wins over the historic technology in a stable bus ID', () => {
  const legacyId = 'Antriebsstrang_01-IO-abgasnachbehandlung-lin-S01';
  for (const [protocol, bus] of [['CAN', 'can'], ['CAN_FD', 'can_fd'], ['CAN_XL', 'can_xl'], ['LIN', 'lin'], ['ETHERNET', 'automotive_ethernet'], ['FLEXRAY', 'flexray']]) {
    assert.equal(routingBusType(protocol, legacyId), bus);
  }
  assert.equal(routingBusType(null, legacyId), 'lin');
});
