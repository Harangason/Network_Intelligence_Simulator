// Pure components inside the exact deployed image; no API calls or project writes.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {extractEngineeringSpecification} from 'file:///app/frontend/src/features/agent/lib/engineering-specification.ts';
import {reviewDocumentEquipment} from 'file:///app/frontend/src/features/agent/lib/document-clarification.ts';

const build = JSON.parse(readFileSync('/app/backend/nis/app/build-info.json', 'utf8'));
assert.equal(build.source_sha256, process.env.NIS_PROBE_EXPECTED_SOURCE);
const raw = readFileSync('/app/frontend/e2e/fixtures/document-preview-example.txt');
const hash = createHash('sha256').update(raw).digest('hex');
assert.equal(hash, '32c864c91ac85c2884ef0c3c9e62456e6ade59cc2a22cae384bdfe5a2e2eff60');
const source = raw.toString('utf8');
const checks = [];
for (const text of [source, '\n- Aufgaben-Anlage: neu 9.txt (text/plain, 11 KB)\n' + source]) {
  const preview = extractEngineeringSpecification(text, {}, 'automotive', false, {preview: true});
  assert.equal(preview.documentReviewRequired, true);
  assert.deepEqual(preview.chains, []);
  assert.deepEqual(preview.targetCounts, {sensors:100,actuators:100,ecus:50,gateways:1,explicit:true});
}
checks.push('exact_source_and_attachment_preview_require_review_without_devices');
const structured = extractEngineeringSpecification('Controller: PLC1\nSensor: Encoder1\n- Geräteanschlüsse: {"PLC1":"EtherCAT","Encoder1":"EtherCAT"}', {}, 'industrial_automation', false, {preview:true});
assert.notEqual(structured.documentReviewRequired, true);
assert.deepEqual([...new Set(structured.chains.map(c=>c.hardware_name))].sort(), ['Encoder1','PLC1']);
assert.ok(structured.chains.every(c=>c.interface_type==='EtherCAT'));
checks.push('explicit_nonautomotive_request_preserved');
const typed = '# Beispielprojekt Montage\n## Architektur\nController Alpha\nSensor S1';
const components = [
  {name:'Alpha',kind:'INSTANCE',role:'CONTROLLER',quantity:1,source_quote:'Controller Alpha',source_context:['Beispielprojekt Montage','Architektur']},
  {name:'S1',kind:'INSTANCE',role:'SENSOR',quantity:1,source_quote:'Sensor S1',source_context:['Beispielprojekt Montage','Architektur']},
];
const review = reviewDocumentEquipment(typed, {interpretation:{components,technologies:[]}}, {}, false);
const reviewed = extractEngineeringSpecification(typed+'\n- Dokument-Geräte: '+JSON.stringify(review), {}, 'custom', false, {preview:true});
assert.notEqual(reviewed.documentReviewRequired,true);
assert.deepEqual([...new Set(reviewed.chains.map(c=>c.hardware_name))].sort(), ['Alpha','S1']);
checks.push('typed_reviewed_inventory_preserved');
console.log(JSON.stringify({status:'PASSED',scope:'Pure actual-image source-preview components; no inference, project tools or canonical writes',build,source_sha256:hash,source_chars:source.length,checks}));
