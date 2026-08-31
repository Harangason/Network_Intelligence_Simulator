import assert from "node:assert/strict";
import test from "node:test";

import { buildEquipmentClusters, equipmentClusterSummary } from "./equipment-clustering.ts";

function chain(name, deviceType, interfaceType = "LIN") {
  return {
    hardware_name: name,
    hardware_description: `${name} device`,
    device_type: deviceType,
    function_name: `${name}_Function`,
    function_description: `${name} control loop`,
    interface_name: `${name}_${interfaceType}`,
    interface_type: interfaceType,
    message_name: `${name}Data`,
    message_id_hex: "0x180",
    direction: "tx",
    cycle_ms: 20,
    dlc: 1,
    signal_name: `${name}Status`,
    signal_display_name: `${name}Status`,
    start_bit: 0,
    length_bits: 3,
    byte_order: "little_endian",
    data_type: "unsigned",
    factor: 1,
    offset_value: 0,
    semantic: { category: name },
    domain: "neutral",
  };
}

test("related thermal equipment is clustered and can be assigned to CAN-FD", () => {
  const clusters = buildEquipmentClusters([
    chain("ClimateController", "ECU", "CAN_FD"),
    chain("ClimateTemperature", "SensorController"),
    chain("HVACValve", "ActuatorController"),
    chain("LightingSwitch", "SensorController"),
  ], [
    { id: "industrial-lin", label: "Industrial LIN", count: 8 },
    { id: "industrial-can_fd", label: "Industrial CAN-FD", count: 2 },
  ]);

  const thermal = clusters.find((cluster) => cluster.label === "Klima");
  assert.ok(thermal);
  assert.equal(thermal.devices.length, 3);
  assert.equal(thermal.recommendedNetworkId, "industrial-can_fd");
  assert.deepEqual(thermal.counts, { ECU: 1, SensorController: 1, ActuatorController: 1 });
});

test("cluster summaries keep the user network choice visible for the agent prompt", () => {
  const summary = equipmentClusterSummary([{
    cluster_id: "rule:climate",
    label: "Klima",
    selected: true,
    network_id: "industrial-can_fd",
    network_label: "Industrial CAN-FD",
    devices: 3,
    counts: { ECU: 1, SensorController: 1, ActuatorController: 1 },
    evidence: ["ClimateController"],
  }, {
    cluster_id: "system:lighting",
    label: "Lighting",
    selected: false,
    network_id: "industrial-lin",
    network_label: "Industrial LIN",
    devices: 1,
    counts: { SensorController: 1 },
    evidence: ["LightingSwitch"],
  }]);

  assert.equal(summary, "Klima -> Industrial CAN-FD (3 Teilnehmer)");
});
