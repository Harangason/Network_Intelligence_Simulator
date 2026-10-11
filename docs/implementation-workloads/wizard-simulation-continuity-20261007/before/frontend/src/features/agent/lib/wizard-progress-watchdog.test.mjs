import test from 'node:test';
import assert from 'node:assert/strict';
import { completedFrontier, WizardProgressWatchdog, WIZARD_STEPS } from '../../../../e2e/support/wizard-progress-watchdog.ts';

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

function warningProof() {
  const approval = { snapshot_id: 'snapshot', signature: 'signature', actor: 'reviewer', approved_at: new Date(101000).toISOString() };
  return { before: workflow(6), after: workflow(6, { parameters: { preflight_warning_approval: approval } }), snapshotId: 'snapshot',
    requestProject: 'project', submitted: { snapshot_id: 'snapshot', actor: 'reviewer' }, status: 200,
    response: { approval: { ...approval }, preflight: { warnings_allowed: true, ready_for_simulation: true } },
    started: 200000, startedWall: 100000, finishedWall: 140000 };
}

test('a distinct durable warning approval starts one section; a separate valid write may cross the old deadline', () => {
  const watchdog = new WizardProgressWatchdog(0, workflow(6)), proof = warningProof();
  assert.equal(watchdog.commitWarningReview(proof, 240001).remainingMs, 240000);
  assert.equal(watchdog.remaining(480000), 1);
  assert.throws(() => watchdog.remaining(480001), /no new contiguous/);
});

for (const [name, mutate] of [
  ['failed HTTP', p => p.status = 500], ['missing receipt', p => delete p.response.approval],
  ['wrong submitted snapshot', p => p.submitted.snapshot_id = 'old'], ['wrong current snapshot', p => p.snapshotId = 'old'],
  ['foreign project', p => p.after.project_id = 'foreign'], ['foreign request', p => p.requestProject = 'foreign'],
  ['changed run', p => p.after.context.agent_execution.run_id = 'new'], ['changed revision', p => p.after.context.agent_execution.request_revision = 'new'],
  ['wrong actor', p => p.submitted.actor = 'other'], ['missing actor', p => p.submitted.actor = ''],
  ['undurable receipt', p => delete p.after.parameters.preflight_warning_approval],
  ['changed stored signature', p => p.after.parameters.preflight_warning_approval.signature = 'other'],
  ['not approved', p => p.response.preflight.warnings_allowed = false], ['not ready', p => p.response.preflight.ready_for_simulation = false],
  ['stale receipt', p => p.response.approval.approved_at = new Date(99000).toISOString()],
  ['future receipt', p => p.response.approval.approved_at = new Date(150000).toISOString()],
  ['no-op existing approval', p => p.before.parameters = structuredClone(p.after.parameters)],
  ['same warnings under a refreshed snapshot', p => p.before.parameters = { preflight_warning_approval: { ...p.response.approval, snapshot_id: 'earlier-snapshot' } }],
  ['late manual start', p => p.started = 240001], ['write exceeded180s', p => p.started = 1000],
]) test(`invalid ${name} cannot extend the warning-review clock`, () => {
  const watchdog = new WizardProgressWatchdog(0, workflow(6)), proof = warningProof();mutate(proof);
  assert.throws(() => watchdog.commitWarningReview(proof, 240002));
  assert.throws(() => watchdog.remaining(240002), /no new contiguous/);
});

test('a repeated warning receipt never resets again, including timestamp-only retries', () => {
  const watchdog = new WizardProgressWatchdog(0, workflow(6)), proof = warningProof();
  watchdog.commitWarningReview(proof, 240001);
  proof.started = 250000;proof.startedWall = 100000;
  assert.throws(() => watchdog.commitWarningReview(proof, 260000), /Repeated or no-op/);
  proof.response.approval.approved_at = new Date(102000).toISOString();proof.after.parameters.preflight_warning_approval.approved_at = proof.response.approval.approved_at;
  assert.throws(() => watchdog.commitWarningReview(proof, 270000), /Repeated or no-op/);
  assert.equal(watchdog.remaining(270000), 210001);
});

for (const field of ['now', 'started', 'startedWall', 'finishedWall']) for (const value of [NaN, Infinity, -Infinity])
  test(`nonfinite ${field} ${value} cannot reset or corrupt a live clock`, () => {
    const watchdog = new WizardProgressWatchdog(0, workflow(6)), proof = warningProof();
    if (field !== 'now') proof[field] = value;
    assert.throws(() => watchdog.commitWarningReview(proof, field === 'now' ? value : 230000), /finite monotonic and wall clocks/);
    assert.equal(watchdog.remaining(239999), 1);
  });
