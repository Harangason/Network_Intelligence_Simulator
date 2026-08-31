import assert from "node:assert/strict";
import test from "node:test";
import { agentBuildProgressPercent, agentRunIsActive, readAgentRunStatus } from "./agent-run-status.ts";

const run = {
  run_id: "wizard-run", state: "RUNNING", step: "routing", completed: 36, total: 150,
  message: "36 von 150 Routing-Pfaden vorbereitet.", updated_at: "2026-08-30T19:00:00Z",
};

test("restores progress only for the matching wizard run", () => {
  assert.deepEqual(readAgentRunStatus(run, run.run_id), run);
  assert.equal(readAgentRunStatus(run, "another-run"), null);
  for (const invalid of [null, {}, { ...run, total: "150" }, { ...run, completed: -1 },
    { ...run, updated_at: "invalid" }, { ...run, state: "UNKNOWN" }]) {
    assert.equal(readAgentRunStatus(invalid, run.run_id), null);
  }
});

test("retains a concrete failure after the chat stream is gone", () => {
  const blocked = { ...run, state: "BLOCKED", message: "Soll/Ist: Gateways 3/1." };
  assert.equal(readAgentRunStatus(blocked, run.run_id)?.message, blocked.message);
  assert.equal(agentRunIsActive(blocked, Date.parse(run.updated_at)), false);
});

test("derives progress from completed batches, including empty and finished work", () => {
  assert.equal(agentBuildProgressPercent(run), 24);
  assert.equal(agentBuildProgressPercent({ ...run, completed: 0, total: 0 }), 0);
  assert.equal(agentBuildProgressPercent({ ...run, completed: 150 }), 100);
  assert.equal(agentBuildProgressPercent({ ...run, completed: 160 }), 100);
});

test("heartbeats keep a restored run active but an interrupted run expires", () => {
  const started = Date.parse(run.updated_at);
  assert.equal(agentRunIsActive(run, started + 119_999), true);
  assert.equal(agentRunIsActive(run, started + 120_000), false);
  assert.equal(agentRunIsActive({ ...run, state: "REVIEW_REQUIRED" }, started), false);
  assert.equal(agentRunIsActive(null, started), false);
});

test("all downstream workflow steps survive reopening the wizard", () => {
  for (const step of ["network_editor", "parameters", "capacity_timing", "validation", "simulation", "results_analysis", "data_science_intelligence"]) {
    assert.equal(readAgentRunStatus({ ...run, step }, run.run_id)?.step, step);
  }
});
