import test from 'node:test';
import assert from 'node:assert/strict';
import { selectionBounds, selectNetworkArea, alphabeticalTargets } from './network-selection.ts';

test('lasso works in either direction and includes enclosed frame contents',()=>{
  const topology={nodes:[{id:'a',kind:'ecu',x:20,y:20,width:20,height:20},{id:'s',kind:'sensor',x:200,y:200,width:20,height:20},{id:'g',kind:'gateway',x:20,y:20,width:20,height:20}],scene:{frames:[{left:10,top:10,width:50,height:50,memberIds:['a','s']}]}};
  const forward=selectionBounds({x:0,y:0},{x:100,y:100});
  assert.deepEqual(forward,selectionBounds({x:100,y:100},{x:0,y:0}));
  assert.deepEqual(selectNetworkArea(topology,forward),['a','s']);
  assert.deepEqual(selectNetworkArea(topology,{left:25,top:25,width:15,height:15}),['a']);
  assert.deepEqual(selectNetworkArea(topology,{left:0,top:0,width:1,height:1}),[]);
});
test('target lists sort German names and numbers without mutating inputs',()=>{
  const values=[{id:'3',label:'Ziel 10'},{id:'2',label:'Ziel 2'},{id:'1',label:'Änderung'}];
  assert.deepEqual(alphabeticalTargets(values).map(v=>v.id),['1','2','3']);
  assert.equal(values[0].id,'3');
});
