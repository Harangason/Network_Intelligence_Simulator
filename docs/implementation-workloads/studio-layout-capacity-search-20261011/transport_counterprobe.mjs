// Counterprobe of the actual pinned Playwright transport: never a production endpoint.
import { request } from '../../../frontend/node_modules/playwright/index.mjs';
import http from 'node:http';
import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';

const calls = new Map();
const server = http.createServer((req, res) => {
  const count = (calls.get(req.url) ?? 0) + 1;
  calls.set(req.url, count);
  if (req.url === '/always-reset' || (req.url === '/recover' && count === 1)) {
    req.socket.destroy(); return;
  }
  res.setHeader('Content-Type', 'application/json');
  if (req.url === '/http-error') { res.writeHead(500); res.end('{"error":"real failure"}'); return; }
  if (req.url === '/invalid-json') { res.end('invalid'); return; }
  res.end('{"project_id":"real-test-project","seed":41}');
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const client = await request.newContext({ baseURL: `http://127.0.0.1:${server.address().port}` });
try {
  const options = { timeout: 60000, maxRetries: 2 };
  const recovered = await client.get('/recover', options);
  assert(recovered.ok());
  assert.deepEqual(await recovered.json(), { project_id: 'real-test-project', seed: 41 });
  assert.equal(calls.get('/recover'), 2);
  await recovered.dispose();
  const error = await client.get('/http-error', options);
  assert.equal(error.status(), 500);
  assert.equal(calls.get('/http-error'), 1);
  await error.dispose();
  const invalid = await client.get('/invalid-json', options);
  await assert.rejects(invalid.json());
  assert.equal(calls.get('/invalid-json'), 1);
  await invalid.dispose();
  await assert.rejects(client.get('/always-reset', options), /Failed after 3 attempt/);
  assert.equal(calls.get('/always-reset'), 3);
  calls.delete('/always-reset');
  await assert.rejects(client.post('/always-reset', { timeout: 60000 }), /socket hang up/);
  assert.equal(calls.get('/always-reset'), 1);
  const evidence = { status: 'PASSED', captured_at: new Date().toISOString(),
    recovered_single_reset: true, persistent_reset_still_fails_after_three_attempts: true,
    http_500_not_retried: true, malformed_json_still_fails: true, writes_not_retried: true,
    timeout_unchanged_ms: 60000, scope: 'Pinned Playwright APIRequestContext with real loopback TCP resets; no product database or UI design tests.' };
  await writeFile(new URL('transport-counterprobe.json', import.meta.url), JSON.stringify(evidence, null, 2));
  console.log(JSON.stringify(evidence));
} finally {
  await client.dispose();
  await new Promise(resolve => server.close(resolve));
}
