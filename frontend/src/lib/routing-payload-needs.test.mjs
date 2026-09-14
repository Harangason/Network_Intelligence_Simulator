import test from 'node:test';
import assert from 'node:assert/strict';
import { payloadCandidates, readPayloadRequirements, signalDomain, signalPurpose, proposePayload } from './routing-payload-needs.ts';

const make = (id, meaning, type, unit, values = {}) => ({ id, name: id, message_id: 'output', semantic: { meaning, semantic_type: type }, data: { enum_values: values }, configuration: {}, unit });
const state = make('CoolingStatus', 'Betriebszustand', 'STATE', 'code', { OFF: 0, ACTIVE: 3, ERROR: 5 });
const health = make('CoolingHealth', 'Diagnosezustand', 'ENUM', 'code', { OK: 0, FAILED: 3 });
const count = make('CoolingAliveCounter', 'Lebendzähler', 'COUNTER', 'count');
const messages = [{ id: 'output', name: 'Cooling', dlc: 3 }];

test('data needs propose existing states and health with their exact encodings', () => {
  const signals = [state, health, count], snapshot = JSON.stringify(signals);
  const result = payloadCandidates(messages, signals, { text: 'an aus und fehler', categories: ['state', 'health'] });
  assert.equal(result.length, 1);
  assert.deepEqual(result[0].matchedSignals.map(s => s.id), ['CoolingStatus', 'CoolingHealth']);
  assert.deepEqual(result[0].allSignals.map(s => s.id), ['CoolingStatus', 'CoolingHealth', 'CoolingAliveCounter']);
  assert.equal(result[0].message.dlc, 3, 'Need selection does not reduce frame size');
  assert.equal(signalDomain(state), 'OFF = 0 · ACTIVE = 3 · ERROR = 5');
  assert.equal(JSON.stringify(signals), snapshot);
});

test('missing measurements produce an explicit empty result, not invented data', () => {
  assert.deepEqual(payloadCandidates(messages, [state, health], { text: 'Temperatur', categories: [] }), []);
  assert.deepEqual(payloadCandidates(messages, [state, health], { text: '', categories: ['measurement'] }), []);
  assert.deepEqual(payloadCandidates([], [state], { text: '', categories: [] }), []);
});

test('physical meaning outranks a Status name and counters are not measurements', () => {
  assert.equal(signalPurpose(make('TemperatureStatus', 'Temperatur', 'NUMERIC', '°C')), 'measurement');
  assert.equal(signalPurpose(count), null);
  assert.equal(signalPurpose({ ...state, configuration: { generation_role: 'COMMAND' } }), 'command');
});

test('saved requirements tolerate legacy absent data and reject unknown category keys', () => {
  assert.deepEqual(readPayloadRequirements(undefined), { text: '', categories: [] });
  assert.deepEqual(readPayloadRequirements({ text: 'Fehler', categories: ['health', 'invalid', 'health', 'constructor'] }), { text: 'Fehler', categories: ['health'] });
});

test('separate output messages are offered as partial coverage for a combined need', () => {
  const result = payloadCandidates([...messages, { id: 'health', name: 'Health' }], [state, { ...health, message_id: 'health' }], { text: '', categories: ['state', 'health'] });
  assert.equal(result.length, 2);
  assert.equal(result.find(c => c.message.id === 'output').missingCategories[0], 'health');
  assert.equal(result.find(c => c.message.id === 'health').missingCategories[0], 'state');
});

test('payload generation creates an independent editable draft preserving canonical codes and frame size', () => {
  const input = [{ ...messages[0], interface_id: 'interface', routingScope: { scope: 'FUNCTION_OUTPUT' } }];
  const snapshot = JSON.stringify([input, state, health, count]);
  const draft = proposePayload(input, [state, health, count], { text: '', categories: [] }, 'interface', [], 'context');
  assert.deepEqual(draft.messageIds, ['output']);
  assert.deepEqual(draft.signalIds, ['CoolingStatus', 'CoolingHealth']);
  draft.signalIds.pop(); draft.requirements.text = 'Nur Betriebszustand';
  assert.equal(JSON.stringify([input, state, health, count]), snapshot);
  assert.equal(draft.contextKey, 'context');
});
test('draft generation leaves unavailable data open and never proposes receive-only traffic', () => {
  assert.deepEqual(proposePayload(messages, [state], { text: 'Temperatur', categories: [] }, '', [], '').messageIds, []);
  assert.deepEqual(proposePayload([{ ...messages[0], direction: 'rx' }], [state], { text: '', categories: [] }, '', [], '').messageIds, []);
});
