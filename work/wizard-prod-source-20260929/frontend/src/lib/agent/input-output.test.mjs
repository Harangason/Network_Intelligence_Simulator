import assert from 'node:assert/strict';
import {test} from 'node:test';
import {visualizationSchema, outputEnvelopeSchema, diagramPositions} from './input-output.ts';
const view = {visualization_type:'NETWORK_DIAGRAM',purpose:'Architektur',source_revision:'v',
  nodes:[{id:'a',label:'A',object_type:'Function'},{id:'b',label:'B',object_type:'HardwareNode'}],
  relationships:[{source:'a',target:'b',label:'läuft auf',evidence_ref:'r'}]};
test('diagram uses only existing objects and positions are finite', () => {
  const positions = diagramPositions(visualizationSchema.parse(view));
  assert.ok(positions.get('a').x < positions.get('b').x);
  assert.equal(visualizationSchema.safeParse({...view, relationships:[{source:'a',target:'missing',evidence_ref:'r'}]}).success,false);
});
test('visualizations do not accept executable UI or CSS', () => {
  assert.equal(visualizationSchema.safeParse({...view,css:'body {display:none}'}).success,false);
  assert.equal(outputEnvelopeSchema.safeParse({schema_version:1,output_id:'o',output_type:'VISUALIZATION',status:'CURRENT',project_ref:'p',run_ref:'r',visualization:view}).success,true);
});
