import assert from "node:assert/strict";
import test from "node:test";

import { extractEngineeringSpecification } from "./engineering-specification.ts";
import { hmiSignalKey, selectHmiSignals } from "./equipment-clustering.ts";
import { buildEquipmentClusters, equipmentClusterBusIssues, reviewedEquipmentCluster, equipmentClusterBusWarnings, equipmentClusterGraphPrompt, equipmentClusterSummary, equipmentTermMeaning } from "./equipment-clustering.ts";

test('explicit task participants and controller ownership reach the cluster graph and Anzeige routing', () => {
  const task = 'Erzeuge ein Automotive CAN-FD Netzwerk mit einem Gateway System, den ECUs Motorsteuerung und Anzeige, einem Sensor MotorTemperature und einem Aktor MotorValve. MotorTemperature wird von Motorsteuerung ausgewertet. Motorsteuerung steuert MotorValve. Statuswerte werden an Anzeige und System übermittelt.';
  const spec = extractEngineeringSpecification(task, { gateways: 1, ecus: 2, sensors: 1, actuators: 1 }, 'automotive', true);
  const clusters = buildEquipmentClusters(spec.chains, [{ id: 'can_fd', label: 'CAN-FD', count: 1 }], 'automotive');
  const controllers = clusters.flatMap(cluster => cluster.controllers);
  assert.deepEqual(controllers.map(controller => controller.name).sort(), ['Anzeige', 'Motorsteuerung']);
  const motor = controllers.find(controller => controller.name === 'Motorsteuerung');
  assert.deepEqual(motor.sensors.map(sensor => sensor.name), ['MotorTemperature']);
  assert.deepEqual(motor.actuators.map(actuator => actuator.name), ['MotorValve']);
  assert.match(motor.sensors[0].reason, /Nutzer ausdrücklich/);
  assert.ok(clusters.flatMap(cluster => cluster.hmiRoutes).some(route => route.source === 'Motorsteuerung' && route.target === 'Anzeige'));
  assert.equal(clusters.flatMap(cluster => cluster.unassigned).length, 0);
});

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

test("LIN findings identify exact participants and values, keeping cluster rules separate", () => {
  const cluster = { label: "Antriebsstrang", devices: [chain("Motor", "ECU"), { ...chain("Slow", "SensorController"), cycle_ms: 50 }, { ...chain("Unknown", "SensorController"), cycle_ms: 0 }], unassigned: [] };
  const issues = equipmentClusterBusIssues(cluster, "lin");
  assert.deepEqual(issues[0].affected.map(item => item.name), ["Motor"]);
  assert.match(issues[0].affected[0].detail, /MotorStatus: 20 ms/);
  assert.equal(issues[1].code, "lin-cluster");
  assert.deepEqual(issues[1].affected, []);
  assert.match(issues[1].action, /Clusterbezeichnung/);
  assert.deepEqual(equipmentClusterBusIssues(cluster, "can-fd"), []);
});

test("display signals default off, toggle per target and retain exclusions in the submitted graph", () => {
  const routes = ['Kombiinstrument', 'HeadUpDisplay'].map(target => ({ source: 'Motor', target, signals: ['Drehzahl', 'Health'], path: ['Motor', target] }));
  assert.ok(selectHmiSignals(routes).every(route => route.signals.length === 0 && route.excluded_signals.length === 2));
  const selected = selectHmiSignals(routes, { [hmiSignalKey(routes[0], 'Drehzahl')]: true });
  assert.deepEqual(selected[0].signals, ['Drehzahl']);
  assert.deepEqual(selected[0].excluded_signals, ['Health']);
  assert.deepEqual(selected[1].signals, []);
  const serialized = JSON.parse(JSON.stringify(equipmentClusterGraphPrompt([{ selected: true, hmi_routes: selected }])));
  assert.deepEqual(serialized[0].hmi_routes, selected);
  assert.deepEqual(selectHmiSignals(routes, { [hmiSignalKey(routes[0], 'Drehzahl')]: false })[0].signals, []);
});

test("warnings follow reviewed ownership and consider every signal of moved hardware", () => {
  const leaf = { name: "Fast", deviceType: "SensorController", reason: "Owner fehlt" };
  const source = { label: "Komfort", controllers: [], unassigned: [], devices: [chain("Fast", "SensorController")] };
  const chains = [{ ...chain("Fast", "SensorController"), cycle_ms: 100 }, { ...chain("Fast", "SensorController"), cycle_ms: 10, signal_name: "FastFeedback", signal_display_name: "FastFeedback" }, { ...chain("Other", "SensorController"), cycle_ms: 5 }];
  const emptied = reviewedEquipmentCluster(source, { tree: [], unassigned: [] }, chains);
  assert.deepEqual(equipmentClusterBusIssues(emptied, "lin"), []);
  const target = reviewedEquipmentCluster(source, { tree: [{ name: "Controller", sensors: [leaf], actuators: [] }], unassigned: [] }, chains);
  const issues = equipmentClusterBusIssues(target, "lin");
  assert.deepEqual(issues[0].affected, [{ name: "Fast", detail: "FastFeedback: 10 ms · Schnittstelle LIN" }]);
  const unresolved = equipmentClusterBusIssues({ ...source, devices: [], unassigned: [leaf] }, "can-fd");
  assert.deepEqual(unresolved[0].affected, [{ name: "Fast", detail: "Owner fehlt" }]);
});

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

test("learned cross-project ownership overrides the heuristic and keeps the endpoint with its ECU", () => {
  const endpoint = chain("EngineSpeed", "SensorController", "CAN_FD");
  const clusters = buildEquipmentClusters([
    chain("Motorsteuerung", "ECU", "CAN_FD"),
    chain("Diagnose", "ECU", "CAN_FD"),
    endpoint,
  ], [{ id: "automotive-can_fd", label: "Automotive CAN-FD", count: 1 }], "automotive", [{
    endpoint_name: "EngineSpeed",
    controller_name: "Motorsteuerung",
    confidence: 0.96,
    reason: "Projektübergreifend bestätigte Controller-Zuordnung (RAG).",
    evidence_count: 2,
    source_projects: ["previous-project"],
    retrieval_sources: ["wizard-review-history", "system-cluster-graph"],
  }]);
  const owner = clusters.flatMap((cluster) => cluster.controllers).find((controller) => controller.name === "Motorsteuerung");

  assert.ok(owner);
  assert.equal(owner.sensors.some((sensor) => sensor.name === "EngineSpeed"), true);
  assert.match(owner.sensors.find((sensor) => sensor.name === "EngineSpeed").reason, /RAG/);
  assert.equal(clusters.reduce((count, cluster) => count + cluster.unassigned.length, 0), 0);
});

test("the raised endpoint budget closes every automotive controller branch", () => {
  const extracted = extractEngineeringSpecification(
    "Industrie: Automotive\n- 50 ECUs\n- 250 Sensoren\n- 250 Aktoren\n- 1 Gateway",
    { sensors: 250, actuators: 250, ecus: 50, gateways: 1 },
    "automotive",
    true,
  );
  const clusters = buildEquipmentClusters(extracted.chains, [
    { id: "automotive-can_fd", label: "Automotive CAN-FD", count: 15 },
    { id: "automotive-lin", label: "Automotive LIN", count: 50 },
    { id: "automotive-ethernet", label: "Automotive Ethernet", count: 10 },
  ], "automotive");
  const controllers = clusters.flatMap((cluster) => cluster.controllers);

  assert.equal(controllers.length, 50);
  assert.equal(controllers.every((controller) => controller.sensors.length > 0), true);
  assert.equal(controllers.every((controller) => controller.actuators.length > 0), true);
  assert.equal(clusters.reduce((count, cluster) => count + cluster.unassigned.length, 0), 0);
});

test("an extra named ECU cannot orphan the last catalog controller and its actuators", () => {
  const extracted = extractEngineeringSpecification(
    "Industrie: Automotive\n- Lichtsteuergerät",
    { sensors: 100, actuators: 100, ecus: 50, gateways: 1 },
    "automotive",
    true,
  );
  const clusters = buildEquipmentClusters(extracted.chains, [
    { id: "automotive-can_fd", label: "Automotive CAN-FD", count: 10 },
    { id: "automotive-lin", label: "Automotive LIN", count: 25 },
    { id: "automotive-ethernet", label: "Automotive Ethernet", count: 5 },
  ], "automotive");
  const headUpDisplay = clusters
    .flatMap((cluster) => cluster.controllers)
    .find((controller) => controller.name === "HeadUpDisplay");

  assert.ok(headUpDisplay);
  assert.deepEqual(
    headUpDisplay.actuators.map((actuator) => actuator.name).sort(),
    ["HeadUpDisplaySchaltausgang", "HeadUpDisplayStellglied"],
  );
  assert.equal(clusters.reduce((count, cluster) => count + cluster.unassigned.length, 0), 0);
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


test("all domains offer HMI outputs and hosted functions do not invent devices", () => {
  const devices = ["Fahrwerk", "BodyControl", "Klimatisierung", "Infotainment", "Telematik", "Konnektivitaet", "Kombiinstrument"].map(name => ({ ...chain(name, "ECU", "Ethernet"), domain: "automotive" }));
  devices.push({ ...chain("CabinSensor", "SensorController"), domain: "automotive" });
  const clusters = buildEquipmentClusters(devices, [{ id: "ethernet", label: "Ethernet" }], "automotive");
  assert.equal(clusters.reduce((sum, cluster) => sum + cluster.devices.length, 0), devices.length);
  const routes = clusters.flatMap(cluster => cluster.hmiRoutes);
  for (const source of ["Fahrwerk", "BodyControl", "Klimatisierung", "Infotainment", "Telematik", "Konnektivitaet"]) {
    assert.ok(routes.some(route => route.source === source && route.target === "Kombiinstrument"), source);
  }
  assert.ok(!routes.some(route => route.source === "CabinSensor"));
  assert.equal(new Set(routes.map(route => JSON.stringify([route.source, route.target]))).size, routes.length);
  const names = clusters.flatMap(cluster => cluster.controllers.flatMap(controller => (controller.functions ?? []).map(fn => fn.name)));
  for (const name of ["Innenraumueberwachung", "InnenraumTemperaturregelung", "RadioFM", "RadioDAB", "Navigation", "GNSSPositionierungGPS", "WLAN", "Bluetooth", "InternetMobilfunk", "Bedienelemente"]) assert.ok(names.includes(name), name);
  assert.ok(selectHmiSignals(routes).every(route => !route.signals.length));
});
