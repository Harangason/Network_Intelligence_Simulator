import test from 'node:test';
import assert from 'node:assert/strict';
import { registeredCatalogResponse } from './catalog-proxy.ts';

test('an unavailable backend cannot silently replace the complete registered catalog', async () => {
  const response = await registeredCatalogResponse(async () => null);
  assert.equal(response.status, 503);
  const body = await response.json();
  assert.match(body.error, /vollständige Technologiekatalog/);
  assert.equal(body.domains, undefined);
  assert.equal(body.technology_count, undefined);
});

test('the exact backend catalog and backend errors retain their identity and status', async () => {
  for (const [status, payload] of [[200, {technology_count: 125, domains: [{id: 'custom'}]}],
    [503, {error: 'registry unavailable'}]]) {
    const backend = Response.json(payload, {status});
    const response = await registeredCatalogResponse(async () => backend);
    assert.equal(response, backend);
    assert.equal(response.status, status);
    assert.deepEqual(await response.json(), payload);
  }
});
