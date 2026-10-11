import assert from "node:assert/strict";
import test from "node:test";
import {
  defaultSimulationFormats,
  groupSimulationFormats,
  mergeSimulationFormats,
  simulationFormatExtension,
  projectSimulationFormats,
} from "./simulation-formats.ts";

test("format catalog exposes universal and native simulator formats in stable order", () => {
  const formats = mergeSimulationFormats(["pcapng", "universal-jsonl"], ["asc", "blf"], defaultSimulationFormats);
  assert.deepEqual(formats, ["universal-jsonl", "universal-csv", "blf", "asc", "pcapng"]);
});

test("project defaults select BLF/DBC for CAN and PCAP for Ethernet from registered profiles", () => {
  assert.deepEqual(projectSimulationFormats([{ native_formats: ["blf", "dbc"] }]), ["blf", "dbc"]);
  assert.deepEqual(projectSimulationFormats([{ native_formats: ["pcap", "pcapng"] }]), ["pcap"]);
  assert.deepEqual(projectSimulationFormats([{ native_formats: ["blf", "dbc"] }, { native_formats: ["pcap"] }]), ["blf", "dbc", "pcap"]);
  assert.deepEqual(projectSimulationFormats([{ native_formats: ["ldf"] }]), defaultSimulationFormats);
});

test("output format groups keep CAN and Ethernet choices visible", () => {
  const groups = groupSimulationFormats(["universal-jsonl", "blf", "asc", "pcap", "pcapng"]);
  assert.deepEqual(groups.map((group) => group.label), ["Universell", "CAN / Fahrzeugdaten", "Ethernet"]);
  assert.deepEqual(groups[1].formats.map((format) => format.id), ["blf", "asc"]);
});

test("local artifact names use the selected native extension", () => {
  assert.equal(simulationFormatExtension("universal-jsonl"), "jsonl");
  assert.equal(simulationFormatExtension("universal-csv"), "csv");
  assert.equal(simulationFormatExtension("asc"), "asc");
  assert.equal(simulationFormatExtension("fibex"), "fibex.xml");
});
