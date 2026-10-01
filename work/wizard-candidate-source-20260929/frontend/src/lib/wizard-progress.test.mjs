import assert from "node:assert/strict";
import test from "node:test";
import { parameterProgressTarget, parametersAreWorking, symbolicProgressAt } from "./wizard-progress.ts";

test("only running step four animates, including a resumed backend run", () => {
  for (const step of ["engineering_model", "routing", "network_editor", "capacity_timing", "validation", "simulation", "results_analysis", "data_science_intelligence"]) {
    assert.equal(parametersAreWorking(true, { step, state: "RUNNING" }, "input-available"), false, step);
  }
  assert.equal(parametersAreWorking(true, { step: "parameters", state: "RUNNING" }), true);
  for (const state of ["BLOCKED", "REVIEW_REQUIRED", "READY_TO_CONTINUE", "COMPLETED", "CANCELED"]) {
    assert.equal(parametersAreWorking(true, { step: "parameters", state }, "input-available"), false, state);
  }
  assert.equal(parametersAreWorking(false, { step: "parameters", state: "RUNNING" }), false);
  assert.equal(parametersAreWorking(true, null, "input-streaming"), true);
  assert.equal(parametersAreWorking(true, null, "output-available"), false);
});

test("approved default parameters use the canonical workflow completion", () => {
  assert.equal(parameterProgressTarget(false, undefined, 100), 100);
  assert.equal(parameterProgressTarget(false, "input-available", 100), 90);
  assert.equal(parameterProgressTarget(true, "input-available", 100), 90);
  assert.equal(parameterProgressTarget(false, "output-available", 100), 100);
  assert.equal(parameterProgressTarget(true, undefined, 100), 100);
});

test("analysis heading follows the actual workflow phase", async () => {
  const { wizardAnalysisHeading } = await import("./wizard-progress.ts");
  assert.equal(wizardAnalysisHeading({
    agentPending: true,
    currentStep: "Routing-Tabelle",
    executionState: "RUNNING",
    modelReviewPending: false,
    routingReviewPending: false,
    runPaused: false,
  }), "Routing-Tabelle wird bearbeitet");
  assert.equal(wizardAnalysisHeading({
    agentPending: false,
    currentStep: "Routing-Tabelle",
    executionState: "REVIEW_REQUIRED",
    modelReviewPending: false,
    routingReviewPending: true,
    runPaused: false,
  }), "Analyse bereit zur Freigabe");
});

test("parameter warnings and errors are not converted into completion", () => {
  assert.equal(parameterProgressTarget(true, undefined, 85), 85);
  assert.equal(parameterProgressTarget(true, "output-error", 40), 40);
  assert.equal(parameterProgressTarget(false, "output-error", 40), 0);
});

test("symbolic progress increases smoothly and stops at its target", () => {
  const frames = Array.from({ length: 33 }, (_, index) => symbolicProgressAt(0, 90, index * 50));
  assert.equal(frames[0], 0);
  assert(frames.some(value => value > 0 && value < 90));
  assert(frames.every((value, index) => value >= (frames[index - 1] ?? 0) && value <= 90));
  assert.equal(frames.at(-1), 90);
  assert.equal(symbolicProgressAt(90, 100, 1600), 100);
  assert.equal(symbolicProgressAt(0, 100, 60_000), 100);
});

test("a new target animates from the current value and stays in bounds", () => {
  assert.equal(symbolicProgressAt(42, 100, 0), 42);
  assert.equal(symbolicProgressAt(100, 40, 1600), 40);
  assert.equal(symbolicProgressAt(0, 150, 1600), 100);
  assert.equal(symbolicProgressAt(0, -50, 1600), 0);
});
