import test from 'node:test';
import assert from 'node:assert/strict';
import { deleteNetworkSelection } from './network-deletion.ts';
const fixture=()=>({nodes:[{id:'owner',ports:[{id:'shared'}]},{id:'a',ports:[{id:'a'},{id:'free'}]},{id:'b',ports:[{id:'b'}]}],
  edges:[{id:'one',source:'owner',sourcePort:'shared',target:'a',targetPort:'a',physicalNetworkId:'bus'},
  {id:'two',source:'owner',sourcePort:'shared',target:'b',targetPort:'b',physicalNetworkId:'bus'}],scene:{manualBusRoutes:{bus:{trunkX:90}}}});
test('port deletion persists even without edges and retains scene metadata',()=>{
  const t=fixture(),before=structuredClone(t),next=deleteNetworkSelection(t,{kind:'port',nodeId:'a',portId:'free'});
  assert.deepEqual(t,before);assert.equal(next.edges.length,2);assert.equal(next.nodes[1].ports.length,1);assert.deepEqual(next.scene,t.scene);
  const connected=deleteNetworkSelection(t,{kind:'port',nodeId:'a',portId:'a'});
  assert.deepEqual(connected.edges.map(e=>e.id),['two']);assert.equal(connected.nodes.length,3);
});
test('branch and trunk selections remove exactly their incident lines, retaining ports',()=>{
  const t=fixture();
  assert.deepEqual(deleteNetworkSelection(t,{kind:'branch',busId:'bus',portId:'a'}).edges.map(e=>e.id),['two']);
  assert.equal(deleteNetworkSelection(t,{kind:'branch',busId:'bus',portId:'shared'}).edges.length,0);
  const trunk=deleteNetworkSelection(t,{kind:'bus',busId:'bus'});
  assert.equal(trunk.edges.length,0);assert.deepEqual(trunk.nodes,t.nodes);
});
