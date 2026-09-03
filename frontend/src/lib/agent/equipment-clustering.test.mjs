import assert from "node:assert/strict";
import test from "node:test";

import { extractEngineeringSpecification } from "./engineering-specification.ts";
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
    bus_name: "Klima",
    devices: 3,
    counts: { ECU: 1, SensorController: 1, ActuatorController: 1 },
    evidence: ["ClimateController"],
  }, {
    cluster_id: "system:lighting",
    label: "Lighting",
    selected: false,
    network_id: "industrial-lin",
    network_label: "Industrial LIN",
    bus_name: "Lighting",
    devices: 1,
    counts: { SensorController: 1 },
    evidence: ["LightingSwitch"],
  }]);

  assert.equal(summary, "Klima -> Industrial CAN-FD / Klima (3 Teilnehmer)");
});

test("automotive equipment is grouped by domain families instead of singleton fallback names", () => {
  const clusters = buildEquipmentClusters([
    chain("Parkassistenz", "ECU", "CAN_FD"),
    chain("ParkassistenzSchaltausgang", "ActuatorController", "CAN_FD"),
    chain("Ultraschallverarbeitung", "ECU", "CAN_FD"),
    chain("VerticalAcceleration", "SensorController", "CAN_FD"),
    chain("OilLevel", "SensorController", "LIN"),
    chain("Wegfahrsperre", "ECU", "CAN_FD"),
    chain("SchiebedachSchaltausgang", "ActuatorController", "LIN"),
    chain("InfotainmentStellglied", "ActuatorController", "Ethernet"),
  ], [
    { id: "automotive-can_fd", label: "Automotive CAN-FD", count: 1 },
    { id: "automotive-lin", label: "Automotive LIN", count: 1 },
    { id: "automotive-ethernet", label: "Automotive Ethernet", count: 1 },
  ]);

  const labels = new Set(clusters.map((cluster) => cluster.label));
  assert.ok(labels.has("Fahrerassistenz"));
  assert.ok(labels.has("Antrieb"));
  assert.ok(labels.has("Zugang und Diebstahlschutz"));
  assert.ok(labels.has("Karosserie und Komfort"));
  assert.ok(labels.has("Infotainment und Anzeige"));
  assert.equal(clusters.find((cluster) => cluster.label === "Fahrerassistenz")?.devices.length, 4);
  assert.equal(clusters.find((cluster) => cluster.label === "Antrieb")?.devices[0]?.hardware_name, "OilLevel");
  assert.equal(clusters.some((cluster) => /^Oil|ParkassistenzSchalt|Vertical/.test(cluster.label)), false);
});

test("clusters count unique hardware and ignore misleading signal names", () => {
  const drive = chain("Antriebs", "ECU", "CAN_FD");
  const driveStatus = { ...drive, signal_name: "BrakeControlStatus", signal_display_name: "BrakeControlStatus" };
  const driveCurrent = { ...drive, signal_name: "BrakeControlCurrent", signal_display_name: "BrakeControlCurrent" };

  const clusters = buildEquipmentClusters([driveStatus, driveCurrent], [
    { id: "automotive-can_fd", label: "Automotive CAN-FD", count: 1 },
  ]);

  assert.equal(clusters.length, 1);
  assert.equal(clusters[0].label, "Antrieb");
  assert.equal(clusters[0].devices.length, 1);
  assert.deepEqual(clusters[0].counts, { ECU: 1 });
});

test("automotive scale clusters stay compact enough to guide network node planning", () => {
  const specification = [
    "Industrie: Automotive",
    "- 100 Sensoren",
    "- 100 Aktoren",
    "- 30 ECUs",
    "- Gateway 0",
    "Kommunikationssysteme:",
    "CAN FD 10",
    "LIN 25",
    "Automotive Ethernet 5",
    "SOME/IP 1",
  ].join("\n");
  const extracted = extractEngineeringSpecification(specification);
  const clusters = buildEquipmentClusters(extracted.chains, [
    { id: "automotive-can_fd", label: "automotive - can_fd", count: 10 },
    { id: "automotive-lin", label: "automotive - lin", count: 25 },
    { id: "automotive-ethernet", label: "automotive - automotive_ethernet", count: 5 },
    { id: "automotive-someip", label: "automotive - someip", count: 1 },
  ]);

  assert.equal(clusters.length, 10);
  assert.equal(clusters.some((cluster) => cluster.devices.length === 1), false);
  assert.equal(clusters.find((cluster) => cluster.devices.some((chain) => chain.hardware_name === "AmbientLight"))?.label, "Licht");
  assert.equal(clusters.find((cluster) => cluster.devices.some((chain) => chain.hardware_name === "AccessoryCurrent"))?.label, "Energie");
  assert.equal(clusters.find((cluster) => cluster.devices.some((chain) => chain.hardware_name === "TransmissionInputSpeed"))?.label, "Antrieb");
});
