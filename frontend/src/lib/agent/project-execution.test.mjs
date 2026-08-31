import assert from "node:assert/strict";
import test from "node:test";
import { runExclusiveProjectBuild } from "./project-execution.ts";

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
