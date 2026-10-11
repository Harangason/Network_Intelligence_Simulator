import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readRegisteredCatalog} from './catalog-response.ts';
import {readApiJson} from './lossless-json.ts';

const catalog = {technology_count: 1, formats: ['json'], domains: [
  {id: 'building', label: 'Building', technologies: [{id: 'knx_tp', label: 'KNX TP'}]},
]};

test('native catalog survives one interrupted response and keeps its industry and protocol', async () => {
  let reads = 0;
  const loaded = await readRegisteredCatalog(() => readApiJson(new Response(++reads === 1
    ? '{"domains":[' : JSON.stringify(catalog))));
  assert.deepEqual(loaded, catalog);
  assert.equal(reads, 2);
});

test('persistent invalid catalog stops after two reads instead of inventing profiles', async () => {
  for (const value of [{}, {domains: {}}, {domains: [{technologies: null}], formats: []}]) {
    let reads = 0;
    await assert.rejects(readRegisteredCatalog(async () => {reads += 1; return value;}), /unvollständig/);
    assert.equal(reads, 2);
  }
});

test('complete native catalog needs one read and retains large parameter integers', async () => {
  let reads = 0;
  const loaded = await readRegisteredCatalog(async () => {
    reads += 1;
    return readApiJson(new Response(JSON.stringify({...catalog, marker: '18446744073709551615'})));
  });
  assert.equal(reads, 1);
  assert.equal(loaded.marker, '18446744073709551615');
});
