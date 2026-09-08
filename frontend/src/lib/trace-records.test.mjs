import assert from 'node:assert/strict';
import test from 'node:test';
import { eventFromRecord, parseTraceText, MAX_IMPORT_BYTES } from './trace-records.ts';

test('IPv6 project addresses and physical TX/RX ports survive JSONL and CSV projection', () => {
  const ethernet = { ip_version: 6, transport_protocol: 'udp', source_port: 1234, destination_ports: [5000],
    source: { port_id: 'sensor-p1', ip: '2001:db8::10', ip_provenance: 'configured' },
    destinations: [{ port_id: 'ecu-p2', ip: '2001:db8::20', ip_provenance: 'configured' }] };
  const event = eventFromRecord({ time_s: 0, ethernet }, 0);
  assert.match(event.ipContext, /IPv6 \/ UDP/);
  assert.match(event.ipContext, /TX sensor-p1/);
  assert.match(event.ipContext, /RX ecu-p2/);
  assert.match(event.ipContext, /2001:db8::20/);
  assert.equal(eventFromRecord({ time_s: 0, ethernet: JSON.stringify(ethernet) }, 0).ipContext, event.ipContext);
});

test('universal trace preserves all decoded channels and canonical source context', () => {
  const event = eventFromRecord({ time_s: 0, route_id: 'runtime-route', route_ref: 'route', source_name: 'ECU', sender_hardware: 'node', source_logical_address: '0x0001',
    destination_names: ['Controller'], signals: [{ signal_id: 's1', signal: 'RPM', value: 1500, unit: 'rpm' },
      { signal_id: 's2', signal: 'Mode', value: 'ACTIVE' }, { signal: 'Enabled', value: false }] }, 0);
  assert.equal(event.timestamp, 0); assert.equal(event.signals.length, 3);
  assert.equal(event.signals[1].value, 'ACTIVE'); assert.equal(event.signals[2].value, false);
  assert.equal(event.source, 'ECU (0x0001)');
  assert.ok(event.refs.some(ref => ref.object_type === 'Route' && ref.id === 'route'));
});
test('CSV imports quoted JSON signal arrays without splitting their commas', () => {
  const signals = JSON.stringify([{ signal_id: 'temp', signal: 'Temperature', value: 23.5, unit: 'degC' }]);
  const csv = 'time_s,source,signals\n0,"ECU, Drive","' + signals.replaceAll('"', '""') + '"';
  const [event] = parseTraceText(csv);
  assert.equal(event.source, 'ECU, Drive'); assert.equal(event.signals[0].value, 23.5);
});
test('missing timestamps and malformed CSV never become invented times', () => {
  assert.throws(() => parseTraceText('[{"source":"ECU"}]'), /Zeitstempel/);
  assert.throws(() => parseTraceText('time_s,source\n,"ECU"'), /Zeitstempel/);
  assert.throws(() => parseTraceText('time_s,source\n0,"ECU'), /geschlossenes/);
  assert.throws(() => parseTraceText('time_s,source\n0,ECU,extra'), /Spaltenzahl/);
});
test('JSON, JSONL and imports remain bounded', () => {
  assert.equal(parseTraceText(JSON.stringify({ events: [{ time_s: 1 }] }))[0].timestamp, 1);
  assert.equal(parseTraceText(Array.from({ length: 3000 }, (_, time_s) => JSON.stringify({ time_s })).join('\n')).length, 2000);
  assert.throws(() => parseTraceText(' '.repeat(MAX_IMPORT_BYTES + 1)), /5 MiB/);
  assert.equal(eventFromRecord({ time_s: 0, signals: Array.from({ length: 100 }, (_, value) => ({ value })) }, 0).signals.length, 64);
});
