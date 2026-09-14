import assert from 'node:assert/strict';
import { test } from 'node:test';
import { getWorkflow, getWorkflowSummary } from './workflow-api.ts';

const versions = (revision = 1) => ({ engineering_model: revision, routing: revision, network_editor: revision, parameters: revision });
const summary = (project, revision = 1) => ({ project_id: project, versions: versions(revision),
  edit_tokens: { parameters: `p${revision}`, topology: `t${revision}` }, context: { marker: revision } });
const detail = (project, key, revision = 1, payload = {}) => ({ project_id: project, versions: versions(revision),
  edit_token: `${key[0]}${revision}`, [key]: payload });

test('large editors load separate canonical details and preserve simulation metadata without an oversized status request', async () => {
  const original = globalThis.fetch;
  const calls = [];
  const parameters = { networks: [{ id: 'bus', name: 'ETH_System_01' }], description: 'p'.repeat(900_000) };
  const topology = { nodes: [{ id: 'sensor', engineeringId: 'canonical-sensor' }], scene: { description: 't'.repeat(1_200_000) } };
  const snapshots = [{ id: 'snapshot', job_id: 'original-job', status: 'COMPLETED' }];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    if (url.endsWith('/parameters')) return Response.json(detail('large-project', 'parameters', 1, parameters));
    if (url.endsWith('/topology')) return Response.json(detail('large-project', 'topology', 1, topology));
    if (url.endsWith('/snapshots')) return Response.json({ simulations: snapshots });
    if (url.endsWith('?view=summary')) return Response.json(summary('large-project'));
    return Response.json({ error: 'workflow_state_response exceeds 2000000 bytes' }, { status: 413 });
  };
  try {
    const result = await getWorkflow('large-project');
    assert.deepEqual(result.parameters, parameters);
    assert.deepEqual(result.topology, topology);
    assert.deepEqual(result.simulation_snapshots, snapshots);
    assert.deepEqual(result.edit_tokens, { parameters: 'p1', topology: 't1' });
    assert.ok(JSON.stringify(result).length > 2_000_000);
    assert.equal(calls.length, 4);
    assert.ok(calls.every(call => call.options.headers['X-Project-ID'] === 'large-project'));
    assert.ok(calls.every(call => call.options.cache === 'no-store'));
    assert.equal(new Set(calls.map(call => call.options.signal)).size, 1, 'one overall request deadline');
  } finally { globalThis.fetch = original; }
});

test('concurrent source changes retry the complete resource set instead of mixing model revisions', async () => {
  const original = globalThis.fetch;
  let attempt = 0;
  globalThis.fetch = async url => {
    if (url.endsWith('/parameters')) { attempt += 1; return Response.json(detail('project', 'parameters', attempt, { marker: attempt })); }
    if (url.endsWith('/topology')) return Response.json(detail('project', 'topology', 2, { marker: 2 }));
    if (url.endsWith('/snapshots')) return Response.json({ simulations: [] });
    return Response.json(summary('project', 2));
  };
  try {
    const result = await getWorkflow('project');
    assert.equal(attempt, 2);
    assert.equal(result.parameters.marker, 2);
    assert.equal(result.topology.marker, 2);
    assert.equal(result.context.marker, 2);
  } finally { globalThis.fetch = original; }
});

test('layout token changes retry even when semantic versions do not change, and retries stay bounded', async () => {
  const original = globalThis.fetch;
  let attempts = 0;
  globalThis.fetch = async url => {
    if (url.endsWith('/parameters')) { attempts += 1; return Response.json(detail('project', 'parameters')); }
    if (url.endsWith('/topology')) return Response.json({ ...detail('project', 'topology'), edit_token: 'stale-layout' });
    if (url.endsWith('/snapshots')) return Response.json({ simulations: [] });
    return Response.json(summary('project'));
  };
  try {
    await assert.rejects(getWorkflow('project'), /Modell wurde während des Ladens geändert/);
    assert.equal(attempts, 3);
  } finally { globalThis.fetch = original; }
});

test('a foreign project detail is rejected instead of displaying or retrying another project', async () => {
  const original = globalThis.fetch;
  let attempts = 0;
  globalThis.fetch = async url => {
    if (url.endsWith('/parameters')) { attempts += 1; return Response.json(detail('other-project', 'parameters')); }
    if (url.endsWith('/topology')) return Response.json(detail('project', 'topology'));
    if (url.endsWith('/snapshots')) return Response.json({ simulations: [] });
    return Response.json(summary('project'));
  };
  try {
    await assert.rejects(getWorkflow('project'), /anderen Projekt/);
    assert.equal(attempts, 1);
  } finally { globalThis.fetch = original; }
});

test('workflow polling coalesces by project while a post-receipt read bypasses the old request', async () => {
  const original = globalThis.fetch;
  const requests = [];
  globalThis.fetch = (_url, options) => new Promise(resolve => {
    requests.push({ project: options.headers['X-Project-ID'], resolve });
  });
  const response = (project, revision) => Response.json({ project_id: project,
    context: { wizard_request: { run_id: 'wizard-test', revision } } });
  try {
    const oldPoll = getWorkflowSummary('amended-project');
    assert.equal(getWorkflowSummary('amended-project'), oldPoll);
    const otherProject = getWorkflowSummary('other-project');
    assert.equal(requests.length, 2);

    // AMEND was accepted after the old GET took its snapshot. This read must
    // start after that receipt rather than inherit the pre-commit response.
    const afterReceipt = getWorkflowSummary('amended-project', { fresh: true });
    assert.equal(requests.length, 3);
    assert.notEqual(afterReceipt, oldPoll);
    requests[0].resolve(response('amended-project', 'before-amend'));
    assert.equal((await oldPoll).context.wizard_request.revision, 'before-amend');

    // Resolving the older request must not delete the newer pending entry.
    assert.equal(getWorkflowSummary('amended-project'), afterReceipt);
    assert.equal(requests.length, 3);
    requests[2].resolve(response('amended-project', 'accepted-amend'));
    assert.equal((await afterReceipt).context.wizard_request.revision, 'accepted-amend');
    requests[1].resolve(response('other-project', 'unrelated-revision'));
    assert.equal((await otherProject).project_id, 'other-project');
  } finally {
    requests.forEach(request => request.resolve(response(request.project, 'cleanup')));
    globalThis.fetch = original;
  }
});
