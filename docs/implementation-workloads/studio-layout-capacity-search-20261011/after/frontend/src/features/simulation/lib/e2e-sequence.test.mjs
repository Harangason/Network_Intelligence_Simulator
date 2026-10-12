import assert from 'node:assert/strict';
import test from 'node:test';
import { buildSequenceDiagram, compileSequenceSearch, sequenceEventMatchesParticipants } from './e2e-sequence.ts';

test('boolean sequence search preserves literal phrases and applies NOT before AND before OR', () => {
  const model = buildSequenceDiagram([
    { event_id: 'motor-can', source: 'Motor Steuerung', destination: 'System', technology: 'CAN', status: 'transmitted' },
    { event_id: 'motor-lin', source: 'Motor Steuerung', destination: 'Aktor', technology: 'LIN', status: 'timeout' },
    { event_id: 'gear', source: 'Getriebe', destination: 'System', technology: 'LIN', status: 'transmitted' },
    { event_id: 'plain', source: 'Untergrund', destination: 'System', technology: 'CAN FD', route_name: 'Status UND Diagnose' },
  ], 'SIMULATED');
  const original = structuredClone(model);
  const ids = query => {
    const search = compileSequenceSearch(query);
    assert.equal(search.error, null);
    return model.events.filter(search.matches).map(event => event.id);
  };
  assert.deepEqual(ids('motor steuerung'), ['motor-can', 'motor-lin']);
  assert.deepEqual(ids('grund'), ['plain']);
  assert.deepEqual(ids('Motor UND NICHT LIN'), ['motor-can']);
  assert.deepEqual(ids('Getriebe ODER Motor UND NICHT LIN'), ['motor-can', 'gear']);
  assert.deepEqual(ids('(Motor OR Getriebe) AND NOT LIN'), ['motor-can']);
  assert.deepEqual(ids('"Motor Steuerung" UND timeout'), ['motor-lin']);
  assert.deepEqual(ids('"CAN FD"'), ['plain']);
  assert.deepEqual(ids('"Status UND Diagnose"'), ['plain']);
  assert.deepEqual(model, original);
});

test('boolean expressions combine with actual endpoint filters for simulated and observed sources', () => {
  for (const source of ['SIMULATED', 'OBSERVED']) {
    const model = buildSequenceDiagram([
      { event_id: 'ab', source: 'A', destination: 'B', technology: 'CAN', status: 'timeout' },
      { event_id: 'ba', source: 'B', destination: 'A', technology: 'LIN', status: 'transmitted' },
      { event_id: 'bc', source: 'B', destination: 'C', technology: 'CAN', status: 'timeout' },
    ], source);
    const search = compileSequenceSearch('CAN UND (timeout ODER rejected)');
    assert.deepEqual(model.events.filter(event => search.matches(event)
      && sequenceEventMatchesParticipants(event, new Set(['A', 'B']))).map(event => event.id), ['ab']);
  }
});

test('invalid sequence search reports syntax errors and never silently matches all events', () => {
  const event = buildSequenceDiagram([{ source: 'A', destination: 'B' }], 'OBSERVED').events[0];
  for (const query of ['Motor UND', 'ODER Motor', '(Motor ODER LIN', 'Motor)', '()', '"Motor', '""',
    'NICHT '.repeat(65) + 'Motor', 'a'.repeat(4097)]) {
    const search = compileSequenceSearch(query);
    assert.ok(search.error, query);
    assert.equal(search.matches(event), false, query);
  }
  assert.equal(compileSequenceSearch('').matches(event), true);
  assert.equal(compileSequenceSearch('"A\\\"B"').error, null);
});

test('participant filtering keeps actual TX/RX endpoints and canonical evidence for both sources', () => {
  const records = [
    { event_id: 'ab', transaction_id: 't', source: 'A', destination: 'B', time_s: 1 },
    { event_id: 'ba', transaction_id: 't', source: 'B', destination: 'A', time_s: 2 },
    { event_id: 'bc', source: 'B', destination: 'C', time_s: 3 },
    { event_id: 'cd', source: 'C', destination: 'D', time_s: 4 },
    { event_id: 'aa', source: 'A', destination: 'A', time_s: 5 },
  ];
  for (const source of ['SIMULATED', 'OBSERVED']) {
    const model = buildSequenceDiagram(records, source);
    const original = structuredClone(model);
    const ids = names => model.events.filter(event => sequenceEventMatchesParticipants(event, new Set(names))).map(event => event.id);
    assert.deepEqual(ids([]), ['ab', 'ba', 'bc', 'cd', 'aa']);
    assert.deepEqual(ids(['A']), ['ab', 'ba', 'aa']);
    assert.deepEqual(ids(['B']), ['ab', 'ba', 'bc']);
    assert.deepEqual(ids(['A', 'B']), ['ab', 'ba']);
    assert.deepEqual(ids(['A', 'B', 'C']), ['ab', 'ba', 'bc']);
    assert.deepEqual(ids(['A', 'C']), []); // No invented connection through B.
    assert.deepEqual(model, original);
  }
});

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
