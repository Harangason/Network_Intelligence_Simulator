import assert from "node:assert/strict";
import test from "node:test";

import { engineeringAgentWorkflowProgress } from "./agent-task-events.ts";

function workflowState(overrides = {}) {
  const statuses = {
    engineering_model: "COMPLETE",
    routing: "COMPLETE",
    network_editor: "COMPLETE",
    parameters: "APPROVED",
    capacity_timing: "COMPLETE",
    validation: "COMPLETE",
    simulation: "COMPLETE",
    results_analysis: "COMPLETE",
    data_science_intelligence: "COMPLETE",
    ...overrides,
  };
  const versions = Object.fromEntries(Object.keys(statuses).map((step, index) => [step, index + 1]));
  return { statuses, versions };
}

test("workflow continuation pauses at routing review instead of restarting", () => {
  const { statuses, versions } = workflowState({ routing: "IN_PROGRESS" });
  const progress = engineeringAgentWorkflowProgress(
    { workflowTarget: "data_science_intelligence" },
    statuses,
    versions,
  );

  assert.equal(progress.currentStep, "routing");
  assert.equal(progress.blockedStep, "routing");
  assert.equal(progress.complete, false);
});

test("workflow continuation still runs automatic technical steps", () => {
  const { statuses, versions } = workflowState({ network_editor: "EMPTY" });
  const progress = engineeringAgentWorkflowProgress(
    { workflowTarget: "data_science_intelligence" },
    statuses,
    versions,
  );

  assert.equal(progress.currentStep, "network_editor");
  assert.equal(progress.blockedStep, undefined);
  assert.equal(progress.complete, false);
});
