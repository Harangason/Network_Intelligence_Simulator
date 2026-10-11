import assert from 'node:assert/strict';
import { test } from 'node:test';
import { agentResponseSchema, chatMessageTypes, parseAgentResponse } from './agent-response.ts';
import { engineeringContextHref } from './assistant-context.ts';
import {readFileSync} from 'node:fs';
const question = {id:'q1', question:'Auswahl?', selection_mode:'SINGLE', options:[{id:'a',label:'A',recommended:true},{id:'b',label:'B',disabled:true}], status:'OPEN'};
test('Python and frontend expose the same message types', () => {
  const schema=JSON.parse(readFileSync(new URL('../../../../docs/agent_core/agent_response.schema.json',import.meta.url),'utf8'));
  assert.deepEqual([...schema.properties.type.enum].sort(),[...chatMessageTypes].sort());
});
for (const type of chatMessageTypes) test(`AgentResponse ${type}`, () => {
  const input = {id:'r1',type,text:'Ergebnis',created_at:new Date().toISOString(), ...(['QUESTION','SINGLE_SELECT','MULTI_SELECT'].includes(type) ? {question:{...question, selection_mode:type==='MULTI_SELECT'?'MULTI':'SINGLE'}} : {})};
  assert.equal(agentResponseSchema.parse(input).type,type);
});
test('invalid schema becomes safe text', () => {
  assert.equal(parseAgentResponse({type:'HTML',html:'<script>alert(1)</script>'}).type,'TEXT');
  assert.equal(parseAgentResponse({id:'r',type:'QUESTION',created_at:'now'}).metadata.contract_error,true);
});
test('selection IDs and recommendations must be consistent', () => {
  const event = {id:'r',type:'QUESTION',created_at:'now',question:{...question, options:[{id:'a',label:'A'},{id:'a',label:'B'}]}};
  assert.equal(agentResponseSchema.safeParse(event).success,false);
  event.question.options=[{id:'a',label:'A'},{id:'b',label:'B'}];
  assert.equal(agentResponseSchema.safeParse(event).success,true);
});
test('only known context targets generate internal links', () => {
  for(const object_type of ['HardwareNode','HardwareNetworkInterface','Function','Interface','Message','Signal','Routing','Simulation','Trace','Workspace']) {
    const href=engineeringContextHref({object_type,id:'id with space'},'network-project-test');
    assert.ok(href.startsWith('/studio')); assert.equal(new URL(href,'http://localhost').searchParams.get('project'),'network-project-test');
  }
  assert.equal(engineeringContextHref({object_type:'javascript:alert(1)'},'p'),null);
});

test('wizard-scale proposals above the old 2000-change ceiling remain renderable', () => {
  const changes = Array.from({length: 3000}, (_, index) => ({
    action: 'CREATE', object_type: 'Signal', data: {name: `Signal-${index}`},
  }));
  const parsed = agentResponseSchema.safeParse({
    id: 'large-proposal', type: 'APPROVAL', text: 'Prüfen', created_at: 'now',
    proposal: {
      proposal_id: 'proposal-large', proposal_type: 'WIZARD_ENGINEERING_MODEL', revision: '1',
      status: 'PROPOSED', rationale: '250 Sensoren und 250 Aktoren', assumptions: [], changes,
      validation_result: {}, canonical_ids: [],
    },
  });
  assert.equal(parsed.success, true);
});
