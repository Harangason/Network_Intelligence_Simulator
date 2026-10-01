import assert from "node:assert/strict";
import test from "node:test";
import { createIntelligenceLoader } from "./intelligence-loader.ts";

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function setup(overrides = {}) {
  const state = { project: "a", snapshot: null, proposals: [], loading: true, error: null, resets: 0, reads: 0, assessments: 0, notifications: 0 };
  const loader = createIntelligenceLoader({
    readProjectId: () => state.project,
    getSnapshot: async (projectId) => { ++state.reads; return { id: projectId }; },
    assessSnapshot: async (projectId) => { ++state.assessments; return { id: `${projectId}-assessed` }; },
    getProposals: async (projectId) => ({ items: [{ proposal_id: projectId }] }),
    onProjectChange: () => { ++state.resets; state.snapshot = null; state.proposals = []; state.error = null; },
    onSnapshot: (value) => { state.snapshot = value; },
    onProposals: (value) => { state.proposals = value; },
    onLoading: (value) => { state.loading = value; },
    onError: (value) => { state.error = value; },
    onAssessed: () => { ++state.notifications; },
    ...overrides,
  });
  return { loader, state };
}

test("initial load and repeated background refreshes retain the visible snapshot", async () => {
  const { loader, state } = setup();
  await loader.refresh();
  for (let iteration = 0; iteration < 25; iteration++) {
    const visible = state.snapshot;
    const pending = loader.refresh();
    assert.equal(state.loading, true);
    assert.equal(state.snapshot, visible);
    await pending;
    assert.equal(state.loading, false);
  }
  assert.equal(state.resets, 1);
  assert.equal(state.reads, 26);
  assert.equal(state.assessments, 0);
});

test("poll, focus and workflow events share an in-flight request", async () => {
  const gate = deferred();
  let calls = 0;
  const { loader } = setup({ getSnapshot: () => { ++calls; return gate.promise; } });
  const first = loader.refresh();
  for (let i = 0; i < 25; i++) assert.equal(loader.refresh(), first);
  await Promise.resolve();
  assert.equal(calls, 1);
  gate.resolve({ id: "snapshot" });
  await first;
});

test("only a missing snapshot triggers an initial assessment; its notification does not loop", async () => {
  const { loader, state } = setup({
    getSnapshot: async () => { throw Object.assign(new Error("Missing"), { status: 404 }); },
    onAssessed: () => { ++state.notifications; void loader.refresh(); },
  });
  await loader.refresh();
  assert.equal(state.assessments, 1);
  assert.equal(state.notifications, 1);
  assert.equal(state.snapshot.id, "a-assessed");
  assert.equal(state.loading, false);
});

test("network, authorization and server errors never trigger an assessment or clear existing data", async () => {
  for (const status of [undefined, 401, 403, 500, 503]) {
    let failure = null;
    const { loader, state } = setup({ getSnapshot: async () => {
      if (failure) throw failure;
      return { id: "existing" };
    } });
    await loader.refresh();
    failure = Object.assign(new Error("Unavailable"), { status });
    await loader.refresh();
    assert.equal(state.snapshot.id, "existing");
    assert.equal(state.proposals.length, 1);
    assert.equal(state.error, failure);
    assert.equal(state.assessments, 0);
    assert.equal(state.loading, false);
  }
});

test("publishes the assessment before proposals finish and retains it if they fail", async () => {
  const gate = deferred();
  const reachedProposals = deferred();
  const { loader, state } = setup({ getProposals: () => { reachedProposals.resolve(); return gate.promise; } });
  const pending = loader.refresh();
  await reachedProposals.promise;
  assert.equal(state.snapshot.id, "a");
  assert.equal(state.loading, true);
  gate.reject(new Error("Proposals unavailable"));
  await pending;
  assert.equal(state.snapshot.id, "a");
  assert.equal(state.error.message, "Proposals unavailable");
  assert.equal(state.loading, false);
});

test("one explicit reassessment follows an in-flight read without racing it", async () => {
  const gate = deferred();
  const { loader, state } = setup({ getSnapshot: () => gate.promise });
  const read = loader.refresh();
  const assess = loader.refresh(true);
  assert.equal(loader.refresh(true), assess);
  gate.resolve({ id: "old" });
  await read;
  await assess;
  assert.equal(state.assessments, 1);
  assert.equal(state.snapshot.id, "a-assessed");
});

test("changing projects ignores a late snapshot from the previous project", async () => {
  const gate = deferred();
  const projects = [];
  const { loader, state } = setup({ getSnapshot: (projectId) => {
    projects.push(projectId);
    return projectId === "a" ? gate.promise : Promise.resolve({ id: projectId });
  } });
  const old = loader.refresh();
  await Promise.resolve();
  state.project = "b";
  await loader.refresh();
  gate.resolve({ id: "old-a" });
  await old;
  assert.deepEqual(projects, ["a", "b"]);
  assert.equal(state.snapshot.id, "b");
  assert.equal(state.proposals[0].proposal_id, "b");
  assert.equal(state.loading, false);
});

test("late proposal responses cannot cross projects", async () => {
  const gate = deferred();
  const reachedProposals = deferred();
  const projects = [];
  const { loader, state } = setup({ getProposals: (projectId) => {
    projects.push(projectId);
    if (projectId === "a") { reachedProposals.resolve(); return gate.promise; }
    return Promise.resolve({ items: [{ proposal_id: projectId }] });
  } });
  const old = loader.refresh();
  await reachedProposals.promise;
  state.project = "b";
  await loader.refresh();
  gate.resolve({ items: [{ proposal_id: "old-a" }] });
  await old;
  assert.deepEqual(projects, ["a", "b"]);
  assert.equal(state.proposals[0].proposal_id, "b");
});

test("unmount discards pending work and queued reassessments", async () => {
  const gate = deferred();
  const { loader, state } = setup({ getSnapshot: () => gate.promise });
  const read = loader.refresh();
  const assess = loader.refresh(true);
  await Promise.resolve();
  loader.dispose();
  gate.resolve({ id: "obsolete" });
  await read;
  await assess;
  await loader.refresh();
  assert.equal(state.snapshot, null);
  assert.equal(state.assessments, 0);
});

test("an abandoned project request does not block a later refresh", async () => {
  const { loader, state } = setup();
  const abandoned = loader.refresh();
  state.project = "b";
  await abandoned;
  state.project = "a";
  await loader.refresh();
  assert.equal(state.snapshot.id, "a");
  assert.equal(state.loading, false);
});
