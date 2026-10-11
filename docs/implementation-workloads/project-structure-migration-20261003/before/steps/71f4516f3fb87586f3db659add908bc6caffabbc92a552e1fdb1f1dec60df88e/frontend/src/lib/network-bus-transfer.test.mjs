import assert from 'node:assert/strict';
import test from 'node:test';
import { busTransferTargets, transferableNodes } from './network-bus-transfer.ts';

const bus=(id,name,nodes,technology='can_fd',local=false,frameId=null)=>({id,name,branches:nodes.map(nodeId=>({nodeId})),technology,local,frameId});
const topology={nodes:[{id:'A',name:'Fahrersitz',kind:'ecu'},{id:'G',name:'Gateway',kind:'gateway'},{id:'S',name:'Sensor',kind:'sensor'}],scene:{
  clusters:[{id:'c',memberIds:['A','B','D','S']},{id:'other',memberIds:['X']}],
  buses:[bus('one','Komfort 01',['A','G']),bus('ten','Komfort 10',['B','G']),bus('two','Komfort 02',['D','G']),
    bus('foreign','Antrieb',['X','G']),bus('wrongtype','Ethernet',['B','G'],'automotive_ethernet'),
    bus('local','LIN 01',['A','S'],'lin',true,'A'),bus('local2','LIN 02',['A','B'],'lin',true,'A'),bus('different-frame','LIN 03',['D'],'lin',true,'D')]
}};
test('transfer targets use the physical bus, same cluster and type, sorted numerically',()=>{
  assert.deepEqual(busTransferTargets(topology,'one','A').map(b=>b.id),['two','ten']);
  assert.deepEqual(transferableNodes(topology,{source:'G',target:'A',physicalNetworkId:'one'}).map(n=>n.id),['A']);
  assert.deepEqual(busTransferTargets(topology,'one','missing'),[]);
});
test('a local bus move preserves the owner and offers only its other local buses',()=>{
  assert.deepEqual(transferableNodes(topology,{source:'A',target:'S',physicalNetworkId:'local'}).map(n=>n.id),['S']);
  assert.deepEqual(busTransferTargets(topology,'local','S').map(b=>b.id),['local2']);
});
