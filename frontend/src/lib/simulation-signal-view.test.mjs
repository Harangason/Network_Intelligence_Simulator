import assert from "node:assert/strict";
import test from "node:test";

import { filterSignalSeries, formatSignalValue, initialSignalSelection, signalIsDynamic } from "./simulation-signal-view.ts";

const series = (overrides = {}) => ({
  signal_id: "s1", signal: "OperatingState", unit: "code", minimum: 0, maximum: 7,
  resolution: 1, cycle_ms: 10, behavior_type: "STATE_MACHINE", model_label: "RULE_BASED",
  semantic_type: "STATE", points: [{ time_s: 0, value: 1, golden_value: 1, faults: [], state: "INIT" }], ...overrides,
});

test("state values expose meaning and keep their raw code", () => {
  assert.equal(formatSignalValue(series(), series().points[0]), "INIT (1) code");
  const unlabeled = series({ points: [{ time_s: 0, value: 1, golden_value: 1, faults: [] }] });
  assert.equal(formatSignalValue(unlabeled, unlabeled.points[0]), "Zustand 1 · Bezeichnung fehlt");
});

test("dynamic filtering and bounded initial selection reduce rendered work", () => {
  const dynamic = series({ signal_id: "dynamic", signal: "DamperPosition", behavior_type: "PHYSICS_MODEL", model_label: "PHYSICS_BASED", semantic_type: "POSITION", points: [{ time_s: 0, value: 50, golden_value: 50, faults: [] }, { time_s: 1, value: 54, golden_value: 54, faults: [] }] });
  const staticSignal = series({ signal_id: "static", signal: "Static", points: [{ time_s: 0, value: 1, golden_value: 1, faults: [] }, { time_s: 1, value: 1, golden_value: 1, faults: [] }] });
  assert.equal(signalIsDynamic(dynamic), true);
  assert.deepEqual(filterSignalSeries([dynamic, staticSignal], { search: "", behavior: "DYNAMIC", kind: "ALL" }).map((item) => item.signal_id), ["dynamic"]);
  assert.equal(initialSignalSelection(Array.from({ length: 50 }, (_, index) => ({ ...dynamic, signal_id: String(index) }))).length, 18);
});
