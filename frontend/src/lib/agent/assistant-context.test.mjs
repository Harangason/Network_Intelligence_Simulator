import assert from 'node:assert/strict';
import test from 'node:test';
import { engineeringContextHref } from './assistant-context.ts';

test('route deep links use the routing workbench selection parameter', () => {
  const url = new URL(engineeringContextHref({ object_type: 'Route', id: 'canonical-route' }, 'project'), 'http://localhost');
  assert.equal(url.pathname, '/studio/routing');
  assert.equal(url.searchParams.get('route'), 'canonical-route');
  assert.equal(url.searchParams.has('object'), false);
});
