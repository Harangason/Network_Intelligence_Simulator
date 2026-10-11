import assert from 'node:assert/strict';
import test from 'node:test';
import { engineeringContextHref } from './assistant-context.ts';

test('route deep links use the routing workbench selection parameter', () => {
  const url = new URL(engineeringContextHref({ object_type: 'Route', id: 'canonical-route' }, 'project'), 'http://localhost');
  assert.equal(url.pathname, '/studio/routing');
  assert.equal(url.searchParams.get('route'), 'canonical-route');
  assert.equal(url.searchParams.has('object'), false);
});

test('workspace result links preserve a safe route back to the same project', () => {
  const url = new URL(engineeringContextHref(
    { object_type: 'Workspace', name: 'Ausführliche Auswertung öffnen', id: 'response-1' },
    'project-a', '/studio/intelligence?project=project-a&tab=issues'), 'http://localhost');
  assert.equal(url.pathname, '/studio/agent');
  assert.equal(url.searchParams.get('project'), 'project-a');
  assert.equal(url.searchParams.get('response'), 'response-1');
  assert.equal(url.searchParams.get('back_to'), '/studio/intelligence?project=project-a&tab=issues');
});

test('workspace result links never preserve external return destinations', () => {
  const url = new URL(engineeringContextHref(
    { object_type: 'Workspace', name: 'Auswertung öffnen' }, 'project-a', '//attacker.example/path'), 'http://localhost');
  assert.equal(url.searchParams.has('back_to'), false);
});
