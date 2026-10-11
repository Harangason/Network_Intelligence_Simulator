import assert from 'node:assert/strict';
import test from 'node:test';

test('signal dictionaries preserve decoded numeric values and discrete states', () => {
  const event = eventFromRecord({time_s: 12.5, signals: {
    Temperature: {physical_value: 34.2, value: 342, unit: 'degC', quality: 'VALID'},
    MotorRPM: {value: 1500, unit: 'rpm'}, MotorCurrent: {value: 2.1, unit: 'A'},
    OperatingState: 'ACTIVE', HealthState: 'OK',
  }}, 0);
  assert.equal(event.signals.length, 5);
  assert.equal(event.signals[0].value, 34.2);
  assert.equal(event.signals[0].unit, 'degC');
  assert.equal(event.signals[3].value, 'ACTIVE');
  assert.equal(event.signals[4].value, 'OK');
});
import { eventFromRecord, parseTraceText, traceMessagePresentation, traceSignalInventory, traceEventFindings, MAX_IMPORT_BYTES } from './trace-records.ts';

test('trace names resolve from the exact frozen snapshot while source IDs remain intact', () => {
  const id = '8a3254f8-8244-45e6-8c0e-634348d56cd4';
  const event = eventFromRecord({ time_s: 0, message_ids: [id] }, 0);
  const original = structuredClone(event);
  const resolved = traceMessagePresentation(event, { engineering_model: { messages: [{ id, name: 'Diagnose Status' }] } });
  assert.equal(resolved.message, 'Diagnose Status');
  assert.deepEqual(resolved.original.message_ids, [id]);
  assert.deepEqual(event, original);
  assert.equal(traceMessagePresentation(event).message, 'Nachricht ohne Klartextnamen');
  assert.equal(traceMessagePresentation(event, { engineering_model: { messages: [{ id: 'another', name: 'Wrong model' }] } }).message, 'Nachricht ohne Klartextnamen');
  const named = eventFromRecord({ time_s: 0, message_name: 'Explicit Trace Name', message_ids: [id] }, 0);
  assert.equal(traceMessagePresentation(named, { engineering_model: { messages: [{ id, name: 'Other name' }] } }).message, 'Explicit Trace Name');
  assert.equal(traceMessagePresentation(eventFromRecord({ time_s: 0, message: 'Imported Status', message_ids: [id] }, 0)).message, 'Imported Status');
});

test('a loaded window exposes every decoded channel including channels beyond 128', () => {
  const signals = Array.from({ length: 317 }, (_, i) => ({ signal_id: `signal-${i}`, signal: `Signal ${i}`, value: i, unit: 'V' }));
  const frames = Array.from({ length: 6 }, (_, i) => eventFromRecord({ time_s: i, signals: signals.slice(i * 64, (i + 1) * 64) }, i));
  assert.equal(traceSignalInventory([...frames, frames[0]]).length, 317);
  assert.equal(traceSignalInventory(frames).at(-1).name, 'Signal 316');
  assert.equal(frames.flatMap(frame => frame.refs.filter(ref => ref.object_type === 'Signal')).length, 317);
});

test('fault chart findings preserve explicit source categories and missing decoders do not fabricate errors', () => {
  const event = eventFromRecord({ time_s: 0, faults: '["BUS_OFF","BUS_OFF","MESSAGE_LOSS"]', status: 'dropped', receiver_action: 'REJECT', deadline_status: 'FAIL' }, 0);
  assert.deepEqual(traceEventFindings(event), ['BUS_OFF', 'MESSAGE_LOSS', 'Status: dropped', 'Empfänger: REJECTED', 'deadline_status: FAIL']);
  assert.deepEqual(traceEventFindings(eventFromRecord({ time_s: 0, payload_hex: '01 02' }, 0)), []);
});

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
  assert.equal(MAX_IMPORT_BYTES, 500 * 1024 * 1024);
  assert.throws(() => parseTraceText(' '.repeat(MAX_IMPORT_BYTES + 1)), /500 MiB/);
  assert.equal(eventFromRecord({ time_s: 0, signals: Array.from({ length: 100 }, (_, value) => ({ value })) }, 0).signals.length, 64);
});

test('event identity is independent of window offset and preserves explicit source IDs', () => {
  const raw = {time_s:12.502, route_id:'egress', sequence:6, sender_interface:'gateway', network:'ETH'};
  assert.equal(eventFromRecord(raw, 0).id, eventFromRecord(raw, 80).id);
  assert.equal(eventFromRecord({...raw,event_id:'canonical-event'}, 5).id, 'canonical-event');
  assert.notEqual(eventFromRecord(raw, 0).id, eventFromRecord({...raw,route_id:'ingress'}, 0).id);
});
