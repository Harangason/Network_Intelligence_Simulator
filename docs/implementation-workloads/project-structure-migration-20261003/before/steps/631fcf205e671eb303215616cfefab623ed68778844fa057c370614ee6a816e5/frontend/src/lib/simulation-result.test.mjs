import test from "node:test";
import assert from "node:assert/strict";
import { mergeSimulationResult } from "./simulation-result.ts";

test("compact registry data cannot hide a snapshot's measured results", () => {
  const full = { status: "completed", trace: { events: 101 }, runtime_metrics: { available: true } };
  const compact = { status: "completed", registry_truncated: true, artifact_count: 6 };
  const merged = mergeSimulationResult(compact, full);
  assert.equal(merged.trace.events, 101);
  assert.equal(merged.runtime_metrics.available, true);
  assert.equal(merged.artifact_count, 6);
  assert.equal(mergeSimulationResult(undefined, full), full);
  assert.equal(mergeSimulationResult(full, undefined), full);
});
