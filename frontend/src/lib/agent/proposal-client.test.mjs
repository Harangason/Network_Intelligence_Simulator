import test from 'node:test';
import assert from 'node:assert/strict';
import { refreshProposal, applyReviewedProposal, approveAndApplyWizardProposal } from './proposal-client.ts';

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

test('wizard review sends one combined approval and apply request', async t => {
  const calls = [];
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push({ url, options });
    return response({ proposal_id: 'old', revision: '2', status: 'APPLIED', canonical_ids: [{ id: 'node', object_type: 'HardwareNode' }] });
  });
  const result = await approveAndApplyWizardProposal({ ...proposal, status: 'VALIDATED' }, 'test', 'csrf');
  assert.equal(result.status, 'APPLIED');
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/approve-apply\?view=status$/);
  assert.equal(calls[0].options.headers['X-Human-Review'], 'confirmed');
  assert.deepEqual(JSON.parse(calls[0].options.body), { revision: '1' });
});

test('lost combined wizard response reads back APPLIED without repeating the write', async t => {
  const methods = [];
  t.mock.method(globalThis, 'fetch', async (url, options = {}) => {
    methods.push(options.method ?? 'GET');
    if (options.method === 'POST') throw new TypeError('Failed to fetch');
    const applied = { ...proposal, revision: '2', status: 'APPLIED', canonical_ids: [{ id: 'node', object_type: 'HardwareNode' }] };
    return response(url.endsWith('?view=status')
      ? { proposal_id: applied.proposal_id, revision: applied.revision, status: applied.status, canonical_ids: applied.canonical_ids }
      : applied);
  });
  const result = await approveAndApplyWizardProposal({ ...proposal, status: 'VALIDATED' }, 'test', 'csrf');
  assert.equal(result.status, 'APPLIED');
  assert.deepEqual(methods, ['POST', 'GET', 'GET']);
});
