import assert from "node:assert/strict";
import test from "node:test";

import { extractEngineeringSpecification } from "./engineering-specification.ts";

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
  const temperature = result.chains.find((chain) => chain.hardware_name === "Temperatursensor");
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
  assert.deepEqual(summary.targetCounts, { sensors: 100, ecus: 50, gateways: 1, explicit: true });
  assert.deepEqual(summary.counts, { SensorController: 100, ECU: 50, Gateway: 1 });
  assert.deepEqual(summary.communicationSystems, ["LIN", "CAN_FD", "Ethernet"]);
  assert.equal(summary.hardwareNames.includes("Gateway"), false);
  assert.equal(summary.hardwareNames.includes("Verwendung durch eine Thermal-/Klima-ECU"), false);
  assert.equal(summary.hardwareNames.filter((name) => name === "System-Gateway").length, 1);
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
