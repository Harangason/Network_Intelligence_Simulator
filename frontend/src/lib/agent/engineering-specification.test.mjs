import assert from "node:assert/strict";
import test from "node:test";

import { normalizeHardwareName, expandEngineeringSignalModel, extractCommunicationSystemCounts, extractEngineeringSpecification, extractEngineeringTargetCounts, extractNetworkArchitectureMode, isEngineeringAnalysisWorkRequest, isEngineeringReviewRequest, isStructuredEngineeringSpecification, packEngineeringChains } from "./engineering-specification.ts";

test("a review with hardware evidence must never trigger model creation", () => {
  const review = `Bewerte diese Intelligence-Empfehlung als Engineering-Agent.
Empfehlung: 2 LIN-Segmente innerhalb der Systemcluster vorsehen.
Evidence: FondtuerRechts-ECU, MotorCurrentSensor, AirbagActuator, System-Gateway
Messbereich: 0 bis 100; Sollwert: 60%`;
  assert.equal(isEngineeringReviewRequest(review), true);
  assert.equal(isStructuredEngineeringSpecification(review), false);
  assert.equal(isStructuredEngineeringSpecification(`Konkrete Aufgabe des Nutzers:\n${review}`), false);
  assert.equal(isEngineeringReviewRequest("Erstelle ein Fahrzeugnetzwerk aus dem folgenden Muster."), false);
});

test("analysis wording stays actionable instead of read-only review", () => {
  const request = "Analysiere diesen Befund und arbeite an der Lösung.";
  assert.equal(isEngineeringReviewRequest(request), false);
  assert.equal(isEngineeringAnalysisWorkRequest(request), true);
});

const SAMPLE = `
# Musterprojekt - Fahrzeugnetzwerk

## 1. Systemumfang

- **100 Sensoren**
- **50 Funktions-ECUs**
- **1 zentrales Gateway**
- LIN
- CAN-FD
- Automotive Ethernet

## 3. Beispiel Temperatursensor

- Bereich: −20 °C bis +120 °C
- Auflösung: 0,1 °C
- Signal: Temperature
- Verwendung durch eine Thermal-/Klima-ECU

## 11. Zentrales Gateway

Es existiert genau ein zentrales Gateway.

## 12. Routing-Tabelle

- Gateway
- Destination Network
`;

function summarize(result) {
  const counts = result.chains.reduce(
    (current, chain) => {
      current[chain.device_type] = (current[chain.device_type] ?? 0) + 1;
      return current;
    },
    {},
  );
  const temperature = result.chains.find((chain) => chain.hardware_name === "Temperatur");
  return {
    targetCounts: result.targetCounts,
    counts,
    communicationSystems: result.communicationSystems,
    hardwareNames: result.chains.map((chain) => chain.hardware_name),
    temperature: temperature && {
      functionName: temperature.function_name,
      minValue: temperature.min_value,
      maxValue: temperature.max_value,
      dataType: temperature.data_type,
    },
  };
}

test("numbered headings and prose do not create extra hardware", () => {
  const summary = summarize(extractEngineeringSpecification(SAMPLE));
  assert.deepEqual(summary.targetCounts, { sensors: 100, actuators: 0, ecus: 50, gateways: 1, explicit: true });
  assert.deepEqual(summary.counts, { SensorController: 100, ECU: 50, Gateway: 1 });
  assert.deepEqual(summary.communicationSystems, ["LIN", "CAN_FD", "Ethernet"]);
  assert.equal(summary.hardwareNames.includes("Gateway"), false);
  assert.equal(summary.hardwareNames.includes("Verwendung durch eine Thermal-/Klima-ECU"), false);
  assert.equal(summary.hardwareNames.filter((name) => name === "System").length, 1);
  assert.deepEqual(summary.temperature, {
    functionName: "Temperatur_Erfassung",
    minValue: -20,
    maxValue: 120,
    dataType: "signed",
  });
});

test("specification extraction is stable over 25 project-creation passes", () => {
  const expected = summarize(extractEngineeringSpecification(SAMPLE));
  for (let pass = 1; pass <= 25; pass += 1) {
    assert.deepEqual(summarize(extractEngineeringSpecification(SAMPLE)), expected, `pass ${pass}`);
  }
});

test("wizard architecture ids are extracted without ambiguity", () => {
  assert.equal(extractNetworkArchitectureMode("- Netzarchitektur-ID: sensor_ecu_actuator"), "sensor_ecu_actuator");
  assert.equal(extractNetworkArchitectureMode("- Netzarchitektur-ID: eva"), "eva");
  assert.equal(extractNetworkArchitectureMode("- Netzarchitektur-ID: ecu_gateway"), "ecu_gateway");
  assert.equal(extractNetworkArchitectureMode("- Netzarchitektur-ID: gateway_ecu_segments"), "gateway_ecu_segments");
  assert.equal(extractNetworkArchitectureMode("- Netzarchitektur-ID: gateway_direct"), "gateway_direct");
  assert.equal(extractNetworkArchitectureMode("- Netzarchitektur-ID: hybrid_ai"), "hybrid_ai");
  assert.equal(extractNetworkArchitectureMode("Variante 0 Sensor ECU Aktor"), "sensor_ecu_actuator");
  assert.equal(extractNetworkArchitectureMode("am Gateway haengen ueber eine Leitung bis zu 6 ECU"), "gateway_ecu_segments");
  assert.equal(extractNetworkArchitectureMode("Kombination aus Variante 2 und 3"), "hybrid_ai");
});

test("wizard variant numbers never become hardware quantities", () => {
  for (const [id, label] of [
    ["sensor_ecu_actuator", "Variante 0 · Sensor-ECU-Aktor"],
    ["eva", "Variante 1 · Einfaches EVA"],
    ["ecu_gateway", "Variante 2 · ECU-vermittelt"],
    ["gateway_ecu_segments", "Variante 4 · Gateway-Segmente"],
    ["gateway_direct", "Variante 3 · Gateway-direkt"],
    ["hybrid_ai", "KI-Kombination · Variante 2 + 3"],
  ]) {
    const wrapped = `Strukturierte Vorgaben fuer den Engineering-Agenten:
- Netzarchitektur-ID: ${id}
- Netzarchitektur: ${label}
- Workflowumfang: Workflow 1 Engineering-Modell; Workflow 2 Routing-Tabelle; Workflow 9 Data Science

Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
${SAMPLE}

Verbindliche Kanonisierung bei der Projektanlage: ADAS und Fahrerassistenz sind Synonyme.

Starte jetzt die Analyse.`;
    const result = extractEngineeringSpecification(wrapped);
    assert.deepEqual(result.targetCounts, { sensors: 100, actuators: 0, ecus: 50, gateways: 1, explicit: true }, label);
    assert.deepEqual(summarize(result), summarize(extractEngineeringSpecification(SAMPLE)), label);
    assert.equal(result.networkArchitecture, id);
    assert.deepEqual(extractEngineeringTargetCounts(wrapped), result.targetCounts);
  }
});

test("quantity matches cannot cross line or variant-label boundaries", () => {
  const text = "Variante 3: Gateway-direkt\nVariante 2: ECU-vermittelt\n3\nGateway / BCM\n- 100 Sensoren\n- 50 Funktions-ECUs\n- 1 zentrales Gateway";
  assert.deepEqual(extractEngineeringTargetCounts(text), { sensors: 100, actuators: 0, ecus: 50, gateways: 1, explicit: true });
});

test("quantity matches support noun-first wizard and file wording", () => {
  const text = [
    "Geräteumfang:",
    "Gateways: 2",
    "ECUs = 47",
    "Sensoren - 95",
    "Aktoren Anzahl 88",
  ].join("\n");

  assert.deepEqual(extractEngineeringTargetCounts(text), { sensors: 95, actuators: 88, ecus: 47, gateways: 2, explicit: true });
});

test("communication system quantities are extracted from the specification text", () => {
  const text = [
    "Kommunikationssysteme:",
    "CAN FD: 20 Busse",
    "LIN 10",
    "Automotive Ethernet = 5",
    "SOME/IP: 1",
    "500 kbit/s CAN FD als Bitrate",
  ].join("\n");

  assert.deepEqual(extractCommunicationSystemCounts(text), { CAN_FD: 20, LIN: 10, Ethernet: 5, SOME_IP: 1 });
  assert.deepEqual(extractEngineeringSpecification(text).communicationSystemCounts, { CAN_FD: 20, LIN: 10, Ethernet: 5, SOME_IP: 1 });
  assert.equal(extractEngineeringSpecification("SOME/IP 1\n- 1 ECU").interfaceType, "Ethernet");
});

test("neu 9 system scope generates all 100 actuators alongside sensors, ECUs and one gateway", () => {
  const text = SAMPLE.replace("- **100 Sensoren**", "- **100 Sensoren**\n- **100 Aktuatoren**");
  const expected = summarize(extractEngineeringSpecification(text));
  for (let pass = 0; pass < 25; pass += 1) {
    const result = extractEngineeringSpecification(text);
    assert.deepEqual(summarize(result), expected);
    assert.deepEqual(summarize(result).counts, { SensorController: 100, ActuatorController: 100, ECU: 50, Gateway: 1 });
    assert.equal(new Set(result.chains.map((chain) => chain.hardware_name)).size, 251);
    assert.equal(result.chains.some((chain) => /100 Aktuatoren/.test(chain.hardware_name)), false);
    assert.equal(result.networkArchitecture, "gateway_direct");
  }
});

test("class 0 to 2 sensor and actuator templates start on LIN", () => {
  const result = extractEngineeringSpecification(SAMPLE, { sensors: 100, actuators: 100 });
  const basicSensors = result.chains.filter((chain) =>
    chain.device_type === "SensorController"
      && !/camera|kamera|vision|radar|lidar|scanner|ultrasonic/i.test(chain.hardware_name),
  );
  const actuators = result.chains.filter((chain) => chain.device_type === "ActuatorController");

  assert.ok(basicSensors.length > 0);
  assert.ok(actuators.length > 0);
  assert.ok(basicSensors.every((chain) => chain.interface_type === "LIN"));
  assert.ok(actuators.every((chain) => chain.interface_type === "LIN"));
});

test("gateway-direct generation does not add a central computer beside the system gateway", () => {
  const result = extractEngineeringSpecification(SAMPLE, { actuators: 100 });
  const centralComputerNames = result.chains
    .map((chain) => chain.hardware_name)
    .filter((name) => /zentralrechner/i.test(name));

  assert.deepEqual(centralComputerNames, []);
  assert.equal(result.chains.filter((chain) => chain.device_type === "Gateway").length, 1);
});

test("German and English actuator quantities and named actuators are recognized", () => {
  for (const noun of ["Aktoren", "Aktuatoren", "Actuators"]) {
    assert.equal(extractEngineeringTargetCounts(`- 100 ${noun}`).actuators, 100);
  }
  const result = extractEngineeringSpecification("- Bremsaktuator\n- Fensteraktor\n- DoorActuator");
  assert.equal(result.chains.filter((chain) => chain.device_type === "ActuatorController").length, 3);
});

test("confirmed count corrections take precedence over the original sample, including zero", () => {
  const counts = { sensors: 2, actuators: 3, ecus: 1, gateways: 0 };
  const text = `Strukturierte Vorgaben fuer den Engineering-Agenten:\n- Hardware-Sollwerte: ${JSON.stringify(counts)}\n\nKonkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:\n${SAMPLE}`;
  const result = extractEngineeringSpecification(text);
  assert.deepEqual(result.targetCounts, { ...counts, explicit: true });
  assert.deepEqual(summarize(result).counts, { SensorController: 2, ActuatorController: 3, ECU: 1 });
});

test("corrected quantities can exceed the initial template catalog", () => {
  const result = extractEngineeringSpecification(SAMPLE, { sensors: 110, actuators: 105, ecus: 55, gateways: 2 });
  assert.deepEqual(summarize(result).counts, { SensorController: 110, ActuatorController: 105, ECU: 55, Gateway: 2 });
  assert.equal(new Set(result.chains.map((chain) => chain.hardware_name)).size, 272);
});

test("generated system variants follow the selected industry without ECU suffixes", () => {
  const examples = [
    ["Automotive", "automotive", "Kuehlkreislaufsteuerung"],
    ["Industrial Automation", "industrial_automation", "SPSLeitsystem"],
    ["Embedded Systems", "embedded_systems", "MainControl"],
    ["Aerospace / Defense", "aerospace", "FlightManagement"],
    ["Rail", "rail", "TrainControl"],
    ["Marine", "marine", "PropulsionControl"],
    ["Building Automation", "building_automation", "Gebaeudeleittechnik"],
    ["Energy", "energy", "Umrichtersteuerung"],
    ["Robotics / ROS", "robotics_ros", "MotionPlanner"],
    ["Generic Networking", "generic_networking", "CoreSwitch"],
  ];

  for (const [label, domain, expectedName] of examples) {
    const result = extractEngineeringSpecification(`Industrie: ${label}\n- 3 ECUs\n- 1 Gateway`);
    const ecuNames = result.chains.filter((chain) => chain.device_type === "ECU").map((chain) => chain.hardware_name);

    assert.equal(result.domain, domain, label);
    assert.equal(ecuNames[0], expectedName, label);
    assert.equal(ecuNames.some((name) => /-ECU$/i.test(name)), false, label);
  }
});

test("automotive prose headings do not create generic or synonymous duplicate ECUs", () => {
  const result = extractEngineeringSpecification(`Industrie: Automotive
- 50 Funktions-ECUs
- 1 zentrales Gateway

## 1. Anforderungen
- je Funktion-ECU min 5 und max 20 Signale anlegen

## 9. Beispiel Motion-/Antriebs-ECU
- Motorsteuergeraet
- Getriebesteuergeraet
- Lenkungssteuergeraet
- Fahrwerksteuergeraet
- Klimasteuergeraet
`);
  const ecuNames = result.chains
    .filter((chain) => chain.device_type === "ECU")
    .map((chain) => chain.hardware_name);

  assert.equal(ecuNames.length, 50);
  assert.equal(new Set(ecuNames.map((name) => name.toLowerCase())).size, 50);
  assert.equal(ecuNames.filter((name) => name === "Motorsteuerung").length, 1);
  assert.equal(ecuNames.filter((name) => name === "Getriebesteuerung").length, 1);
  assert.equal(ecuNames.filter((name) => name === "Lenkung").length, 1);
  assert.equal(ecuNames.filter((name) => name === "Fahrwerk").length, 1);
  assert.equal(ecuNames.filter((name) => name === "Klimatisierung").length, 1);
  for (const invalid of ["Funktion", "Motion", "Antriebs", "Motor", "Getriebe", "Lenkungs", "Klima", "Thermal", "Fahrdynamik"]) {
    assert.equal(ecuNames.includes(invalid), false, invalid);
  }
});

test("generated sensor names stay industry specific while basic devices start on LIN", () => {
  const industrial = extractEngineeringSpecification("Industrie: Industrial Automation\n- 2 Sensoren\n- 1 ECU");
  const embedded = extractEngineeringSpecification("Industrie: Embedded Systems\n- 2 Sensoren\n- 1 ECU");

  assert.deepEqual(
    industrial.chains.filter((chain) => chain.device_type === "SensorController").map((chain) => chain.hardware_name),
    ["MotorCurrent", "AxisPosition"],
  );
  assert.deepEqual(
    embedded.chains.filter((chain) => chain.device_type === "SensorController").map((chain) => chain.interface_type),
    ["LIN", "LIN"],
  );
  assert.equal(industrial.chains.some((chain) => /^FrontLeftWheel/.test(chain.hardware_name)), false);
});

test("hardware roles are properties, not name suffixes; instance numbers stay stable", () => {
  for (const [raw, clean] of [["Airbag-ECU", "Airbag"], ["Airbagsteuergerät", "Airbag"], ["Airbag-Steuergeraet-2", "Airbag-2"], ["AcceleratorPositionSensor", "AcceleratorPosition"], ["BrakeActuator", "Brake"], ["BremsAktuator", "Brems"], ["Airbag-ECU-2", "Airbag-2"], ["Sensor", "Sensor"]]) {
    assert.equal(normalizeHardwareName(raw), clean);
  }
  const result = extractEngineeringSpecification(SAMPLE, { actuators: 100 });
  assert.equal(result.chains.some((chain) => /(?:-ECU|Sensor|Actuator|Aktuator)$/.test(chain.hardware_name)), false);
  assert.equal(new Set(result.chains.map((chain) => chain.hardware_name)).size, result.chains.length);
  assert.equal(result.chains.filter((chain) => chain.device_type === "ActuatorController").length, 100);
  assert.equal(result.chains.filter((chain) => chain.device_type === "ECU").length, 50);
  assert.equal(new Set(result.chains.filter((chain) => chain.device_type === "ECU").map((chain) => chain.hardware_name)).size, 50);
});

test("derived user-facing names use the normalized hardware name", () => {
  const result = extractEngineeringSpecification(`
    Airbagsteuergerät
    - Kommunikationsprotokoll: LIN
    - Wertebereich: 0..1
  `);
  const chain = result.chains.find((item) => item.hardware_name === "Airbag");

  assert.ok(chain);
  assert.equal(chain.device_type, "ECU");
  assert.equal(chain.function_name, "Airbag_Steuerung");
  assert.equal(chain.interface_name, "Airbag_1");
  assert.equal(chain.message_name, "AirbagSteuerungData");
  assert.equal(chain.signal_name, "AirbagStatus");
  assert.equal(chain.signal_display_name, "AirbagStatus");
  assert.equal([chain.hardware_name, chain.function_name, chain.interface_name, chain.message_name, chain.signal_name].some((value) => /steuerger(?:ä|ae|a|�)t/i.test(value)), false);
});

test("new-project generator sizes signal bits and message DLC from physical range", () => {
  const result = extractEngineeringSpecification(SAMPLE, { actuators: 2 });
  const temperature = result.chains.find((chain) => chain.hardware_name === "Temperatur");
  const gateway = result.chains.find((chain) => chain.device_type === "Gateway");
  const binaryActuator = result.chains.find((chain) => chain.signal_name.endsWith("SchaltausgangStatus"));

  assert.equal(temperature?.length_bits, 12);
  assert.equal(temperature?.dlc, 2);
  assert.equal(gateway?.length_bits, 8);
  assert.equal(gateway?.dlc, 1);
  assert.equal(binaryActuator?.length_bits, 1);
  assert.equal(binaryActuator?.dlc, 1);
});

test("recognized physical sensors receive complete conservative defaults when the prompt omits them", () => {
  const result = extractEngineeringSpecification("TemperaturSensor\nDruckSensor\n- Kommunikationsprotokoll: LIN");
  const temperature = result.chains.find((chain) => chain.signal_name === "Temperatur");
  const pressure = result.chains.find((chain) => chain.signal_name === "Druck");

  assert.ok(temperature);
  assert.equal(temperature.min_value, -40);
  assert.equal(temperature.max_value, 215);
  assert.equal(temperature.factor, 0.1);
  assert.equal(temperature.unit, "degC");
  assert.equal(temperature.quality.value_domain_complete, true);
  assert.ok(pressure);
  assert.equal(pressure.min_value, 0);
  assert.equal(pressure.max_value, 250);
  assert.equal(pressure.unit, "bar");
  assert.equal(pressure.semantic.semantic_type, "NUMERIC");
});

test("direct prose creation request extracts front camera engineering chain", () => {
  const result = extractEngineeringSpecification(
    "lege ein Hardware konten an. Frontkamera mit der Funktion umfelderfassung mit Schnittstellen die notwendigen Signale sollen Objekte wie Bälle erkennen lönnen",
  );

  assert.equal(result.chains.length, 1);
  assert.equal(result.chains[0].hardware_name, "Frontkamera");
  assert.equal(result.chains[0].device_type, "SensorController");
  assert.equal(result.chains[0].domain, "automotive");
  assert.equal(result.chains[0].function_name, "Frontkamera_Umfelderfassung");
  assert.equal(result.chains[0].interface_type, "Ethernet");
  assert.equal(result.chains[0].interface_name, "Frontkamera_1");
  assert.equal(result.chains[0].message_name, "FrontkameraUmfelderfassungData");
  assert.equal(result.chains[0].signal_name, "ObjektErkannt");
  assert.equal(result.chains[0].length_bits, 1);
  assert.equal(result.chains[0].dlc, 1);
  assert.equal(result.chains[0].semantic?.semantic_type, "BOOLEAN");
});

test("packing reuses one interface and one message for compatible producer signals", () => {
  const base = extractEngineeringSpecification("Motorsteuergerät mit Signal Motordrehzahl");
  const template = base.chains[0];
  const packed = packEngineeringChains([
    { ...template, signal_name: "MotorRpm", signal_display_name: "MotorRpm", length_bits: 16 },
    { ...template, signal_name: "MotorTorque", signal_display_name: "MotorTorque", length_bits: 16 },
    { ...template, signal_name: "MotorCurrent", signal_display_name: "MotorCurrent", length_bits: 16 },
  ]);

  assert.equal(new Set(packed.map((chain) => chain.interface_name)).size, 1);
  assert.equal(new Set(packed.map((chain) => chain.message_name)).size, 1);
  assert.deepEqual(packed.map((chain) => chain.start_bit).sort((a, b) => a - b), [0, 16, 32]);
  assert.equal(packed[0].dlc, 6);
  assert.equal(packed[0].configuration?.payload_used_bits, 48);
  assert.equal(packed[0].configuration?.payload_capacity_bits, 48);
});

test("intelligent devices receive a complete five-signal minimum model before packing", () => {
  const base = extractEngineeringSpecification("Motorsteuergerät mit CAN-FD und Signal Motordrehzahl").chains[0];
  const expanded = expandEngineeringSignalModel([base]);
  const packed = packEngineeringChains(expanded);

  assert.equal(expanded.length, 5);
  assert.equal(new Set(expanded.map((chain) => chain.signal_name)).size, 5);
  assert.equal(new Set(packed.map((chain) => chain.message_name)).size, 1);
  assert.deepEqual(packed.map((chain) => chain.start_bit).sort((a, b) => a - b), [0, 4, 7, 11, 19]);
});

test("CAN-FD packing uses valid payload classes and splits atomically beyond one frame", () => {
  const base = extractEngineeringSpecification("Fahrwerksteuergerät mit CAN-FD und Signal Federweg");
  const template = { ...base.chains[0], interface_type: "CAN_FD", cycle_ms: 10 };
  const packed = packEngineeringChains([
    { ...template, signal_name: "BlobA", signal_display_name: "BlobA", length_bits: 392 },
    { ...template, signal_name: "BlobB", signal_display_name: "BlobB", length_bits: 120 },
    { ...template, signal_name: "BlobC", signal_display_name: "BlobC", length_bits: 8 },
  ]);
  const messageNames = new Set(packed.map((chain) => chain.message_name));

  assert.equal(messageNames.size, 2);
  assert.ok(packed.every((chain) => [1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64].includes(chain.dlc)));
  assert.equal(packed.find((chain) => chain.signal_name === "BlobA")?.dlc, 64);
  assert.equal(packed.find((chain) => chain.signal_name === "BlobB")?.start_bit, 392);
  assert.equal(packed.find((chain) => chain.signal_name === "BlobC")?.start_bit, 0);
});

test("direct lowercase camera creation request is still actionable", () => {
  const result = extractEngineeringSpecification("frontkamera anlegen mit funktion umfelderfassung und signal objekt erkannt");

  assert.equal(result.chains.length, 1);
  assert.equal(result.chains[0].hardware_name, "frontkamera");
  assert.equal(result.chains[0].function_name, "Frontkamera_Umfelderfassung");
});
