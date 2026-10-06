import test from 'node:test';
import assert from 'node:assert/strict';
import { recipientRecommendations, recipientDeviceGroup } from './routing-recipient-recommendations.ts';
const message = { id: 'message', name: 'State', routingScope: { consumer_refs: ['function'] } };
const interfaces = [{ id: 'interface', hardware_node_id: 'receiver', function_id: 'function' }];
const route = (target, overrides = {}) => ({ source: { node_id: 'sender' }, payload: { message_ids: ['message'], signal_ids: [] }, destinations: [{ node_id: target }], route_code: target, validation: { valid: true }, status: 'READY_FOR_REVIEW', approval_state: 'PENDING', ...overrides });
test('only explicit partners and stored confidence above 95 percent become recommendations', () => {
  const result = recipientRecommendations('sender', [message], [route('high', { confidence: .96 }), route('limit', { confidence: .95 }), route('unknown'), route('approved', { approval_state: 'APPROVED' }), route('unrelated', { source: { node_id: 'other' }, confidence: 1 }), route('other-payload', { payload: { message_ids: ['other'] }, confidence: 1 }), route('outdated', { confidence: 1, status: 'OUTDATED' })], interfaces);
  assert.deepEqual([...result.keys()].sort(), ['approved', 'high', 'receiver']);
  assert.equal(result.get('receiver').confidence, null, 'A declared partner is evidence, not a fabricated probability');
  assert.equal(result.get('high').confidence, .96);
});
test('ambiguous function allocation is not a high confidence recommendation; signal-only routes resolve their parent', () => {
  const ambiguous = [...interfaces, { id: 'second', hardware_node_id: 'other', function_id: 'function' }];
  assert.equal(recipientRecommendations('sender', [message], [], ambiguous).size, 0);
  const result = recipientRecommendations('sender', [{ ...message, routingScope: { consumer_refs: [] } }], [route('signal-target', { approval_state: 'APPROVED', payload: { signal_ids: ['signal'] } })], [], [{ id: 'signal', message_id: 'message' }]);
  assert.ok(result.has('signal-target'));
});
test('device groups keep sensors, actuators and controller types distinct', () => {
  assert.equal(recipientDeviceGroup({ device_type: 'ECU' }), 'ECUs & Gateways');
  assert.equal(recipientDeviceGroup({ device_type: 'Gateway' }), 'ECUs & Gateways');
  assert.equal(recipientDeviceGroup({ device_type: 'SensorController' }), 'Sensoren');
  assert.equal(recipientDeviceGroup({ device_type: 'ActuatorController' }), 'Aktoren');
});
test('a historical approval or high score cannot override the current local recipient contract', () => {
  const local = { ...message, routingScope: { consumer_refs: ['function'], restricted: true } };
  const result = recipientRecommendations('sender', [local], [route('outsider', { approval_state: 'APPROVED', confidence: 1 })], interfaces);
  assert.ok(result.has('receiver')); assert.ok(!result.has('outsider'));
});
