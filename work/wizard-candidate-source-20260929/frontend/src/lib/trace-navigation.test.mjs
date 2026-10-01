import test from 'node:test';
import assert from 'node:assert/strict';
import { traceViewHref } from './trace-navigation.ts';

test('trace view changes preserve project, job and cause focus including zero', () => {
  for (const focus of ['0', '1.44e-06']) {
    const href = traceViewHref(`project=qa&job=run&view=messages&focus_s=${focus}`, 'sequence');
    const url = new URL(href, 'http://localhost');
    assert.equal(url.searchParams.get('view'), 'sequence');
    assert.equal(url.searchParams.get('project'), 'qa');
    assert.equal(url.searchParams.get('job'), 'run');
    assert.equal(url.searchParams.get('focus_s'), focus);
  }
});
