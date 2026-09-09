import assert from 'node:assert/strict';
import test from 'node:test';
import { backendEndpoints } from './backend-endpoints.ts';

test('one isolated backend serves jobs, engineering, agent chat and history', () => {
  assert.deepEqual(backendEndpoints({ SIMULATOR_BACKEND_API_URL: 'http://127.0.0.1:15059/api/' }), {
    simulator: 'http://127.0.0.1:15059/api', engineering: 'http://127.0.0.1:15059/api/engineering',
  });
});

test('explicit engineering override and legacy simulator configuration remain supported', () => {
  assert.deepEqual(backendEndpoints({ SIMULATOR_API_URL: 'http://legacy/api', ENGINEERING_API_URL: 'http://engineering/api/engineering/' }), {
    simulator: 'http://legacy/api', engineering: 'http://engineering/api/engineering',
  });
});
