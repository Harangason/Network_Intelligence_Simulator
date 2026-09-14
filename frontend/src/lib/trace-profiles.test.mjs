import test from 'node:test';
import assert from 'node:assert/strict';
import { eventFromRecord } from './trace-records.ts';
import { automaticProfile, availableColumns, displayTraceValue } from './trace-profiles.ts';

test('mixed sessions preserve vendor fields and never force a CAN profile', () => {
  const can = eventFromRecord({ timestamp: 0, technology: 'CAN FD · 1', dlc: 9, extended_id: false, vendor: { counter: 0 } }, 0);
  const eth = eventFromRecord({ timestamp: 1, technology: 'Ethernet', protocols: { ip: { source: '::1' } } }, 1);
  assert.equal(automaticProfile([can]), 'can');
  assert.equal(automaticProfile([eth]), 'ethernet');
  assert.equal(automaticProfile([can, eth]), 'generic');
  const columns = availableColumns([can, eth]);
  assert.equal(columns.find(c => c.key === 'vendor.counter').read(can), 0);
  assert.equal(displayTraceValue(columns.find(c => c.key === 'extended_id').read(can)), 'false');
  assert.equal(columns.find(c => c.key === 'protocols.ip.source').read(eth), '::1');
});

test('unknown records retain original structure and missing time is explicit', () => {
  const raw = { timestamp: null, time_status: 'unavailable', vendor: { matrix: [[1,2],[3,4]] }, technology: 'custom' };
  const event = eventFromRecord(raw, 0);
  assert.equal(event.timeKnown, false);
  assert.equal(event.original, raw);
  assert.equal(automaticProfile([event]), 'generic');
  assert.equal(displayTraceValue(event.original.vendor.matrix), '[[1,2],[3,4]]');
});
