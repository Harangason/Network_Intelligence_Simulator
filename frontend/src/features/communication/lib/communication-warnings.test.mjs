import test from 'node:test';
import assert from 'node:assert/strict';
import { communicationWarnings } from './communication-warnings.ts';

function fixture() {
  const objects = [
    { id: 'ecu', object_type: 'HardwareNode', name: 'Camera', device_type: 'ECU' },
    { id: 'target', object_type: 'HardwareNode', name: 'Diagnose', device_type: 'ECU' },
    { id: 'fn', object_type: 'Function', hardware_node_id: 'ecu' },
    { id: 'if', object_type: 'Interface', function_id: 'fn' },
    { id: 'receive', object_type: 'Interface', hardware_node_id: 'target' },
    { id: 'port', object_type: 'HardwareNetworkInterface', name: 'ETH_Camera_01', hardware_node_id: 'ecu', network_ref: 'bus', channel_index: 1 },
    { id: 'destination', object_type: 'HardwareNetworkInterface', name: 'ETH_Camera_01', hardware_node_id: 'target', network_ref: 'bus' },
    { id: 'message', name: 'CameraStatus', object_type: 'Message', interface_id: 'if', hardware_interface_id: 'port' },
    { id: 's1', object_type: 'Signal', message_id: 'message', length_bits: 10, factor: 0.1 },
    { id: 's2', object_type: 'Signal', message_id: 'message' },
    { id: 'sibling', object_type: 'Message', interface_id: 'if', hardware_interface_id: 'port' },
    { id: 'sibling-signal', object_type: 'Signal', message_id: 'sibling' },
  ];
  const topology = { nodes: [
    { engineeringId: 'ecu', ports: [{ id: 'p1', hardwareInterfaceId: 'port', physicalNetworkId: 'bus' }] },
    { engineeringId: 'target', ports: [{ id: 'p2', hardwareInterfaceId: 'destination', physicalNetworkId: 'bus' }] },
  ], edges: [{ sourcePort: 'p1', targetPort: 'p2' }] };
  const route = { id: 'route', route_code: 'RT-CAMERA', status: 'APPROVED', approval_state: 'APPROVED', validation: { valid: true },
    source: { node_id: 'ecu', interface_id: 'if', port_id: 'port', network_id: 'bus' },
    destinations: [{ node_id: 'target', interface_id: 'receive', port_id: 'destination', network_id: 'bus' }],
    payload: { message_id: 'message', signal_ids: ['s1'] } };
  const networks = [{ id: 'bus' }];
  return { objects, topology, route, networks, assess(routes = [route]) { return communicationWarnings(objects, routes, networks, topology); } };
}

test('connected canonical endpoints have no communication warning', () => {
  assert.equal(fixture().assess().size, 0);
});

test('approved route on a detached channel warns through signals, interface and function despite another connected channel', () => {
  const f = fixture();
  const broken = { id: 'old-port', object_type: 'HardwareNetworkInterface', hardware_node_id: 'ecu', name: 'ETH_Camera_01', network_ref: null };
  f.objects.push(broken);
  f.objects.find(o => o.id === 'message').hardware_interface_id = broken.id;
  f.route.source.port_id = broken.id;
  const before = structuredClone({ objects: f.objects, route: f.route });
  const warnings = f.assess();
  for (const id of ['old-port', 'message', 's1', 's2', 'if', 'fn', 'ecu']) {
    assert.ok(warnings.get(id)?.some(w => w.code === 'BUS_UNASSIGNED'), id);
  }
  assert.ok(warnings.get('s1').some(w => w.routeCode === 'RT-CAMERA'));
  assert.equal(warnings.has('sibling'), false);
  assert.equal(warnings.has('sibling-signal'), false);
  assert.deepEqual(f.objects, before.objects); // No repair, encoding change or guessed assignment.
  assert.deepEqual(f.route, before.route);
});

test('route-only error propagates to selected signals but not untransmitted sibling signals', () => {
  const f = fixture();
  f.route.source.network_id = 'old-bus';
  const warnings = f.assess();
  assert.ok(warnings.get('s1').some(w => w.code === 'ROUTE_BUS_MISMATCH'));
  for (const id of ['message', 'if', 'fn', 'ecu']) assert.ok(warnings.has(id), id);
  for (const id of ['s2', 'sibling', 'sibling-signal']) assert.equal(warnings.has(id), false, id);
  f.route.source.network_id = 'bus';
  assert.equal(f.assess().size, 0, 'repair clears derived warnings');
});

test('missing bus, port or drawn edge cannot be replaced by a matching display name', () => {
  for (const change of [
    f => { f.networks[0].id = 'renamed-id'; },
    f => { f.objects = f.objects.filter(o => o.id !== 'port'); },
    f => { f.topology.edges = []; },
  ]) {
    const f = fixture(); change(f);
    const warnings = communicationWarnings(f.objects, [f.route], f.networks, f.topology);
    assert.ok(warnings.has('message'));
    assert.ok(warnings.has('s1'));
  }
});

test('legacy drawing port aliases resolve to canonical channels; rejected routes do not contaminate current communication', () => {
  const f = fixture();
  f.route.source.port_id = 'p1';
  assert.equal(f.assess().size, 0);
  f.route.status = 'REJECTED'; f.route.source.port_id = 'deleted';
  assert.equal(f.assess().size, 0);
});

test('stored invalid assessment remains a warning until explicitly revalidated', () => {
  const f = fixture();
  f.route.validation = { valid: false, errors: [{ code: 'TIMEOUT', message: 'Timeout überschritten' }] };
  assert.match(f.assess().get('s1').find(w => w.code === 'ROUTE_REVIEW_REQUIRED').reason, /Timeout/);
});

test('function ownership detects wrong publisher even without interface.hardware_node_id', () => {
  const f = fixture();
  f.objects.find(o => o.id === 'message').hardware_interface_id = 'destination';
  assert.ok(f.assess([]).get('message').some(w => w.code === 'MESSAGE_PORT_OWNER_MISMATCH'));
});
