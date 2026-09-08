import test from 'node:test';
import assert from 'node:assert/strict';
import { reasoningRequest, traceFocusHref, reasoningFocusTime } from './reasoning-api.ts';

test('one reasoning timestamp focuses all four project-scoped views', () => {
  for (const view of ['messages', 'sequence', 'signals', 'trace']) {
    const url = new URL(traceFocusHref('project space', 'job', view, 12.48), 'http://localhost');
    assert.equal(url.pathname, '/trace-analysis');
    assert.equal(url.searchParams.get('project'), 'project space');
    assert.equal(url.searchParams.get('focus_s'), '12.48');
    assert.equal(url.searchParams.get('view'), view);
  }
  assert.throws(() => traceFocusHref('p', 'j', 'wrong', 0));
  assert.throws(() => traceFocusHref('p', 'j', 'trace', NaN));
});

test('focus uses the supported cause-effect time instead of an unrelated early observation', () => {
  assert.equal(reasoningFocusTime({ observations: [{ timestamp: 0 }], causal_chain: [
    { relation: 'CORRELATED_ONLY', timestamp: .001 }, { relation: 'INJECTED_CAUSE', timestamp: .02 },
  ] }), .02);
  assert.equal(reasoningFocusTime(null), undefined);
});

test('reasoning transport scopes requests and surfaces server errors', async t => {
  const requests = [];
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    requests.push({ url, options });
    return new Response(JSON.stringify({ reasoning_id: 'r' }), { status: 201 });
  });
  assert.equal((await reasoningRequest('p', '', { job_id: 'j' })).reasoning_id, 'r');
  assert.equal(requests[0].options.headers['X-Project-ID'], 'p');
  assert.equal(requests[0].options.method, 'POST');
  assert.equal(requests[0].options.cache, 'no-store');
  globalThis.fetch = async () => new Response(JSON.stringify({ error: 'Analyse ist veraltet' }), { status: 409 });
  await assert.rejects(reasoningRequest('p', '/r/proposal', {}), /veraltet/);
});
