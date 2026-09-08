import test from 'node:test';
import assert from 'node:assert/strict';
import { refreshProposal, applyReviewedProposal } from './proposal-client.ts';

const proposal = { proposal_id: 'old', revision: '1', status: 'APPROVED', rationale: 'Original',
  assumptions: [], changes: [{ action: 'CREATE', object_type: 'HardwareNode' }],
  validation_result: {}, canonical_ids: [] };
const response = data => Response.json({ success: true, data });

test('compact status polling preserves the reviewed changes', async t => {
  t.mock.method(globalThis, 'fetch', async () => response({ proposal_id: 'old', revision: '1', status: 'APPLIED' }));
  const result = await refreshProposal(proposal, 'test');
  assert.equal(result.status, 'APPLIED');
  assert.deepEqual(result.changes, proposal.changes);
});

test('replacement status triggers a full read before showing its new content', async t => {
  const urls = [];
  t.mock.method(globalThis, 'fetch', async url => {
    urls.push(url);
    return response(url.endsWith('?view=status')
      ? { proposal_id: 'new', revision: '2', status: 'VALIDATED' }
      : { ...proposal, proposal_id: 'new', revision: '2', status: 'VALIDATED', rationale: 'Replacement', changes: [] });
  });
  const result = await refreshProposal(proposal, 'test');
  assert.equal(result.rationale, 'Replacement');
  assert.deepEqual(result.changes, []);
  assert.ok(urls[1].endsWith('/new'));
});

test('lost apply response is reconciled with the committed state without duplicate writes', async t => {
  const methods = [];
  t.mock.method(globalThis, 'fetch', async (_url, options) => {
    methods.push(options.method ?? 'GET');
    if (options.method === 'POST') throw new TypeError('Failed to fetch');
    return response({ proposal_id: 'old', revision: '1', status: 'APPLIED', canonical_ids: [{ id: 'node', object_type: 'HardwareNode' }] });
  });
  const result = await applyReviewedProposal(proposal, 'test', 'csrf');
  assert.equal(result.status, 'APPLIED');
  assert.deepEqual(methods, ['POST', 'GET']);
});

test('an unreadable or uncommitted apply is not reported as success', async t => {
  t.mock.method(globalThis, 'fetch', async (_url, options) => {
    if (options.method === 'POST') throw new TypeError('Failed to fetch');
    return response(proposal);
  });
  await assert.rejects(applyReviewedProposal(proposal, 'test', 'csrf'), /Übernahme nicht bestätigt/);
});
