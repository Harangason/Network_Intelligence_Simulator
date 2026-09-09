import test from 'node:test';
import assert from 'node:assert/strict';
import { transportMessages } from './agent-chat-history.ts';
import { hasCompleteProposal, proposalChangePage, refreshProposal } from './agent/proposal-client.ts';

const full = {
  proposal_id: 'large', proposal_type: 'WIZARD_ENGINEERING_MODEL', revision: 'r1', status: 'VALIDATED',
  rationale: 'Alle Änderungen prüfen', assumptions: [], validation_result: { valid: true }, canonical_ids: [],
  changes: Array.from({ length: 3000 }, (_, index) => ({ local_ref: `change-${index}`, action: 'CREATE', object_type: 'Signal', data: { name: `Signal-${index}` } })),
};

function roundtrip() {
  const messages = [{ id: 'reply', role: 'assistant', parts: [{ type: 'data-engineering', data: { id: 'response', type: 'APPROVAL', created_at: 'now', proposal: full } }] }];
  return JSON.parse(JSON.stringify(transportMessages(messages)))[0].parts[0].data.proposal;
}

test('3000-change history stores a typed reference, restores same revision fully and exposes every page', async t => {
  const stored = roundtrip();
  assert.equal(stored.content_state, 'REFERENCE');
  assert.equal(stored.change_count, 3000);
  assert.deepEqual(stored.changes, []);
  assert.equal(hasCompleteProposal(stored), false);
  const urls = [];
  t.mock.method(globalThis, 'fetch', async url => {
    urls.push(url);
    return Response.json({ success: true, data: url.endsWith('?view=status')
      ? { proposal_id: full.proposal_id, revision: full.revision, status: full.status }
      : full });
  });
  const restored = await refreshProposal(stored, 'project');
  assert.equal(hasCompleteProposal(restored), true);
  assert.equal(restored.changes.length, 3000);
  assert.equal(urls.length, 2);
  const pages = Array.from({ length: 60 }, (_, page) => proposalChangePage(restored, page));
  assert.ok(pages.every(page => page.changes.length === 50));
  assert.deepEqual(pages.flatMap(page => page.changes), full.changes);
  assert.equal(proposalChangePage(restored, 999).page, 59);
});

test('a failed full reload never turns a history reference into reviewable data', async t => {
  const reference = roundtrip();
  t.mock.method(globalThis, 'fetch', async url => {
    if (!url.endsWith('?view=status')) throw new TypeError('Failed to fetch');
    return Response.json({ success: true, data: { proposal_id: full.proposal_id, revision: full.revision, status: full.status } });
  });
  await assert.rejects(refreshProposal(reference, 'project'));
  assert.equal(hasCompleteProposal(reference), false);
});

test('a reopened review always verifies canonical contents even for an apparently complete legacy snapshot', async t => {
  const urls = [];
  t.mock.method(globalThis, 'fetch', async url => {
    urls.push(url);
    return Response.json({ success: true, data: url.endsWith('?view=status')
      ? { proposal_id: full.proposal_id, revision: full.revision, status: full.status }
      : full });
  });
  const legacy = { ...full, changes: full.changes.slice(0, 100) };
  const restored = await refreshProposal(legacy, 'project', undefined, true);
  assert.equal(restored.changes.length, 3000);
  assert.equal(urls.length, 2);
});

test('a legacy truncation marker cannot be accepted as a complete proposal', () => {
  assert.equal(hasCompleteProposal({ ...full, changes: [...full.changes.slice(0, 100), '[2900 weitere Eintraege nicht gecacht]'] }), false);
});
