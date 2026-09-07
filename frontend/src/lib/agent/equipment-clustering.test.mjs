import assert from "node:assert/strict";
import test from "node:test";

import { extractEngineeringSpecification } from "./engineering-specification.ts";
import { buildEquipmentClusters, equipmentClusterBusWarnings, equipmentClusterGraphPrompt, equipmentClusterSummary, equipmentTermMeaning } from "./equipment-clustering.ts";

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

test("industrial clusters assign endpoints to PLC controllers", () => {
  const clusters = buildEquipmentClusters([
    chain("LinePLC", "PLC", "ProfiNET"),
    chain("LineSensor", "SensorController", "ProfiNET"),
    chain("LineActuator", "ActuatorController", "ProfiNET"),
  ], [{ id: "industrial-profinet", label: "PROFINET", count: 1 }], "industrial_automation");

  const cluster = clusters.find((item) => item.controllers.some((controller) => controller.name === "LinePLC"));
  assert.ok(cluster);
  assert.equal(cluster.controllers[0].sensors.length, 1);
  assert.equal(cluster.controllers[0].actuators.length, 1);
  assert.equal(cluster.unassigned.length, 0);
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

test("agent graph prompt keeps ownership and HMI routes without verbose confidence metadata", () => {
  const prompt = equipmentClusterGraphPrompt([{
    cluster_id: "family:traction",
    label: "Antriebsstrang",
    selected: true,
    network_id: "rail-can",
    network_label: "Rail CAN",
    bus_name: "Traction_CAN",
    devices: 2,
    counts: { ECU: 1, ActuatorController: 1 },
    evidence: ["TractionControl"],
    tree: [{
      name: "TractionControl",
      interfaceType: "CAN",
      sensors: [],
      actuators: [{ name: "TractionValve", deviceType: "ActuatorController", interfaceType: "CAN", confidence: 0.98, reason: "same stem" }],
    }],
    unassigned: [],
    hmi_routes: [{ source: "TractionControl", target: "PassengerInformation", signals: ["TractionStatus"], path: ["TractionControl", "Rail CAN", "Gateway", "PassengerInformation"] }],
    validation: { valid: true, warnings: [] },
  }]);
  const serialized = JSON.stringify(prompt);
  assert.match(serialized, /TractionValve/);
  assert.match(serialized, /PassengerInformation/);
  assert.doesNotMatch(serialized, /confidence|same stem/);
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

test("rail graph assigns endpoints to ECUs and exposes traction signals to passenger HMI", () => {
  const clusters = buildEquipmentClusters([
    chain("TractionControl", "ECU", "CAN"),
    chain("TractionControlSchaltausgang", "ActuatorController", "CAN"),
    chain("Bogiesensorik", "ECU", "CAN"),
    chain("AxleTemperature", "SensorController", "CAN"),
    chain("PassengerInformation", "ECU", "Ethernet"),
  ], [
    { id: "rail-mvb", label: "Rail MVB", count: 2 },
    { id: "rail-etb", label: "Rail ETB Ethernet", count: 1 },
    { id: "rail-lin", label: "Rail LIN", count: 1 },
  ], "rail");

  const traction = clusters.find((cluster) => cluster.label === "Antriebsstrang");
  const runningGear = clusters.find((cluster) => cluster.label === "Fahrwerk / Drehgestell");
  assert.ok(traction);
  assert.ok(runningGear);
  assert.equal(traction.recommendedNetworkId, "rail-mvb");
  assert.equal(traction.controllers[0].actuators[0].name, "TractionControlSchaltausgang");
  assert.equal(runningGear.controllers[0].sensors[0].name, "AxleTemperature");
  assert.equal(traction.unassigned.length, 0);
  assert.equal(traction.hmiRoutes[0].target, "PassengerInformation");
  assert.deepEqual(traction.hmiRoutes[0].path, ["TractionControl", "Rail MVB", "Gateway", "PassengerInformation"]);
  assert.ok(equipmentClusterBusWarnings(traction, "rail-lin", "Rail LIN").length > 0);
});

test("ambiguous endpoints remain visible instead of being assigned round-robin", () => {
  const clusters = buildEquipmentClusters([
    chain("BrakeControl", "ECU", "CAN"),
    chain("SafetyInterlock", "ECU", "CAN"),
    chain("UnknownSafetySensor", "SensorController", "CAN"),
  ], [{ id: "rail-can", label: "Rail CAN", count: 1 }], "rail");
  const safety = clusters.find((cluster) => cluster.id === "family:safety");
  assert.ok(safety);
  assert.equal(safety.unassigned.length, 1);
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

test("automotive semantic roots keep airbag, doors, seats, climate and suspension in their proper families", () => {
  const clusters = buildEquipmentClusters([
    chain("Airbag", "ECU", "CAN_FD"),
    chain("Fahrertuer", "ECU", "LIN"),
    chain("Beifahrersitz", "ECU", "LIN"),
    chain("ClimateController", "ECU", "CAN_FD"),
    chain("AmbientTemperature", "SensorController", "LIN"),
    chain("ChassisController", "ECU", "CAN_FD"),
    chain("RearRightSuspensionTravel", "SensorController", "CAN_FD"),
  ], [
    { id: "automotive-can_fd", label: "Automotive CAN-FD", count: 2 },
    { id: "automotive-lin", label: "Automotive LIN", count: 2 },
  ], "automotive");
  const familyOf = (name) => clusters.find((cluster) => cluster.devices.some((device) => device.hardware_name === name))?.id;
  assert.equal(familyOf("Airbag"), "family:safety");
  assert.equal(familyOf("Fahrertuer"), "family:body_comfort");
  assert.equal(familyOf("Beifahrersitz"), "family:body_comfort");
  assert.equal(familyOf("AmbientTemperature"), "family:climate");
  assert.equal(familyOf("RearRightSuspensionTravel"), "family:chassis");
  assert.equal(equipmentTermMeaning("AccessoryCurrent").german, "Stromaufnahme der Nebenverbraucher");
});
