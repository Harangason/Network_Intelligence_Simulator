import assert from "node:assert/strict";
import test from "node:test";
import { agentBuildProgressPercent, agentRunHasDurableOutcome, agentRunIsActive, agentReviewStep, readAgentRunStatus, resolveAgentRunStep, wizardContinuationPrompt, wizardRunCanRetry, wizardRunNeedsAutomaticRecovery } from "./agent-run-status.ts";

const run = {
  run_id: "wizard-run", state: "RUNNING", step: "routing", completed: 36, total: 150,
  message: "36 von 150 Routing-Pfaden vorbereitet.", updated_at: "2026-08-30T19:00:00Z",
};

test('routing continuation does not restart the completed model stage', () => {
  const stale = { ...run, step: 'engineering_model', completed: 0, total: 0 };
  assert.equal(resolveAgentRunStep(stale, { engineering_model: 'COMPLETE', routing: 'EMPTY' }).step, 'routing');
  assert.equal(stale.step, 'engineering_model');
  assert.equal(resolveAgentRunStep(stale, { engineering_model: 'OUTDATED', routing: 'EMPTY' }).step, 'engineering_model');
  assert.equal(resolveAgentRunStep({ ...stale, state: 'CANCELED' }, { engineering_model: 'COMPLETE' }).state, 'CANCELED');
});

test('an amended request still reviews its changed model even when the old model remains complete', () => {
  const changed = { ...run, step: 'engineering_model', model_review_required: true, request_revision: 'new-revision' };
  assert.equal(resolveAgentRunStep(changed, { engineering_model: 'COMPLETE', routing: 'COMPLETE' }).step, 'engineering_model');
  assert.equal(resolveAgentRunStep({ ...changed, model_review_required: false }, { engineering_model: 'COMPLETE', routing: 'EMPTY' }).step, 'routing');
});

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

test("model review is distinct from routing review", () => {
  const applied = { ...run, state: "READY_TO_CONTINUE" };
  assert.equal(readAgentRunStatus(applied, run.run_id)?.state, "READY_TO_CONTINUE");
  assert.equal(agentReviewStep(applied), null);
  assert.equal(agentReviewStep({ ...run, state: "REVIEW_REQUIRED", step: "engineering_model" }), "engineering_model");
  assert.equal(agentReviewStep({ ...run, state: "REVIEW_REQUIRED" }), "routing");
  assert.equal(agentReviewStep(run), null);
});

test("heartbeats keep a restored run active but an interrupted run expires", () => {
  const started = Date.parse(run.updated_at);
  assert.equal(agentRunIsActive(run, started + 119_999), true);
  assert.equal(agentRunIsActive(run, started + 120_000), false);
  assert.equal(agentRunIsActive({ ...run, state: "REVIEW_REQUIRED" }, started), false);
  assert.equal(agentRunIsActive(null, started), false);
});

test("a durable server outcome supersedes a disconnected browser stream", () => {
  assert.equal(agentRunHasDurableOutcome({ ...run, state: "REVIEW_REQUIRED", step: "network_editor" }), true);
  assert.equal(agentRunHasDurableOutcome({ ...run, state: "READY_TO_CONTINUE" }), true);
  assert.equal(agentRunHasDurableOutcome({ ...run, state: "COMPLETED" }), true);
  assert.equal(agentRunHasDurableOutcome({ ...run, state: "RUNNING" }), false);
  assert.equal(agentRunHasDurableOutcome({ ...run, state: "BLOCKED" }), false);
});

test("all downstream workflow steps survive reopening the wizard", () => {
  for (const step of ["network_editor", "parameters", "capacity_timing", "validation", "simulation", "results_analysis", "data_science_intelligence"]) {
    assert.equal(readAgentRunStatus({ ...run, step }, run.run_id)?.step, step);
  }
});

test("an explicit retry remains available after earlier failed continuations", () => {
  assert.equal(wizardRunCanRetry(true, true, { ...run, state: "BLOCKED" }), true);
  assert.equal(wizardRunCanRetry(true, true, { ...run, state: "READY_TO_CONTINUE" }), true);
  assert.equal(wizardRunCanRetry(true, true, { ...run, state: "CANCELED" }), false);
  assert.equal(wizardRunCanRetry(false, true, { ...run, state: "BLOCKED" }), false);
});

test("wizard continuation stays compact so the backend can restore the durable request", () => {
  const prompt = wizardContinuationPrompt({ automatic: false, runId: "wizard-run" });
  assert.match(prompt, /Lauf-ID: wizard-run\./);
  assert.doesNotMatch(prompt, /Strukturierte Vorgaben fuer den Engineering-Agenten/);
  assert.ok(prompt.length < 1000);

  const targeted = wizardContinuationPrompt({ automatic: true, runId: "wizard-run", workflowTarget: "simulation" });
  assert.match(targeted, /Ziel: simulation\./);
  assert.ok(targeted.length < 300);
});

test("only an interrupted backend run is resumed automatically once", () => {
  const base = { runPaused: true, hasResumablePrompt: true, automaticResumeCount: 0, restoredSession: false };
  assert.equal(wizardRunNeedsAutomaticRecovery({ ...base, run: { ...run, state: "BLOCKED", recoverable: true } }), true);
  assert.equal(wizardRunNeedsAutomaticRecovery({ ...base, run: { ...run, updated_at: "2026-09-08T09:00:00Z" }, now: Date.parse("2026-09-08T09:03:00Z") }), true);
  assert.equal(wizardRunNeedsAutomaticRecovery({ ...base, run: { ...run, state: "BLOCKED", recoverable: false } }), false);
  assert.equal(wizardRunNeedsAutomaticRecovery({ ...base, run: null, restoredSession: true }), true);
  assert.equal(wizardRunNeedsAutomaticRecovery({ ...base, run: null, restoredSession: false }), false);
  assert.equal(wizardRunNeedsAutomaticRecovery({ ...base, run: { ...run, state: "BLOCKED", recoverable: true }, automaticResumeCount: 1 }), false);
});
