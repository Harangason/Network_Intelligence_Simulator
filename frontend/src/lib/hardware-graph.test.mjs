import test from 'node:test';
import assert from 'node:assert/strict';
import { buildHardwareGraph, visibleHardwareGraph, nodePath, fitGraph2D } from './hardware-graph.ts';

const device = (id, name, kind, extra = {}) => ({ id, name, kind, x: 0, y: 0, ports: [], engineeringId: `eng-${id}`, ...extra });
const topology = {
  nodes: [device('gateway', 'Echtes Gateway', 'gateway'), device('ecu', 'Fahrersitz', 'ecu'), device('sensor', 'FrontLeftSuspensionTravel', 'sensor', { systemOwnerId: 'eng-ecu', ports: [{ id: 'p', name: 'Irreführender Name CAN FD', bus: 'lin' }] }), device('orphan', 'Abgasnachbehandlung', 'actuator')],
  edges: [{ id: 'real-edge', source: 'sensor', target: 'ecu', bus: 'lin', name: 'can-fd-S01' }],
  scene: { clusters: [{ id: 'saved-cluster', label: 'Bestätigtes Cluster' }], frames: [{ id: 'saved-frame', label: 'Bestätigter Systemrahmen', clusterId: 'saved-cluster', memberIds: ['ecu', 'sensor'] }] },
};
const functions = [{ id: 'f', name: 'Sensorwert', hardware_node_id: 'eng-sensor' }, { id: 'u', name: 'Offene Funktion', hardware_node_id: 'missing' }];
const options = { query: '', kind: '', bus: '', depth: Infinity, collapsed: new Set(), physical: true };

test('shows every real device exactly once including gateways; uses saved memberships without name inference', () => {
  const before = JSON.stringify(topology), graph = buildHardwareGraph(topology, functions, 'hardware');
  assert.deepEqual(graph.nodes.filter(n => n.hardware).map(n => n.id).sort(), topology.nodes.map(n => n.id).sort());
  assert.equal(new Set(graph.nodes.map(n => n.id)).size, graph.nodes.length);
  assert.deepEqual(nodePath(graph, 'sensor').map(n => n.name), ['Projekt-Topologie', 'Bestätigtes Cluster', 'Bestätigter Systemrahmen', 'FrontLeftSuspensionTravel']);
  assert.equal(nodePath(graph, 'orphan').at(-2).name, 'Zuordnung offen');
  assert.equal(graph.links.find(l => l.id === 'edge:real-edge').bus, 'lin');
  assert.equal(JSON.stringify(topology), before);
});
test('combined mode preserves function mappings; unresolved mappings stay unresolved', () => {
  const graph = buildHardwareGraph(topology, functions, 'combined');
  assert.equal(graph.links.find(l => l.id === 'mapping:f').target, 'sensor');
  assert.equal(graph.byId.get('function:u').kind, 'unmapped');
  assert.ok(!graph.links.some(l => l.id === 'mapping:u'));
  assert.equal(graph.nodes.filter(n => n.functionRef).length, functions.length);
  assert.equal(buildHardwareGraph(topology, functions, 'functions').nodes.filter(n => n.hardware).length, 0);
  assert.deepEqual(visibleHardwareGraph(buildHardwareGraph(topology, functions, 'functions'), { ...options, bus: 'lin' }).matches.map(n => n.id), ['function:f']);
});
test('search finds collapsed leaves with ancestor context and preserves alphabetical results', () => {
  const graph = buildHardwareGraph(topology, functions, 'hardware');
  const hidden = visibleHardwareGraph(graph, { ...options, collapsed: new Set(['view:frame:saved-frame']) });
  assert.ok(!hidden.nodes.some(n => n.id === 'sensor'));
  const found = visibleHardwareGraph(graph, { ...options, query: 'suspension', depth: 0, collapsed: new Set(['view:frame:saved-frame']) });
  assert.deepEqual(found.matches.map(n => n.id), ['sensor']);
  assert.deepEqual(found.nodes.map(n => n.id).sort(), nodePath(graph, 'sensor').map(n => n.id).sort());
  assert.deepEqual(visibleHardwareGraph(graph, { ...options, query: 'nonexistent' }).nodes, []);
});
test('filter uses actual technology and never leaves dangling links; replay depth is bounded', () => {
  const graph = buildHardwareGraph(topology, functions, 'hardware');
  const filtered = visibleHardwareGraph(graph, { ...options, bus: 'lin' });
  assert.ok(filtered.matches.some(n => n.id === 'sensor'));
  assert.equal(visibleHardwareGraph(graph, { ...options, bus: 'can_fd' }).matches.length, 0);
  for (let depth = 0; depth <= graph.maxDepth; depth++) {
    const current = visibleHardwareGraph(graph, { ...options, depth });
    assert.ok(current.nodes.every(n => n.depth <= depth));
    assert.ok(current.links.every(l => current.nodes.some(n => n.id === l.source) && current.nodes.some(n => n.id === l.target)));
  }
});
test('2D fit actually contains bounds, deterministic 3D is finite and does not alter physical coordinates', () => {
  const graph = buildHardwareGraph(topology, functions, 'combined');
  assert.deepEqual(graph.nodes.map(n => n.space), buildHardwareGraph(topology, functions, 'combined').nodes.map(n => n.space));
  assert.ok(graph.nodes.every(n => n.space.every(Number.isFinite)));
  assert.ok(graph.nodes.some(n => Math.abs(n.space[2]) > 1));
  for (const [width, height] of [[400, 560], [1200, 900]]) {
    const t = fitGraph2D(graph.nodes, width, height);
    for (const node of graph.nodes) { const x = node.x * t.scale + t.x, y = node.y * t.scale + t.y; assert.ok(x >= 0 && x <= width); assert.ok(y >= 0 && y <= height); }
  }
  assert.ok(topology.nodes.every(n => n.x === 0 && n.y === 0));
});
test('duplicate display names cannot merge IDs or cyclic physical links turn into hierarchy cycles', () => {
  const t = { nodes: [device('a', 'Motor', 'ecu'), device('b', 'Motor', 'ecu')], edges: [{ id: 'ab', source: 'a', target: 'b', bus: 'can' }, { id: 'ba', source: 'b', target: 'a', bus: 'can' }] };
  const graph = buildHardwareGraph(t, [], 'hardware');
  assert.equal(graph.nodes.filter(n => n.name === 'Motor').length, 2);
  assert.equal(graph.links.filter(l => l.kind === 'physical').length, 2);
  assert.equal(nodePath(graph, 'a').length, 3);
});
