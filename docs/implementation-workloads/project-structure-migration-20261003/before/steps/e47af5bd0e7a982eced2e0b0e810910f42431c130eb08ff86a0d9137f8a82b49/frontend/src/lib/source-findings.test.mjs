import test from 'node:test';
import assert from 'node:assert/strict';
import {findingsAtSource,parameterIsUnverified} from './source-findings.ts';
const base={projectId:'project-a',snapshotProjectId:'project-a'};
const port={severity:'BLOCKER',code:'RATE_MISSING',message:'Rate fehlt',object_type:'HardwareNetworkInterface',object_id:'port-a'};
test('canonical object gets only its own type and identity findings',()=>{
 const findings=[port,{...port,object_id:'port-b'},{...port,object_type:'Message'}];
 assert.deepEqual(findingsAtSource(findings,{...base,objectType:'HardwareNetworkInterface',objectId:'port-a'}),[port]);
});
test('object finding cannot leak into stage-wide panel',()=>assert.deepEqual(findingsAtSource([{...port,category:'technology'}],{...base,stage:'parameters'}),[]));
test('project-stage technology finding is rendered in parameter source',()=>{
 const f={severity:'BLOCKER',code:'TECHNOLOGY_UNASSIGNED',message:'Auswahl fehlt',object_type:'WorkflowParameters',object_id:'project-a',step:'parameters'};
 assert.deepEqual(findingsAtSource([f],{...base,stage:'parameters'}),[f]);
 assert.deepEqual(findingsAtSource([{...f,object_id:'project-b'}],{...base,stage:'parameters'}),[]);
});
test('missing or foreign snapshot project cannot leak findings',()=>{
 for(const snapshotProjectId of [undefined,'project-b'])assert.deepEqual(findingsAtSource([port],{...base,snapshotProjectId,objectType:port.object_type,objectId:port.object_id}),[]);
});
test('stage mapping preserves all distinct codes and messages',()=>{
 const fs=[{severity:'ERROR',code:'A',message:'first',category:'capacity'},{severity:'ERROR',code:'A',message:'second',category:'timing'}];
 assert.deepEqual(findingsAtSource(fs,{...base,stage:'capacity_timing'}),fs);
 assert.deepEqual(findingsAtSource(fs,{...base,stage:'routing'}),[]);
});
test('explicit source step takes precedence over broad category',()=>{
 const f={severity:'ERROR',code:'A',message:'route',step:'routing',category:'network'};
 assert.deepEqual(findingsAtSource([f],{...base,stage:'routing'}),[f]);
 assert.deepEqual(findingsAtSource([f],{...base,stage:'network_editor'}),[]);
});
test('warning is included only when explicitly blocking',()=>{
 assert.deepEqual(findingsAtSource([{...port,severity:'WARNING'}],{...base,objectType:port.object_type,objectId:port.object_id}),[]);
 assert.equal(findingsAtSource([{...port,severity:'WARNING',blocking:true}],{...base,objectType:port.object_type,objectId:port.object_id}).length,1);
});
for(const value of [undefined,null,'','  '])test('missing parameter remains unverified '+JSON.stringify(value),()=>assert.equal(parameterIsUnverified({technology:'lin',bitrate:value},'bitrate','lin'),true));
for(const value of [0,false,19200])test('present value is not treated as absent '+value,()=>assert.equal(parameterIsUnverified({technology:'lin',value},'value','lin'),false));
test('other selected technology does not confirm stored values',()=>assert.equal(parameterIsUnverified({technology:'can_fd',bitrate:500000},'bitrate','lin'),true));
test('empty project has no confirmed technology despite a displayed candidate',()=>assert.equal(parameterIsUnverified({},'technology','can_fd'),true));
