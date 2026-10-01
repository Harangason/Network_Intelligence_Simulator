import test from 'node:test';
import assert from 'node:assert/strict';
import { buildHardwareGraph, visibleHardwareGraph, nodePath, fitGraph2D, searchTerms, graphLinkEndpoints, graphLinkPath, graphNodeRadius, hasCommunicationFlow, communicationColor } from './hardware-graph.ts';

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
  assert.deepEqual(nodePath(graph, 'sensor').map(n => n.name), ['Projekt-Topologie', 'Bestätigtes Cluster', 'Bestätigter Systemrahmen', 'Fahrersitz', 'FrontLeftSuspensionTravel']);
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

test('UND searches multiple node names together, respects quoted UND and reports missing terms', () => {
  assert.deepEqual(searchTerms('"ECU A" UND ECU B und "Licht und Sicht"'), ['ecu a', 'ecu b', 'licht und sicht']);
  const graph = buildHardwareGraph(topology, functions, 'hardware');
  const result = visibleHardwareGraph(graph, { ...options, query: 'Fahrersitz und FrontLeftSuspensionTravel und fehlt' });
  assert.deepEqual(result.matches.map(n => n.id), ['ecu', 'sensor']);
  assert.deepEqual(result.missingTerms, ['fehlt']);
  assert.ok(result.links.some(l => l.kind === 'physical'));
  assert.deepEqual(searchTerms(' und  UND '), []);
});

test('controller click can fold owned peripherals, depth-limited and searched branches can be opened independently', () => {
  const graph = buildHardwareGraph(topology, functions, 'combined');
  assert.equal(graph.byId.get('sensor').parentId, 'ecu');
  assert.equal(graph.byId.get('function:f').parentId, 'sensor');
  assert.ok(!visibleHardwareGraph(graph, { ...options, collapsed: new Set(['ecu']) }).nodes.some(n => n.id === 'sensor'));
  const opened = visibleHardwareGraph(graph, { ...options, depth: 0, expanded: new Set(['view:root']) });
  assert.ok(opened.nodes.length > 1);
  assert.ok(opened.nodes.every(n => n.depth <= 1));
  const foldedSearch = visibleHardwareGraph(graph, { ...options, query: 'suspension', searchCollapsed: new Set(['ecu']) });
  assert.ok(foldedSearch.matches.some(n => n.id === 'sensor'));
  assert.ok(!foldedSearch.nodes.some(n => n.id === 'sensor'));
  const otherFrame = structuredClone(topology);
  otherFrame.scene.frames[0].memberIds = ['ecu'];
  otherFrame.scene.frames.push({ id: 'different-zone', label: 'Andere Zone', clusterId: 'saved-cluster', memberIds: ['sensor'] });
  assert.equal(buildHardwareGraph(otherFrame, [], 'hardware').byId.get('sensor').parentId, 'view:frame:different-zone');
});

test('lines connect facing surfaces without inward curves in every quadrant and in 3D', () => {
  const graph = buildHardwareGraph(topology, [], 'hardware');
  for (const [dx, dy, dz] of [[300, 100, 200], [-300, 100, -200], [300, -100, -200], [-300, -100, 200], [0, 300, 0]]) {
    const a = { ...graph.byId.get('ecu'), x: 400, y: 500, space: [400, 500, 300] };
    const b = { ...graph.byId.get('sensor'), x: 400 + dx, y: 500 + dy, space: [400 + dx, 500 + dy, 300 + dz] };
    for (const three of [false, true]) {
      const ends = graphLinkEndpoints(a, b, three, a.id), start = three ? a.space : [a.x, a.y, 0], end = three ? b.space : [b.x, b.y, 0];
      assert.ok(Math.abs(Math.hypot(...ends.source.map((v, i) => v - start[i])) - graphNodeRadius(a, three) * (three ? 1.6 : 1)) < 1e-8);
      assert.ok(Math.abs(Math.hypot(...ends.target.map((v, i) => v - end[i])) - graphNodeRadius(b, three)) < 1e-8);
      assert.ok(ends.source.every((v, i) => v >= Math.min(start[i], end[i]) && v <= Math.max(start[i], end[i])));
    }
    assert.match(graphLinkPath(a, b, 'hierarchy'), /^M [-\d.]+ [-\d.]+ L [-\d.]+ [-\d.]+$/);
    assert.ok(graphLinkEndpoints(a, a).source.every(Number.isFinite));
  }
});

const route = (id, source, target, extra = {}) => ({
  id, route_code: id, name: `Wert ${id}`, status: 'ACTIVE', approval_state: 'APPROVED', validation: { valid: true },
  source: { node_id: source, protocol: 'CAN_FD' }, destinations: [{ node_id: target }], payload: { message_id: 'message', signal_ids: [] }, timing: { cycle_time_ms: 20 }, ...extra,
});
const communication = routes => ({ routes, interfaces: [], relations: [] });

test('message routes establish sender direction using canonical IDs; physical bus direction creates no traffic', () => {
  const t = { nodes: [device('motor', 'Motor', 'ecu'), device('hmi', 'HMI', 'ecu')], edges: [{ id: 'bus', source: 'hmi', target: 'motor', bus: 'can_fd' }] };
  const data = communication([route('r1', 'eng-motor', 'eng-hmi'), route('r2', 'eng-motor', 'eng-hmi'), route('old', 'eng-hmi', 'eng-motor', { status: 'OUTDATED' }), route('rejected', 'eng-motor', 'eng-hmi', { status: 'REJECTED' }), route('scaffold', 'eng-hmi', 'eng-motor', { payload: { signal_ids: [] } })]);
  const before = JSON.stringify([t, data]);
  const graph = buildHardwareGraph(t, [], 'hardware', data), links = graph.links.filter(l => l.kind === 'communication');
  assert.equal(links.length, 2);
  const forward = links.find(l => l.source === 'motor');
  assert.equal(forward.target, 'hmi'); assert.equal(forward.directed, true);
  assert.deepEqual(forward.communications.map(c => c.id), ['r1', 'r2']);
  const reverse = links.find(l => l.source === 'hmi');
  assert.equal(reverse.communications[0].active, false); assert.equal(reverse.communications[0].status, 'Weg veraltet');
  assert.equal(visibleHardwareGraph(graph, { ...options, communication: false }).links.filter(l => l.kind === 'communication').length, 0);
  assert.equal(JSON.stringify([t, data]), before);
});

test('function route endpoints require exact interface/function ownership; unknown relationship direction stays static', () => {
  const fns = [{ id: 'fm', name: 'Drehzahl senden', hardware_node_id: 'eng-motor' }, { id: 'fh', name: 'Drehzahl anzeigen', hardware_node_id: 'eng-hmi' }];
  const t = { nodes: [device('motor', 'Motor', 'ecu'), device('hmi', 'HMI', 'ecu')], edges: [] };
  const data = { interfaces: [{ id: 'im', function_id: 'fm' }, { id: 'ih', function_id: 'fh' }], routes: [route('r', 'eng-motor', 'eng-hmi', { source: { node_id: 'eng-motor', interface_id: 'im' }, destinations: [{ node_id: 'eng-hmi', interface_id: 'ih' }] })], relations: [] };
  let graph = buildHardwareGraph(t, fns, 'functions', data);
  assert.deepEqual(graph.links.filter(l => l.kind === 'communication').map(l => [l.source, l.target]), [['function:fm', 'function:fh']]);
  data.interfaces[1].function_id = 'fm';
  assert.equal(buildHardwareGraph(t, fns, 'functions', data).links.filter(l => l.kind === 'communication').length, 0);
  data.routes = [];
  data.relations = [{ id: 'rel', source_type: 'HardwareNode', source_id: 'eng-motor', target_type: 'HardwareNode', target_id: 'eng-hmi', relation_type: 'COMMUNICATES_WITH', attributes: {} }];
  graph = buildHardwareGraph(t, [], 'hardware', data);
  assert.equal(graph.links.find(l => l.kind === 'communication').directed, false);
  assert.equal(graph.links.find(l => l.kind === 'communication').communications[0].active, false);
  data.relations[0].attributes.direction = 'TARGET_TO_SOURCE';
  assert.equal(buildHardwareGraph(t, [], 'hardware', data).links.find(l => l.kind === 'communication').source, 'hmi');
  data.relations[0].attributes.direction = 'BIDIRECTIONAL';
  assert.equal(buildHardwareGraph(t, [], 'hardware', data).links.filter(l => l.kind === 'communication').length, 2);
});

test('overview includes application and diagnostic communication; filtering only takes a subset', () => {
  const t = { nodes: [device('motor', 'Motorsteuerung', 'ecu'), device('kombi', 'Kombiinstrument', 'ecu'), device('diagnose', 'Diagnose', 'ecu')], edges: [] };
  const data = communication([route('display', 'eng-motor', 'eng-kombi'), route('diagnostics', 'eng-motor', 'eng-diagnose')]);
  const graph = buildHardwareGraph(t, [], 'hardware', data);
  const all = visibleHardwareGraph(graph, options).links.filter(l => l.kind === 'communication');
  const filtered = visibleHardwareGraph(graph, { ...options, query: 'motor und kombi' }).links.filter(l => l.kind === 'communication');
  assert.equal(all.length, 2);
  assert.equal(filtered.length, 1);
  assert.equal(filtered[0], all.find(l => l.target === 'kombi'));
});

test('modeled direction animates even while physical validation is pending; colors retain warnings', () => {
  const t = { nodes: [device('motor', 'Motor', 'ecu'), device('hmi', 'HMI', 'ecu')], edges: [{ id: 'wire', source: 'motor', target: 'hmi', bus: 'can_fd' }] };
  for (const extra of [{ validation: null }, { status: 'OUTDATED' }, { validation: { valid: false } }]) {
    const graph = buildHardwareGraph(t, [], 'hardware', communication([route('r', 'eng-motor', 'eng-hmi', extra)]));
    const edge = graph.links.find(l => l.kind === 'communication');
    assert.equal(hasCommunicationFlow(edge), true);
    assert.equal(communicationColor(edge), '#e5a65d');
    assert.equal(hasCommunicationFlow({ ...edge, directed: false }), false);
    assert.equal(hasCommunicationFlow(graph.links.find(l => l.kind === 'physical')), false);
  }
});
