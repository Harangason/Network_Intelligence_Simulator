import test from 'node:test';
import assert from 'node:assert/strict';
import { planNetworkConnection } from './network-connections.ts';

const port = (id, network, bus='can_fd') => ({id, name:network, bus, physicalNetworkId:network, hardwareInterfaceId:'hwi-'+id});
const endpoint = id => ({kind:'port', nodeId:id, portId:id});
const bus = {kind:'bus', busId:'local'};
function fixture() { return {nodes:[
  {id:'sensor', name:'Bestehend', kind:'sensor', ports:[port('sensor','local')]},
  {id:'ecu', name:'Fahrerassistenz', kind:'ecu', ports:[port('ecu','local')]},
  {id:'test', name:'Test', kind:'sensor', ports:[port('test','spare')]},
  {id:'other', kind:'ecu', ports:[port('other','other-bus')]},
  {id:'wrong', kind:'sensor', ports:[port('wrong','lin','lin')]},
  ],edges:[{id:'old', source:'ecu', sourcePort:'ecu', target:'sensor', targetPort:'sensor', physicalNetworkId:'local'},
           {id:'other-edge',source:'other',sourcePort:'other',target:'outside',targetPort:'outside',physicalNetworkId:'other-bus'}],
  scene:{buses:[{id:'local',name:'CAN FD 01',frameId:'ecu'}]}}; }

test('free sensor attaches to its controller bus in either direction and retains channel identity',()=>{
  for(const [from,to] of [[endpoint('test'),bus],[bus,endpoint('test')],[endpoint('test'),endpoint('ecu')],[endpoint('ecu'),endpoint('test')]]) {
    const t=fixture(), before=structuredClone(t), plan=planNetworkConnection(t,from,to,'new');
    assert.deepEqual(t,before);
    assert.equal(plan.edge.physicalNetworkId,'local');
    assert.deepEqual(new Set([plan.edge.source,plan.edge.target]),new Set(['test','ecu']));
    const p=plan.nodes.find(n=>n.id==='test').ports[0];
    assert.equal(p.hardwareInterfaceId,'hwi-test'); assert.equal(p.physicalNetworkId,'local');
    assert.deepEqual(plan.nodes.find(n=>n.id==='other'),before.nodes.find(n=>n.id==='other'));
  }
});
test('wrong technology, duplicate membership, self connection and bus merge are rejected',()=>{
  assert.throws(()=>planNetworkConnection(fixture(),endpoint('wrong'),bus,'x'),/Bustypen/);
  assert.throws(()=>planNetworkConnection(fixture(),endpoint('sensor'),bus,'x'),/bereits/);
  assert.throws(()=>planNetworkConnection(fixture(),endpoint('test'),endpoint('test'),'x'),/selben Gerät/);
  assert.throws(()=>planNetworkConnection(fixture(),endpoint('other'),bus,'x'),/nicht zusammengeführt/);
  const duplicate=fixture();duplicate.nodes[0].ports.push(port('second','spare-2'));
  assert.throws(()=>planNetworkConnection(duplicate,{kind:'port',nodeId:'sensor',portId:'second'},bus,'x'),/bereits an den Bus/);
});
test('two free persisted ports get one shared network, not two inconsistent singleton IDs',()=>{
  const t=fixture();t.nodes.push({id:'free',kind:'sensor',ports:[port('free','free-network')]});
  const p=planNetworkConnection(t,endpoint('test'),endpoint('free'),'new');
  assert.equal(p.edge.physicalNetworkId,'free-network');
  assert.equal(p.nodes.find(n=>n.id==='test').ports[0].physicalNetworkId,'free-network');
});
