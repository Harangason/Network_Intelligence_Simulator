import assert from 'node:assert/strict';
import { test } from 'node:test';
import { committedProjectExists } from './project-creation-recovery.ts';

test('a lost create response is recovered only from the exact committed project ID', async () => {
  const calls = [];
  const fetcher = async (url, options) => {
    calls.push({ url, options });
    return Response.json({ items: [
      { project_id: 'network-project-other', name: 'Neues Projekt' },
      { project_id: 'network-project-requested', name: 'Neues Projekt' },
    ] });
  };
  assert.equal(await committedProjectExists('network-project-requested', 'Neues Projekt', fetcher), true);
  assert.equal(await committedProjectExists('network-project-requested', 'Neues Trace-Projekt', fetcher), false);
  assert.deepEqual(calls.map(({ url, options }) => [url, options.cache]), [
    ['/api/engineering/projects?offset=0', 'no-store'],
    ['/api/engineering/projects?offset=0', 'no-store'],
  ]);
});

test('failed and malformed registry reads never claim project creation', async () => {
  assert.equal(await committedProjectExists('project', 'Neues Projekt', async () => Response.json({}, { status: 503 })), false);
  assert.equal(await committedProjectExists('project', 'Neues Projekt', async () => Response.json({ items: null })), false);
});
