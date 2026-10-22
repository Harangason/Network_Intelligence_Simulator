import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { extractEngineeringSpecification, expandEngineeringSignalModel, applyIndustryGenerationPath,
  packEngineeringChains, reconcileConfirmedGraphDevices, applyConfirmedClusterGraph, readDocumentReferenceDesign } from './engineering-specification.ts';
import { documentFactIdentity } from './document-clarification.ts';
const sha = text => createHash('sha256').update(text).digest('hex');
function example() {
  const source = 'Controller\nSensor\nAktor\nRegelung\nDiagnose\nREQ-001: Erhalten';
  const facts = [['Controller','INSTANCE','CONTROLLER'], ['Sensor','CATEGORY','SENSOR'], ['Aktor','CATEGORY','ACTUATOR'],
    ['Regelung','FUNCTION','OTHER'], ['Diagnose','FUNCTION','OTHER'], ['REQ-001: Erhalten','REQUIREMENT','OTHER']]
    .map(([name, kind, role]) => ({ name, kind, role, quantity: kind === 'INSTANCE' ? 1 : null, source_quote:name, source_context:[] }));
  const ids = facts.map(fact => 'F' + sha(documentFactIdentity(fact)).slice(0,12));
  const equipment = { source_text:source, source_name:'reference-example.txt', source_sha256:sha(source), source_chars:source.length,
    facts, technologies:[], devices:[{name:'Controller',role:'CONTROLLER',quantity:1,source_quote:'Controller',minimum:false}], questions:[], answers:[], function_assignments:{} };
  const definition = {length_bits:1,data_type:'unsigned',unit:'code',factor:1,offset_value:0,
    semantic:{semantic_type:'BOOLEAN',meaning:'Stellbefehl'},data:{enum_values:{OFF:0,ON:1}}};
  const design = {schema_version:1,design_id:'test-design',revision:1,request_sha256:'a'.repeat(64),source_sha256:sha(source),status:'ACCEPTED',
    fact_id_map:Object.fromEntries(facts.map((fact,i)=>[ids[i],documentFactIdentity(fact)])),decision_evidence:[],protected_fields:{},
    proposal:{devices:[['C','Controller','CONTROLLER'],['S','Sensor','SENSOR'],['A','Aktor','ACTUATOR']].map(([id,name,kind],i)=>({id,name,kind,quantity:1,source_fact_ids:[ids[i]],rationale:'Referenzannahme',...(i?{owner_device_id:'C'}:{})})),
      ports:[['CP','C'],['SP','S'],['AP','A']].map(([id,device_id])=>({id,device_id,technology:'can_fd',network_scope:'local',role:'LOCAL',parameters:{},rationale:'Referenzanschluss'})),
      functions:[{source_fact_id:ids[3],realization:'ATOMIC',executor_device_ids:['C'],realized_by_fact_ids:[],rationale:'Referenzzuordnung'},
        {source_fact_id:ids[4],realization:'ATOMIC',executor_device_ids:['C'],realized_by_fact_ids:[],rationale:'Referenzzuordnung'}],
      commands:[{device_id:'A',definition}],measurements:[],functional_dependencies:[{id:'LOCAL',producer_fact_id:ids[3],consumer_fact_ids:[ids[4]],executor_device_id:'C',encoding:definition}],
      communication:[{id:'COMMAND',producer_device_id:'C',consumer_device_ids:['A'],source_port_id:'CP',consumer_port_ids:['AP'],
        scope:'LOCAL_IO',role:'COMMAND',signal_name:'Stellbefehl',producer_fact_id:ids[3],encoding:definition,transmission_mode:'EVENT',
        trigger:'explicit',release_times_ms:[20,50],min_interval_ms:10,rationale:'Expliziter Referenzverkehr'}],unresolved:[]}};
  return {equipment,design,ids, prompt:()=>source+'\n- Dokument-Geräte: '+JSON.stringify(equipment)+'\n- Dokument-Referenzentwurf: '+JSON.stringify(design)};
}
test('accepted plan retains complete source facts, atomic and local function bindings without synthetic traffic',()=>{
  const {prompt,design}=example(), spec=extractEngineeringSpecification(prompt());
  assert.equal(spec.chains.length,3);
  assert.deepEqual(spec.reference_design.original_facts,JSON.parse(prompt().split('- Dokument-Geräte: ')[1].split('\n')[0]).facts);
  assert.deepEqual(spec.reference_design.proposal.functional_dependencies,design.proposal.functional_dependencies);
  const tx=spec.chains.filter(c=>!c.configuration.reference_receive_only);
  assert.equal(tx.length,1);assert.equal(tx[0].configuration.reference_communication_id,'COMMAND');
  assert.equal(tx[0].configuration.reference_function_fact_id,design.proposal.functions[0].source_fact_id);
  assert.deepEqual(tx[0].configuration.transmission,{mode:'EVENT',minimum_interval_ms:10,trigger:'explicit',release_times_ms:[20,50]});
  assert.equal(tx[0].configuration.processing_evidence,'NONE');
  for(const c of spec.chains.filter(c=>c.configuration.reference_receive_only)) {
    assert.equal(c.signal_name,'');assert.equal(c.message_name,'');assert.equal(c.function_name,'');assert.equal(c.length_bits,0);assert.equal(c.cycle_ms,0);
  }
  assert.equal(expandEngineeringSignalModel(spec.chains).length,3);
  assert.equal(packEngineeringChains(spec.chains).length,3);
  assert.equal(applyIndustryGenerationPath(spec.chains,'automotive',prompt()).length,3);
  assert.equal(applyConfirmedClusterGraph(spec.chains,prompt()).length,3);
  assert.equal(reconcileConfirmedGraphDevices(spec,prompt()).length,3);
});
test('all physical ports remain distinct including receive-only and no-port electronics',()=>{
  const ex=example();
  ex.design.proposal.ports.push({...ex.design.proposal.ports[0],id:'BACKBONE',technology:'ethernet',network_scope:'backbone',role:'BACKBONE'});
  ex.design.proposal.devices.push({id:'C2',name:'LocalCompute',kind:'CONTROLLER',quantity:1,source_fact_ids:[ex.ids[4]],rationale:'Lokale Referenzausführung'});
  const spec=extractEngineeringSpecification(ex.prompt());
  assert.equal(spec.chains.length,5);
  assert.equal(spec.chains.filter(c=>c.configuration.reference_device_id==='C').length,2);
  const local=spec.chains.find(c=>c.configuration.reference_device_id==='C2');
  assert.equal(local.configuration.reference_no_port,true);assert.equal(local.interface_name,'');
});
test('compiler preserves signed, floating, big endian and explicit structured payload fields',()=>{
  const ex=example(), row=ex.design.proposal.communication[0];
  row.encoding={...row.encoding,length_bits:32,data_type:'float32',byte_order:'big_endian',unit:'Nm',min_value:-10,max_value:10,
    semantic:{semantic_type:'NUMERIC',meaning:'Drehmoment'},data:{structured_payload:{processing_evidence:'NONE',fields:[{name:'x',bits:32}]}}};
  const chain=extractEngineeringSpecification(ex.prompt()).chains[0];
  assert.equal(chain.data_type,'float32');assert.equal(chain.byte_order,'big_endian');assert.equal(chain.min_value,-10);
  assert.deepEqual(chain.configuration.structured_payload,row.encoding.data.structured_payload);
  assert.equal(chain.dlc,4);
});
test('compiler refuses source loss, unknown wire technology and implicit group addressing',()=>{
  for(const mutation of ['hash','facts','technology','group','consumer','function']) {
    const ex=example();
    if(mutation==='hash') ex.design.source_sha256='b'.repeat(64);
    if(mutation==='facts') delete ex.design.fact_id_map[ex.ids[5]];
    if(mutation==='technology') ex.design.proposal.ports[0].technology='fictional';
    if(mutation==='group') ex.design.proposal.devices[1].quantity=3;
    if(mutation==='consumer') ex.design.proposal.communication[0].consumer_port_ids=[];
    if(mutation==='function') ex.design.proposal.communication[0].producer_fact_id=ex.ids[5];
    assert.throws(()=>extractEngineeringSpecification(ex.prompt()),undefined,mutation);
  }
  assert.equal(readDocumentReferenceDesign('No accepted design'),undefined);
});
