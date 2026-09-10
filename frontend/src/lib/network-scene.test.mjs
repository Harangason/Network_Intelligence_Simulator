import assert from 'node:assert/strict';
import test from 'node:test';
import { busJunctions, isInlineBusBranch, moveSceneWire, previewNetworkScene } from './network-scene.ts';

const branch = (...points) => ({points: points.map(([x, y]) => ({x, y}))});

test('straight bus attachments have no arrows; side branches keep both directions', () => {
  assert.equal(isInlineBusBranch(branch([100, 0], [100, 28], [100, 28])), true);
  assert.equal(isInlineBusBranch(branch([0, 100], [100, 100])), false);
  assert.equal(isInlineBusBranch(branch([0, 0], [0, 28], [100, 28])), false);
});

test('junction dots require three distinct directions, not duplicate endpoints', () => {
  const branches = [branch([100, 0], [100, 28], [100, 28]),
    branch([0, 100], [100, 100]), branch([0, 200], [100, 200])];
  assert.deepEqual(busJunctions(branches), [{x: 100, y: 100}]);
  branches.push(branch([200, 200], [100, 200]));
  assert.deepEqual(busJunctions(branches), [{x: 100, y: 100}, {x: 100, y: 200}]);
  assert.deepEqual(busJunctions([]), []);
});

test('moving a device keeps the preview free of false inline junctions', () => {
  const gateway = {id: 'gateway', x: 0, y: 0, width: 200, height: 100, ports: [{id: 'g', side: 'bottom', offset: .5}]};
  const left = {id: 'left', x: 0, y: 200, width: 80, height: 80, ports: [{id: 'l', side: 'right', offset: .5}]};
  const right = {id: 'right', x: 200, y: 200, width: 80, height: 80, ports: [{id: 'r', side: 'left', offset: .5}]};
  const topology = {nodes: [gateway, left, right], edges: []};
  const scene = {frames: [], buses: [{label: {x: 126, y: 144}, branches: [
    {...branch([100, 100], [100, 128], [100, 128]), nodeId: 'gateway', portId: 'g'},
    {...branch([80, 240], [100, 240]), nodeId: 'left', portId: 'l'},
    {...branch([200, 240], [100, 240]), nodeId: 'right', portId: 'r'},
  ]}]};
  const before = structuredClone(scene);
  const preview = previewNetworkScene(scene, topology, {...topology, nodes: [gateway, {...left, x: -30}, right]});
  assert.deepEqual(preview.buses[0].junctions, [{x: 100, y: 240}]);
  assert.deepEqual(preview.buses[0].label, {x: 126, y: 144});
  assert.equal(isInlineBusBranch(preview.buses[0].branches[0]), true);
  assert.deepEqual(scene, before);
});

test('wire dragging preserves endpoints and orthogonal connections, including a moved frame', () => {
  const owner = {id:'owner', x:0, y:0, width:200, height:100, ports:[{id:'o', side:'bottom', offset:.5}]};
  const child = {id:'child', x:200, y:200, width:100, height:100, ports:[{id:'c', side:'left', offset:.5}]};
  const topology = {nodes:[owner, child], edges:[{id:'edge'}], scene:{width:500, height:500, frames:[{id:'owner', memberIds:['owner','child'], left:-20, top:-46, width:340, height:372}], buses:[{
    id:'bus', local:true, frameId:'owner', label:{x:120,y:144}, branches:[
      {...branch([100,100],[100,128],[100,128]), nodeId:'owner',portId:'o'},
      {...branch([200,250],[100,250]), nodeId:'child',portId:'c'}
    ]} ]}};
  const shifted = moveSceneWire(topology, 'bus', 130);
  const bent = moveSceneWire(shifted, 'bus', 290, 'c');
  assert.deepEqual(bent.nodes, topology.nodes);
  assert.deepEqual(bent.edges, topology.edges);
  assert.deepEqual(bent.scene.manualBusRoutes, {bus:{trunkX:130, branchY:{c:290}}});
  assert.deepEqual(bent.scene.buses[0].branches[1].points, [{x:200,y:250},{x:176,y:250},{x:176,y:290},{x:130,y:290}]);
  assert.equal(topology.scene.manualBusRoutes, undefined);
  const moved = {...bent, nodes:bent.nodes.map(n=>({...n, x:n.x+50, y:n.y+40}))};
  const preview = previewNetworkScene(bent.scene, bent, moved);
  assert.deepEqual(preview.manualBusRoutes, {bus:{trunkX:180, branchY:{c:330}}});
  assert.deepEqual(preview.buses[0].branches[1].points, [{x:250,y:290},{x:226,y:290},{x:226,y:330},{x:180,y:330}]);
  const clamped = moveSceneWire(topology, 'bus', 20, 'o');
  assert.equal(clamped.scene.manualBusRoutes.bus.branchY.o, 118);
});
