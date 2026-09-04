import assert from "node:assert/strict";
import test from "node:test";
import {
  isCompletedProjectWorkflowRun,
  isCompletedProjectWorkflowTarget,
  runExclusiveProjectBuild,
} from "./project-execution.ts";

test("completed workflow runs are idempotent per run id", () => {
  const workflow = {
    context: {
      agent_execution: { run_id: "run-42", state: "COMPLETED" },
    },
  };

  assert.equal(isCompletedProjectWorkflowRun(workflow, "run-42"), true);
  assert.equal(isCompletedProjectWorkflowRun(workflow, "run-43"), false);
  assert.equal(isCompletedProjectWorkflowRun({ context: {} }, "run-42"), false);
});

test("completed automatic targets are idempotent independent of a stale wizard run id", () => {
  const workflow = {
    context: {
      agent_execution: { run_id: "historic-run", state: "COMPLETED", step: "data_science_intelligence" },
    },
  };

  assert.equal(isCompletedProjectWorkflowTarget(workflow, "data_science_intelligence"), true);
  assert.equal(isCompletedProjectWorkflowTarget(workflow, "simulation"), false);
});

test("parallel starts cannot rebuild the same project", async () => {
  let release;
  const first = runExclusiveProjectBuild("a", () => new Promise((resolve) => { release = resolve; }));
  await assert.rejects(runExclusiveProjectBuild("a", async () => assert.fail("duplicate execution")), /bereits ein Agent/);
  assert.equal(await runExclusiveProjectBuild("b", async () => 2), 2);
  release(1);
  assert.equal(await first, 1);
  assert.equal(await runExclusiveProjectBuild("a", async () => 3), 3);
});

test("failed builds release the project for an explicit retry", async () => {
  await assert.rejects(runExclusiveProjectBuild("a", async () => { throw new Error("timeout"); }), /timeout/);
  assert.equal(await runExclusiveProjectBuild("a", async () => "resumed"), "resumed");
});
