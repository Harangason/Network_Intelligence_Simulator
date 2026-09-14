import assert from 'node:assert/strict';
import test from 'node:test';
import { reconcileQuestionSelection } from './question-selection.ts';

test('open question polling preserves an edited choice and recommended defaults', () => {
  assert.deepEqual(reconcileQuestionSelection(['measurement'], 'OPEN', [], true), ['measurement']);
  assert.deepEqual(reconcileQuestionSelection(['measurement'], 'OPEN', ['status'], true), ['measurement']);
  assert.deepEqual(reconcileQuestionSelection(['recommended'], 'OPEN', [], false), ['recommended']);
  assert.deepEqual(reconcileQuestionSelection([], 'OPEN', ['saved'], false), ['saved']);
});

test('a persisted final decision takes precedence over unsent local selections', () => {
  assert.deepEqual(reconcileQuestionSelection(['measurement'], 'ANSWERED', ['status'], true), ['status']);
  assert.deepEqual(reconcileQuestionSelection(['measurement'], 'SKIPPED', [], true), []);
});
