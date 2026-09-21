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
});

test('an imported event without correlation or release evidence stays uncorrelated', () => {
  const model = buildSequenceDiagram([{ event_id: 'raw', time_s: .02, source: 'A', destination: 'B',
    status: 'observed' }], 'OBSERVED');
  assert.equal(model.uncorrelatedCount, 1);
  assert.equal(model.events[0].transactionId, null);
  assert.equal(model.events[0].transportLatencyMs, null);
});
