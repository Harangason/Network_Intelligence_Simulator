import test from 'node:test';
import assert from 'node:assert/strict';
import { completedFrontier, WizardProgressWatchdog, WIZARD_STEPS } from '../../../e2e/support/wizard-progress-watchdog.ts';

function workflow(count, overrides = {}) {
  return {
    project_id: 'project',
    context: { agent_execution: { run_id: 'run', request_revision: 'revision', state: 'RUNNING', updated_at: 't0' } },
    statuses: Object.fromEntries(WIZARD_STEPS.map((step, index) => [step, index < count ? 'COMPLETE' : 'IN_PROGRESS'])),
    ...overrides,
  };
}

test('only a contiguous completed prefix is a stage boundary', () => {
  const state = workflow(4);
  state.statuses.capacity_timing = 'ERROR';
  state.statuses.simulation = 'COMPLETE';
  assert.equal(completedFrontier(state), 4);
  state.statuses.capacity_timing = 'WARNING';
  state.statuses.validation = 'APPROVED';
  assert.equal(completedFrontier(state), 7);
});

test('the real Capacity, Validation, Simulation, Results, Intelligence sequence receives a budget per completed frontier', () => {
  const watchdog = new WizardProgressWatchdog(0, workflow(4));
  for (const [count, now] of [[5, 39000], [6, 57000], [8, 224000], [9, 300000]]) {
    assert.equal(watchdog.observe(workflow(count), now).advanced, true);
    assert.equal(watchdog.remaining(now), 240000);
  }
});

test('heartbeats, READY retries, recovery and changed step labels do not reset the budget', () => {
  const watchdog = new WizardProgressWatchdog(0, workflow(4));
  for (const [index, state] of ['RUNNING', 'READY_TO_CONTINUE', 'BLOCKED', 'RUNNING'].entries()) {
    const current = workflow(4);
    Object.assign(current.context.agent_execution, { state, updated_at: 'heartbeat-' + index, step: WIZARD_STEPS[index], recoverable: true });
    assert.equal(watchdog.observe(current, (index + 1) * 50000).advanced, false);
  }
  assert.throws(() => watchdog.observe(workflow(4), 240000), /no new contiguous stage completion/);
});

test('a regression and reappearance of the same completion cannot extend the high-water mark', () => {
  const watchdog = new WizardProgressWatchdog(0, workflow(4));
  watchdog.observe(workflow(6), 10000);
  assert.equal(watchdog.observe(workflow(3), 100000).advanced, false);
  assert.equal(watchdog.observe(workflow(6), 249999).advanced, false);
  assert.throws(() => watchdog.remaining(250000), /no new contiguous stage completion/);
});

test('out-of-order downstream completion and repeated review do not reset the budget', () => {
  const watchdog = new WizardProgressWatchdog(0, workflow(4));
  const current = workflow(4);
  current.statuses.data_science_intelligence = 'WARNING';
  current.context.agent_execution.state = 'REVIEW_REQUIRED';
  assert.equal(watchdog.observe(current, 239999).advanced, false);
  assert.throws(() => watchdog.observe(current, 240000), /no new contiguous stage completion/);
});

for (const field of ['project', 'run', 'revision', 'missing']) {
  test(`a changed ${field} identity cannot extend or silently replace the active run`, () => {
    const watchdog = new WizardProgressWatchdog(0, workflow(4));
    const current = workflow(7);
    if (field === 'project') current.project_id = 'other';
    if (field === 'run') current.context.agent_execution.run_id = 'other';
    if (field === 'revision') current.context.agent_execution.request_revision = 'other';
    if (field === 'missing') delete current.context.agent_execution.request_revision;
    assert.throws(() => watchdog.observe(current, 1000), /project, run or request revision changed/);
  });
}

test('late progress cannot revive an expired section', () => {
  const watchdog = new WizardProgressWatchdog(0, workflow(4));
  assert.throws(() => watchdog.observe(workflow(9), 240001), /no new contiguous stage completion/);
});

test('the first valid run binds identity without rewarding startup delay', () => {
  const watchdog = new WizardProgressWatchdog(0);
  assert.equal(watchdog.observe({}, 100000).remainingMs, 140000);
  assert.equal(watchdog.observe(workflow(4), 200000).remainingMs, 40000);
  assert.throws(() => watchdog.observe(workflow(4), 240000), /no new contiguous stage completion/);
});
