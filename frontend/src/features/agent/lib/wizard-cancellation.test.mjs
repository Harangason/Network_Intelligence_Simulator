import assert from 'node:assert/strict';
import test from 'node:test';
import { requestWizardCancellation } from './wizard-cancellation.ts';

test('declining confirmation does not stop the stream or contact the server', async () => {
  const result = await requestWizardCancellation('project', 'run', {
    confirm: () => false,
    onConfirmed: () => assert.fail('stream must remain active'),
    request: () => assert.fail('no request before confirmation'),
  });
  assert.equal(result, null);
});

test('confirmed cancellation targets only this project and run', async () => {
  const order = [];
  const workflow = { context: { agent_execution: { state: 'CANCELED' } } };
  const result = await requestWizardCancellation('project', 'run/id', {
    confirm: message => { assert.match(message, /wirklich abbrechen/); order.push('confirmed'); return true; },
    onConfirmed: () => order.push('stop-stream'),
    request: async (url, options) => {
      order.push('request');
      assert.equal(url, '/api/engineering/agent/runs/run%2Fid/cancel');
      assert.equal(options.headers['X-Project-ID'], 'project');
      assert.deepEqual(JSON.parse(options.body), { confirmed: true });
      assert.ok(options.signal);
      return Response.json({ success: true, data: workflow });
    },
  });
  assert.deepEqual(order, ['confirmed', 'stop-stream', 'request']);
  assert.deepEqual(result, workflow);
});

test('server failure is surfaced instead of reporting cancellation', async () => {
  await assert.rejects(requestWizardCancellation('project', 'run', {
    confirm: () => true,
    request: async () => Response.json({ error: 'Server nicht erreichbar' }, { status: 503 }),
  }), /Server nicht erreichbar/);
});

test('cancel carries the reviewed request revision and surfaces stale revision conflicts', async () => {
  await assert.rejects(requestWizardCancellation('project', 'run', {
    confirm: () => true, requestRevision: 'older-revision',
    request: async (_url, options) => {
      assert.equal(JSON.parse(options.body).request_revision, 'older-revision');
      return Response.json({ error: 'Auftragsrevision geändert.' }, { status: 409 });
    },
  }), /Auftragsrevision geändert/);
});
