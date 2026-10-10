import test from 'node:test';
import assert from 'node:assert/strict';
import { refreshProposal, restoreWizardProposal, applyReviewedProposal, approveAndApplyWizardProposal } from './proposal-client.ts';

const proposal = { proposal_id: 'old', revision: '1', status: 'APPROVED', rationale: 'Original',
  assumptions: [], changes: [{ action: 'CREATE', object_type: 'HardwareNode' }],
  validation_result: {}, canonical_ids: [] };
const response = data => Response.json({ success: true, data });

test('returning to a stale wizard proposal validates saved values without approval or application', async t => {
  const calls = [];
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push({ url, ...options });
    return response(url.endsWith('/validate') ? {...proposal, status:'VALIDATED', revision:'3'}
      : {proposal_id:'old', status:'OUTDATED', revision:'2', content_state:'REFERENCE', change_count:4000});
  });
  for (const initial of [proposal, {...proposal,content_state:'REFERENCE',changes:[],change_count:4000}]) {
    calls.length = 0;
    const result = await restoreWizardProposal(initial, 'project-A');
    assert.equal(result.status, 'VALIDATED');
    assert.deepEqual(result.canonical_ids, []);
    assert.deepEqual(calls.map(call => [call.url,call.method ?? 'GET']), [
      ['/api/engineering/agent/proposals/old?view=status','GET'],
      ['/api/engineering/agent/proposals/old/validate','POST'],
    ]);
    assert.ok(calls.every(call => call.headers['X-Project-ID'] === 'project-A'));
    assert.ok(calls.every(call => !call.headers['X-Human-Review'] && !call.url.includes('/approve') && !call.url.includes('/apply')));
  }
});

test('already current or applied wizard proposals are read without revalidation', async t => {
  for (const status of ['VALIDATED', 'APPROVED', 'APPLIED', 'REJECTED']) {
    const calls = [];
    t.mock.method(globalThis, 'fetch', async (url, options) => {
      calls.push(options.method ?? 'GET');
      return response({ ...proposal, status });
    });
    assert.equal((await restoreWizardProposal(proposal, 'project-A')).status, status);
    assert.deepEqual(calls, ['GET']);
  }
});

test('compact status polling preserves the reviewed changes', async t => {
  t.mock.method(globalThis, 'fetch', async () => response({ proposal_id: 'old', revision: '1', status: 'APPLIED',
    content_state:'REFERENCE', changes:[], change_count:1 }));
  const result = await refreshProposal(proposal, 'test');
  assert.equal(result.status, 'APPLIED');
  assert.deepEqual(result.changes, proposal.changes);
  assert.equal(result.content_state, 'FULL');
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

test('a successful HTTP response with OUTDATED is never reported as applied', async t => {
  t.mock.method(globalThis, 'fetch', async () => response({...proposal,status:'OUTDATED'}));
  await assert.rejects(approveAndApplyWizardProposal(proposal,'test','csrf'), /nicht bestätigt.*nicht übernommen/);
  await assert.rejects(applyReviewedProposal(proposal,'test','csrf'), /nicht bestätigt.*nicht übernommen/);
});

import { proposalFindingGroups } from './proposal-client.ts';
import { loadWizardProposal } from './proposal-client.ts';
test('parent wizard restoration validates stale status directly and polls matching contents compactly', async t => {
  const calls = [];
  let status = 'OUTDATED';
  const fresh = {...proposal, revision: '2', status: 'VALIDATED'};
  t.mock.method(globalThis, 'fetch', async (url, options = {}) => {
    calls.push({url,method:options.method ?? 'GET',project:options.headers['X-Project-ID']});
    if (url.endsWith('/validate')) { status = 'VALIDATED'; return response(fresh); }
    assert.ok(url.endsWith('?view=status'), 'No stale or repeated full body should be fetched.');
    return response({proposal_id:'old',revision:status === 'OUTDATED' ? '1' : '2',status,content_state:'REFERENCE'});
  });
  let current = await loadWizardProposal('old','saved-project');
  for (let index=0;index<3;index++) current = await loadWizardProposal('old','saved-project',current);
  assert.deepEqual(current.changes,proposal.changes);
  assert.equal(current.revision,'2'); assert.equal(current.status,'VALIDATED');
  assert.equal(calls.filter(call=>call.method==='POST').length,1);
  assert.equal(calls.length,5);
  assert.ok(calls.every(call=>call.project==='saved-project'));
});

test('parent wizard loads a changed active proposal with its own full content', async t => {
  const calls=[];
  const replacement={...proposal,proposal_id:'replacement',revision:'7',rationale:'Current replacement',status:'VALIDATED'};
  t.mock.method(globalThis,'fetch',async url=> {
    calls.push(url);
    return response(url.endsWith('?view=status')
      ? {proposal_id:'replacement',revision:'7',status:'VALIDATED',content_state:'REFERENCE'} : replacement);
  });
  const result=await loadWizardProposal('replacement','saved-project',proposal);
  assert.equal(result.proposal_id,'replacement'); assert.equal(result.rationale,'Current replacement');
  assert.deepEqual(calls,['/api/engineering/agent/proposals/replacement?view=status','/api/engineering/agent/proposals/replacement']);
});

test('all 301 historical capacity findings retain identities in compact technology groups', () => {
  const changes = Array.from({ length: 301 }, (_, i) => ({ local_ref: `port-${i}`, object_type: 'HardwareNetworkInterface', data: { name: `ECU${i}_LIN`, technology: 'LIN', network_ref: 'local-lin' } }));
  const findings = changes.map(change => ({ code: 'CAPACITY_UNVERIFIED', object_id: `$${change.local_ref}`, message: 'Rate fehlt', severity: 'OPEN' }));
  const groups = proposalFindingGroups({ changes, validation_result: { findings } });
  assert.equal(groups.length, 1); assert.equal(groups[0].findings.length, 301);
  assert.equal(groups[0].findings[300].object_name, 'ECU300_LIN');
});
