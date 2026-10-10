import test from "node:test";
import assert from "node:assert/strict";
import { mergeSimulationResult, mergeSimulationSnapshots, selectSimulationSnapshot } from "./simulation-result.ts";

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

const old = { id: "old", job_id: "job-old", is_outdated: true, created_at: "2026-10-01T00:00:00Z" };
const latest = { id: "latest", job_id: "job-latest", is_outdated: false, created_at: "2026-10-02T00:00:00Z" };
const ready = { id: "ready", job_id: null, is_outdated: false, created_at: "2026-10-03T00:00:00Z" };

test("an absent browser session restores the project's latest executed snapshot, not an unexecuted draft", () => {
  assert.equal(selectSimulationSnapshot([old, ready, latest]), latest);
  assert.equal(selectSimulationSnapshot([ready]), null);
  assert.equal(selectSimulationSnapshot([]), null);
  assert.equal(selectSimulationSnapshot([old]), old);
});

test("explicit history selection stays exact and cannot silently fall back from another project's snapshot", () => {
  assert.equal(selectSimulationSnapshot([old, latest], { snapshotId: "old" }), old);
  assert.equal(selectSimulationSnapshot([old, latest], { jobId: "job-old" }), old);
  assert.equal(selectSimulationSnapshot([latest], { jobId: "local-standalone" }), null);
  assert.throws(() => selectSimulationSnapshot([latest], { snapshotId: "another-project" }));
  assert.throws(() => selectSimulationSnapshot([ready, latest], { snapshotId: "ready" }));
});

test("restoration preserves complete trace, signal, assessment and source data without mutating historical evidence", () => {
  const snapshot = { model_simulation: { signals: [{ id: "temperature" }] }, trace: { events: 17 }, assessment: { conformance: "FAIL" }, runtime_metrics: { available: true } };
  const registry = { registry_truncated: true, status: "completed" };
  const before = structuredClone(snapshot);
  const merged = mergeSimulationResult(registry, snapshot);
  assert.deepEqual(merged.model_simulation.signals, [{ id: "temperature" }]);
  assert.equal(merged.trace.events, 17);
  assert.equal(merged.assessment.conformance, "FAIL");
  assert.deepEqual(snapshot, before);
});

test("metadata refresh retains frozen prediction, inputs and measured result while applying the current outdated status", () => {
  const full = { ...latest, status: 'COMPLETED', calculated_metrics: { overview: { network_count: 2 } },
    configuration: { seed: 42 }, result: { trace: { events: 303 } } };
  const before = structuredClone(full);
  const metadata = { ...latest, status: 'OUTDATED', is_outdated: true, outdated_reason: 'Parameter geändert' };
  const refreshed = mergeSimulationSnapshots([metadata], [full, old]);
  assert.equal(refreshed.length, 1);
  assert.equal(refreshed[0].id, full.id);
  assert.deepEqual(refreshed[0].calculated_metrics, full.calculated_metrics);
  assert.deepEqual(refreshed[0].configuration, full.configuration);
  assert.deepEqual(refreshed[0].result, full.result);
  assert.equal(refreshed[0].is_outdated, true);
  assert.equal(refreshed[0].status, 'OUTDATED');
  assert.equal(refreshed[0].outdated_reason, 'Parameter geändert');
  assert.deepEqual(full, before);
  assert.equal(mergeSimulationSnapshots([old], [full])[0].result, undefined);
});
