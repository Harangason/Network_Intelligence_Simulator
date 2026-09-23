import assert from 'node:assert/strict';
import test from 'node:test';
import { buildSequenceDiagram } from './e2e-sequence.ts';

test('simulation and trace use the same multi-hop transaction projection', () => {
  const records = [
    { event_id: 'r:1:segment:0', transaction_id: 'r:1', time_s: .012, origin_release_time_s: .01,
      sender_hardware: 'Source', receiver_hardware: ['Gateway'], technology: 'CAN_FD',
      route_id: 'r', status: 'transmitted', segment_index: 0, segment_count: 2, final_segment: false },
    { event_id: 'r:1:segment:1', transaction_id: 'r:1', time_s: .018, origin_release_time_s: .01,
      sender_hardware: 'Gateway', receiver_hardware: ['Target'], technology: 'LIN',
      route_id: 'r', status: 'transmitted', segment_index: 1, segment_count: 2, final_segment: true },
  ];
  const simulated = buildSequenceDiagram(records, 'SIMULATED');
  const observed = buildSequenceDiagram(records, 'OBSERVED');
  assert.deepEqual(simulated.events, observed.events);
  assert.deepEqual(simulated.participants, ['Source', 'Gateway', 'Target']);
  assert.ok(Math.abs(simulated.events[1].transportLatencyMs - 8) < 1e-9);
  assert.equal(simulated.correlatedCount, 2);
  assert.deepEqual(simulated.transactions[0].technologies, ['CAN_FD', 'LIN']);
  assert.equal(simulated.transactions[0].complete, true);
  assert.equal(simulated.transactions[0].receiverStatus, 'NOT_OBSERVED');
});

test('an imported event without correlation or release evidence stays uncorrelated', () => {
  const model = buildSequenceDiagram([{ event_id: 'raw', time_s: .02, source: 'A', destination: 'B',
    status: 'observed' }], 'OBSERVED');
  assert.equal(model.uncorrelatedCount, 1);
  assert.equal(model.events[0].transactionId, null);
  assert.equal(model.events[0].transportLatencyMs, null);
});

test('missing middle hop does not become a complete transaction', () => {
  const records = [
    { event_id: 'segment:0', transaction_id: 'r:2', segment_index: 0, segment_count: 3,
      origin_release_time_s: 1, time_s: 1.01, status: 'transmitted' },
    { event_id: 'segment:2', transaction_id: 'r:2', segment_index: 2, segment_count: 3,
      final_segment: true, origin_release_time_s: 1, time_s: 1.02, status: 'transmitted' },
  ];
  const model = buildSequenceDiagram(records, 'SIMULATED');
  assert.equal(model.transactions[0].complete, false);
  assert.equal(model.transactions[0].receiverStatus, 'NOT_OBSERVED');
});

test('receiver acceptance needs explicit evidence and data age needs generation time', () => {
  const records = [
    { event_id: 'frame', transaction_id: 'r:3', time_s: 1.01, origin_release_time_s: 1,
      data_generation_time_s: .998, status: 'transmitted', segment_index: 0,
      segment_count: 1, final_segment: true },
    { event_id: 'accept', transaction_id: 'r:3', event_type: 'RECEIVER_ACCEPTANCE',
      origin_release_time_s: 1, data_generation_time_s: .998, time_s: 1.014 },
  ];
  const model = buildSequenceDiagram(records, 'OBSERVED');
  assert.equal(model.events[0].receiverStatus, null);
  assert.equal(model.events[1].receiverStatus, 'ACCEPTED');
  assert.ok(Math.abs(model.events[1].e2eLatencyMs - 14) < 1e-9);
  assert.ok(Math.abs(model.events[1].dataAgeAtAcceptMs - 16) < 1e-9);
  assert.equal(model.transactions[0].complete, true);
  assert.equal(model.transactions[0].receiverStatus, 'ACCEPTED');
  const noGeneration = buildSequenceDiagram(records.map(record => ({ ...record, data_generation_time_s: undefined })), 'OBSERVED');
  assert.equal(noGeneration.events[1].dataAgeAtAcceptMs, null);
});
