import assert from 'node:assert/strict';
import test from 'node:test';
import {withWireCrossings} from './network-crossings.ts';
import {moveSceneWire} from './network-scene.ts';

const wire=(id,...pairs)=>({id,path:'',bounds:{left:0,top:0,width:300,height:200},label:{x:0,y:0},branches:pairs.map((points,i)=>({nodeId:`${id}-${i}`,portId:`${id}-${i}`,path:'',points:points.map(([x,y])=>({x,y}))}))});

test('distinct physical buses jump with an actual gap, independent of drawing order',()=>{
  const buses=[wire('A',[[0,50],[100,50]]),wire('B',[[50,0],[50,100]])];
  const before=structuredClone(buses), scene=withWireCrossings({buses});
  assert.deepEqual(scene.wireBridges,[{busId:'A',branch:0,path:'M 44 50 A 6 6 0 0 1 56 50'}]);
  assert.equal(scene.buses[0].branches[0].displayPath,'M 0 50 L 44 50 M 56 50 L 100 50');
  assert.deepEqual(scene.wireBridges,withWireCrossings({buses:[...buses].reverse()}).wireBridges);
  assert.deepEqual(buses,before);
  assert.deepEqual(withWireCrossings(scene),scene);
});
test('same bus junctions stay connected and reverse direction preserves endpoints',()=>{
  assert.deepEqual(withWireCrossings({buses:[wire('A',[[0,50],[100,50]],[[50,0],[100,0]],[[100,100],[100,100]])]}).wireBridges,[]);
  const scene=withWireCrossings({buses:[wire('A',[[100,50],[0,50]]),wire('B',[[50,0],[50,100]])]});
  assert.equal(scene.buses[0].branches[0].displayPath,'M 100 50 L 56 50 M 44 50 L 0 50');
});
test('close crossings merge; T-touch bridges the vertical path',()=>{
  let scene=withWireCrossings({buses:[wire('A',[[0,50],[100,50]]),wire('B',[[50,0],[50,100]]),wire('C',[[58,0],[58,100]])]});
  assert.deepEqual(scene.wireBridges,[{busId:'A',branch:0,path:'M 44 50 A 10 6 0 0 1 64 50'}]);
  scene=withWireCrossings({buses:[wire('A',[[0,50],[50,50]]),wire('B',[[50,0],[50,100]])]});
  assert.equal(scene.wireBridges.length,1);
  assert.equal(scene.wireBridges[0].path,'M 50 44 A 6 6 0 0 1 50 56');
});
test('drag preview adds and removes jumps without changing connectivity',()=>{
  const scene=withWireCrossings({width:500,height:500,buses:[wire('A',[[0,50],[100,50]]),wire('B',[[150,0],[150,28]],[[200,100],[150,100]])]});
  const topology={nodes:[{id:'B-0',ports:[{id:'B-0',side:'bottom'}]},{id:'B-1',ports:[{id:'B-1',side:'left'}]}],edges:[{id:'edge'}],scene};
  assert.equal(scene.wireBridges.length,0);
  const crossed=moveSceneWire(topology,'B',50);
  assert.ok(crossed.scene.wireBridges.length>0);
  assert.equal(moveSceneWire(crossed,'B',150).scene.wireBridges.length,0);
  assert.deepEqual(crossed.edges,topology.edges);
});
