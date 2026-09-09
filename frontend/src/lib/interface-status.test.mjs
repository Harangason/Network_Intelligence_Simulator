import test from 'node:test';
import assert from 'node:assert/strict';
import { interfaceTraffic, physicalBindingStatus, missingCommandSignals } from './interface-status.ts';

test('receiver-only interface retains references without taking message ownership', () => {
  const route = { id: 'r', status: 'APPROVED', source: { interface_id: 'sender' }, destinations: [{ interface_id: 'receiver' }], payload: { message_id: 'm', message_ids: ['m'] } };
  assert.deepEqual(interfaceTraffic('receiver', [route]).map(t => [t.direction, t.messageIds]), [['RX', ['m']]]);
  assert.equal(interfaceTraffic('receiver', [{ ...route, status: 'REJECTED' }]).length, 0);
  assert.equal(route.source.interface_id, 'sender');
});

test('binding state does not pretend to be a runtime status', () => {
  assert.equal(physicalBindingStatus({ network_ref: 'bus', status: 'UNMAPPED' }), 'Bus zugeordnet');
  assert.equal(physicalBindingStatus({ network_ref: null, status: 'ACTIVE' }), 'Bus fehlt');
  assert.equal(physicalBindingStatus({ network_ref: 'bus', status: 'ERROR' }), 'Bus zugeordnet · ERROR');
});

test('command requirement clears only with signal definitions belonging to that message', () => {
  const message = { object_type: 'Message', id: 'command', configuration: { transport_unit: { provenance: { generator: 'wizard-local-actuator-command' } } } };
  assert.equal(missingCommandSignals(message, [{ message_id: 'feedback' }]), true);
  assert.equal(missingCommandSignals(message, [{ message_id: 'command' }]), false);
});
