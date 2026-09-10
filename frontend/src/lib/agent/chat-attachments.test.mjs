import test from 'node:test';
import assert from 'node:assert/strict';
import { chatDocumentContext, validateChatAttachment } from './chat-attachments.ts';

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
