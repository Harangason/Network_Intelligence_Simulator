import assert from "node:assert/strict";
import test from "node:test";
import { buildCanonicalSignalDefinition, buildSignalOptimizationProposal, calculateSignalBitRequirement } from "./signal-architecture.ts";

function requirement(signal) {
  return calculateSignalBitRequirement(buildCanonicalSignalDefinition(signal));
}

test("numeric requirements use range and resolution", () => {
  const result = requirement({
    id: "speed",
    name: "RotationalSpeed",
    semantic: { semantic_type: "NUMERIC", meaning: "Rotational process speed" },
    data_type: "unsigned",
    min_value: 0,
    max_value: 5000,
    factor: 50,
    offset_value: 0,
    length_bits: 8,
    data: { resolution: 50 },
  });

  assert.equal(result.semanticType, "NUMERIC");
  assert.equal(result.valueCount, 101);
  assert.equal(result.requiredBits, 7);
  assert.equal(result.status, "OVERDIMENSIONED");
});

test("enum and state requirements use defined values and reserve values", () => {
  const states = ["OFF", "INIT", "READY", "STARTING", "RUNNING", "STOPPING", "STANDBY", "LIMITED", "WARNING", "ERROR", "EMERGENCY_STOP", "UNKNOWN"];
  const result = requirement({
    id: "state",
    name: "DriveOperatingState",
    semantic: { semantic_type: "STATE" },
    data_type: "enum",
    length_bits: 8,
    data: { enum_values: Object.fromEntries(states.map((name, index) => [name, index])) },
  });

  assert.equal(result.requiredBits, 4);
  assert.equal(result.status, "OVERDIMENSIONED");
});

test("boolean, flag, counter and bitfield requirements are not numeric range shortcuts", () => {
  assert.equal(requirement({ id: "b", name: "Enabled", semantic: { semantic_type: "BOOLEAN" }, length_bits: 8 }).requiredBits, 1);
  assert.equal(requirement({ id: "f", name: "WarningFlag", semantic: { semantic_type: "FLAG" }, length_bits: 1 }).requiredBits, 1);
  assert.equal(requirement({ id: "c", name: "RollingCounter", semantic: { semantic_type: "COUNTER" }, min_value: 0, max_value: 15, length_bits: 4 }).requiredBits, 4);
  assert.equal(requirement({ id: "bf", name: "StatusBits", semantic: { semantic_type: "BITFIELD" }, length_bits: 8, quality: { bit_members: [{ bit: 0 }, { bit: 1 }, { bit: 2 }, { bit: 3 }] } }).requiredBits, 4);
});

test("legacy uint8 min max values remain unknown until semantically classified", () => {
  const result = requirement({ id: "legacy", name: "LegacyValue", data_type: "unsigned", min_value: 0, max_value: 255, factor: 1, offset_value: 0, length_bits: 8 });

  assert.equal(result.semanticType, "UNKNOWN");
  assert.equal(result.requiredBits, null);
  assert.equal(result.status, "UNKNOWN");
  assert.match(result.reason, /Semantik fehlt/);
});

test("legacy status names are treated as conservative state signals", () => {
  const result = requirement({ id: "status", name: "ProcessStatus", data_type: "unsigned", min_value: 0, max_value: 255, factor: 1, offset_value: 0, length_bits: 8 });

  assert.equal(result.semanticType, "STATE");
  assert.equal(result.valueCount, 8);
  assert.equal(result.requiredBits, 3);
  assert.equal(result.status, "OVERDIMENSIONED");
});

test("optimization proposals describe savings without mutating the signal", () => {
  const signal = buildCanonicalSignalDefinition({
    id: "state",
    name: "DriveOperatingState",
    semantic: { semantic_type: "ENUM" },
    length_bits: 8,
    data: { allowed_values: ["OFF", "INIT", "READY", "RUNNING"], reserved_values: ["RESERVED"] },
  });
  const proposal = buildSignalOptimizationProposal(signal);

  assert.equal(signal.encoding.bitLength, 8);
  assert.equal(proposal.requiredBits, 3);
  assert.equal(proposal.potentialSavingBits, 5);
  assert.equal(proposal.status, "OVERDIMENSIONED");
});
