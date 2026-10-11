import test from 'node:test';
import assert from 'node:assert/strict';
import { networkSearchEntries, searchNetworkEntries } from './network-editor-search.ts';

const topology = {
  nodes: [
    { id: 'far-away', name: 'Kühlung', kind: 'ecu', x: 18000, y: 26000, ports: [{ name: 'Temperatur Eingang', bus: 'can_fd', physicalNetworkName: 'CAN_Klima_01' }] },
    { id: 'camera', name: 'FrontCamera', kind: 'sensor', ports: [{ name: 'Camera Anschluss', bus: 'automotive_ethernet' }] },
    { id: 'motor', name: 'Motor', kind: 'ecu', ports: [] },
    { id: 'motor-sensor', name: 'Motortemperatur', kind: 'sensor', ports: [] },
  ],
  edges: [],
  scene: { frames: [{ memberIds: ['far-away'], label: 'Klima' }], buses: [
    { id: 'internal-id', name: 'ETH_Fahrerassistenz_01', technology: 'automotive_ethernet', labelText: 'ETH 01', participantCount: 2 },
  ] },
};

test('finds offscreen devices by name, type, associated bus and port without altering topology', () => {
  const before = structuredClone(topology), entries = networkSearchEntries(topology);
  for (const query of ['kuehlung', 'KÜHLUNG', 'temperatur eingang', 'ecu klima', 'CAN-Klima 01'])
    assert.equal(searchNetworkEntries(entries, query)[0].id, 'far-away', query);
  assert.equal(searchNetworkEntries(entries, 'sensor eth')[0].id, 'camera');
  assert.deepEqual(topology, before);
});

test('exact names precede partial names and blank or missing terms do not choose a result', () => {
  const entries = networkSearchEntries(topology);
  assert.deepEqual(searchNetworkEntries(entries, 'motor').map(entry => entry.id), ['motor', 'motor-sensor']);
  for (const query of ['', '   ', '!!!', 'missing-name', 'motor camera']) assert.deepEqual(searchNetworkEntries(entries, query), []);
});

test('bus names update with the current canonical model; same names keep distinct identities', () => {
  const next = structuredClone(topology);
  next.scene.buses[0].name = 'ETH_Klima_02'; next.scene.buses[0].labelText = 'ETH_Klima_02';
  next.nodes.push({ ...next.nodes[0], id: 'second' });
  const entries = networkSearchEntries(next);
  assert.equal(searchNetworkEntries(entries, 'ETH Klima 02')[0].id, 'internal-id');
  assert.deepEqual(searchNetworkEntries(entries, 'Fahrerassistenz'), []);
  assert.equal(new Set(searchNetworkEntries(entries, 'kuehlung').map(entry => entry.key)).size, 2);
});

test('legacy views expose bus connections without a saved scene', () => {
  const entries = networkSearchEntries({ ...topology, scene: undefined, edges: [{ id: 'edge', physicalNetworkName: 'LIN_Klima_01', bus: 'lin' }] });
  assert.equal(searchNetworkEntries(entries, 'LIN_Klima_01')[0].kind, 'edge');
});
