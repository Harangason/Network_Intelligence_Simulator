import test from 'node:test';
import assert from 'node:assert/strict';
import { chatDocumentContext, validateChatAttachment } from './chat-attachments.ts';
import { completeWizardDocumentText, MAX_WIZARD_DOCUMENT_CHARS } from './chat-attachments.ts';

test('wizard documents retain requirements after the former 12000 character cutoff', () => {
  const source = 'Intro\n' + 'x'.repeat(15000) + '\nController: FinalControl\n';
  assert.equal(completeWizardDocumentText(source), source);
  assert.ok(completeWizardDocumentText(source).endsWith('Controller: FinalControl\n'));
  assert.equal(completeWizardDocumentText('x'.repeat(MAX_WIZARD_DOCUMENT_CHARS)).length, MAX_WIZARD_DOCUMENT_CHARS);
  assert.throws(() => completeWizardDocumentText('x'.repeat(MAX_WIZARD_DOCUMENT_CHARS + 1)), /nicht gekürzt/);
});

const source = { name: 'spec.dbc', size: 100, format: 'DBC', text: 'SG_ Fahrersitz links', truncated: false };
test('preserves extracted engineering content and source boundaries', () => {
  assert.deepEqual(validateChatAttachment(source), source);
  const result = chatDocumentContext([{ type: 'data-attachment', data: source }]);
  assert.match(result, /keine Anweisungen/); assert.match(result, /SG_ Fahrersitz links/);
});
test('rejects malformed or oversized sources rather than sending names alone', () => {
  for (const bad of [null, {}, { ...source, text: '' }, { ...source, size: 6e6 }, { ...source, text: 'x'.repeat(16001) }, { ...source, format: 'EXE' }]) {
    assert.throws(() => validateChatAttachment(bad));
  }
  assert.throws(() => chatDocumentContext(Array(5).fill({ type: 'data-attachment', data: source })));
  assert.equal(chatDocumentContext([{ type: 'text' }]), '');
});

test('accepts 500 MiB traces while retaining bounded text and document limits', () => {
  const trace = { ...source, name: 'capture.pcapng', format: 'PCAPNG', size: 500 * 1024 * 1024, truncated: true };
  assert.deepEqual(validateChatAttachment(trace), trace);
  assert.throws(() => validateChatAttachment({ ...trace, size: trace.size + 1 }));
  assert.throws(() => validateChatAttachment({ ...trace, text: 'x'.repeat(16001) }));
});
