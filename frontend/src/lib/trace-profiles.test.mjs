import test from 'node:test';
import assert from 'node:assert/strict';
import { eventFromRecord } from './trace-records.ts';
import { automaticProfile, availableColumns, displayTraceValue, TRACE_PROFILES } from './trace-profiles.ts';

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

test('each requested technology has its own profile and transport fields', () => {
  const samples = [
    ['CAN_FD', 'can', {can: {arbitration_id: 291}}],
    ['DDS', 'dds', {dds: {topic: 'Temperature'}}],
    ['Modbus_RTU', 'modbus', {modbus: {function_code: 3, register_address: 100}}],
    ['PROFINET', 'profinet', {profinet: {frame_id: 32768}}],
    ['ARINC429', 'arinc429', {arinc429: {label: '203'}}],
  ];
  for (const [technology, expected, protocols] of samples) {
    const event = eventFromRecord({time_s: 0, technology, protocols, message: 'unit', source: 'node'}, 0);
    assert.equal(automaticProfile([event]), expected);
    if (expected !== 'can') {
      assert.ok(TRACE_PROFILES[expected].columns.some(column => column.read(event) !== undefined));
      assert.ok(TRACE_PROFILES[expected].columns.every(column => column.label !== 'CAN-ID'));
    }
  }
});

test('mixed default columns use neutral names and normalized references', () => {
  const event = eventFromRecord({time_s: 0, technology: 'DDS', message_id: 'topic-1', sender_hardware: 'writer-1'}, 0);
  const columns = TRACE_PROFILES.generic.columns;
  assert.deepEqual(columns.map(column => column.label), ['Nachricht / Transport Unit', 'Sender', 'Empfänger', 'Zeitbasis']);
  assert.equal(columns[0].read(event), 'topic-1');
  assert.equal(columns[1].read(event), 'writer-1');
});

test('CAN identifiers, transport direction and observation status are distinct', () => {
  const event = eventFromRecord({time_s: 0, technology: 'CAN_FD', message: 'MotorStatus',
    status: 'FAULT', direction: 'tx', protocols: {can: {arbitration_id: 291}}}, 0);
  const columns = TRACE_PROFILES.can.columns;
  assert.equal(columns.find(column => column.label === 'CAN-ID').read(event), 291);
  assert.equal(columns.find(column => column.label === 'Rx/Tx').read(event), 'tx');
  assert.equal(columns.find(column => column.label === 'Status').read(event), 'FAULT');
  const noIdentifier = eventFromRecord({time_s: 0, technology: 'CAN_FD', message: 'MotorStatus'}, 0);
  assert.equal(columns.find(column => column.label === 'CAN-ID').read(noIdentifier), undefined);
});
