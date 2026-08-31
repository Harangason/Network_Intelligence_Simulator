import assert from "node:assert/strict";
import test from "node:test";

import { normalizeHardwareName, extractEngineeringSpecification, extractEngineeringTargetCounts, extractNetworkArchitectureMode, isEngineeringReviewRequest, isStructuredEngineeringSpecification } from "./engineering-specification.ts";

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
    functionName: "Temperatursensor_Erfassung",
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
  assert.equal(extractNetworkArchitectureMode("- Netzarchitektur-ID: eva"), "eva");
  assert.equal(extractNetworkArchitectureMode("- Netzarchitektur-ID: ecu_gateway"), "ecu_gateway");
  assert.equal(extractNetworkArchitectureMode("- Netzarchitektur-ID: gateway_direct"), "gateway_direct");
  assert.equal(extractNetworkArchitectureMode("- Netzarchitektur-ID: hybrid_ai"), "hybrid_ai");
  assert.equal(extractNetworkArchitectureMode("Kombination aus Variante 2 und 3"), "hybrid_ai");
});

test("wizard variant numbers never become hardware quantities", () => {
  for (const [id, label] of [
    ["eva", "Variante 1 · Einfaches EVA"],
    ["ecu_gateway", "Variante 2 · ECU-vermittelt"],
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
