import assert from 'node:assert/strict';
import test from 'node:test';
import { parseWizardCommand, wizardReceipt, wizardRequestRevision, wizardQuestionFromConversation, wizardConversationMatches, wizardContextForRequest } from './wizard-protocol.ts';

const command = { action: 'START', run_id: 'run-test-a', operation_id: 'op-start', target: 'data_science_intelligence', wizard_context: { project_id: 'project-a', scope_ids: ['engineering_model', 'data_science_intelligence'] } };

test('start transports the confirmed target and complete request context without a prose convention', () => {
  assert.deepEqual(parseWizardCommand(command), command);
  assert.throws(() => parseWizardCommand({ ...command, target: 'unknown' }));
  assert.throws(() => parseWizardCommand({ ...command, wizard_context: undefined }));
  assert.throws(() => parseWizardCommand({ ...command, operation_id: '' }));
  assert.throws(() => parseWizardCommand({ ...command, run_id: 'short' }));
  assert.throws(() => parseWizardCommand({ ...command, operation_id: 'invalid/id' }));
  assert.throws(() => parseWizardCommand({ ...command, operation_id: 'a'.repeat(121) }));
  assert.throws(() => parseWizardCommand({ ...command, request_revision: 'a'.repeat(129) }));
});

test('continuation preserves operation identity and revision; controls cannot carry an unvalidated extra field', () => {
  const resume = { action: 'CONTINUE', run_id: 'run-test-a', operation_id: 'same-operation', request_revision: 'revision-a', automatic: true };
  assert.deepEqual(parseWizardCommand(resume), resume);
  assert.deepEqual(parseWizardCommand(JSON.parse(JSON.stringify(resume))), resume);
  assert.throws(() => parseWizardCommand({ ...resume, agent_execution: { state: 'COMPLETED' } }));
  assert.equal(wizardRequestRevision({ wizard_request: { run_id: 'run-b', revision: 'revision-b' } }, 'run-a'), undefined);
  assert.equal(wizardRequestRevision({ wizard_request: { run_id: 'run-a', revision: 'revision-a' } }, 'run-a'), 'revision-a');
});

test('automatic resume is acknowledged only by a valid matching server receipt', () => {
  const receipt = { accepted: true, duplicate: false, run_id: 'run-a', operation_id: 'op-1', request_revision: 'rev-1', target: 'simulation' };
  assert.deepEqual(wizardReceipt({ type: 'CONTEXT', status: 'ACCEPTED', wizard_receipt: receipt }, 'run-a'), receipt);
  assert.equal(wizardReceipt({ type: 'PROGRESS', wizard_receipt: receipt }, 'run-a'), null);
  assert.equal(wizardReceipt({ type: 'CONTEXT', wizard_receipt: { ...receipt, accepted: false } }, 'run-a'), null);
  assert.equal(wizardReceipt({ type: 'CONTEXT', wizard_receipt: receipt }, 'run-b'), null);
});

const question = { id: 'q-1', question: 'Welche Ausgabe?', selection_mode: 'SINGLE', options: [{ id: 'status', label: 'Status' }, { id: 'value', label: 'Messwert' }], status: 'OPEN', decision_key: 'output', context_revision: 3, expires_at: '2026-09-15T00:00:00Z', selected_options: [] };
const conversation = { current_requirement: 'Strukturierte Vorgaben fuer den Engineering-Agenten:\n- Lauf-ID: run-a\n- Projektname: A', current_question: 'q-1', questions: { 'q-1': question } };

test('a restored wizard reads the persisted structured question and option IDs without parsing question prose', () => {
  const result = wizardQuestionFromConversation(conversation, 'run-a');
  assert.equal(result?.id, 'q-1');
  assert.deepEqual(result.options.map(option => option.id), ['status', 'value']);
  assert.equal(wizardQuestionFromConversation(conversation, 'run-b'), null);
  assert.equal(wizardQuestionFromConversation({ ...conversation, current_question: null }, 'run-a'), null);
  assert.equal(wizardQuestionFromConversation({ ...conversation, questions: { 'q-1': { ...question, status: 'ANSWERED' } } }, 'run-a'), null);
  assert.equal(wizardConversationMatches(conversation, 'run'), false, 'run-id prefix must not select another run');
});

test('status context follows only its accepted project, run and request revision after an amendment', () => {
  const wizard = { project_id: 'project-a', run_id: 'run-a', request_revision: 'amended-revision',
    hardware_counts: { sensors: 251 }, task: 'Original task plus confirmed addition', scope_ids: ['engineering_model'] };
  const workflow = { project_id: 'project-a', context: { wizard_request: { run_id: 'run-a', revision: 'amended-revision' }, agent_wizard_status: wizard } };
  assert.equal(wizardContextForRequest(workflow, 'project-a', 'run-a', 'amended-revision'), wizard);
  assert.equal(wizardContextForRequest(workflow, 'project-a', 'run-a', 'previous-revision'), null);
  assert.equal(wizardContextForRequest(workflow, 'project-b', 'run-a', 'amended-revision'), null);
  assert.equal(wizardContextForRequest(workflow, 'project-a', 'other-run', 'amended-revision'), null);
  assert.equal(wizardContextForRequest(workflow, 'project-a', 'run-a', undefined), null);
  assert.equal(wizardContextForRequest({ ...workflow, context: { ...workflow.context,
    agent_wizard_status: { ...wizard, request_revision: 'previous-revision' } } }, 'project-a', 'run-a', 'amended-revision'), null);
});
