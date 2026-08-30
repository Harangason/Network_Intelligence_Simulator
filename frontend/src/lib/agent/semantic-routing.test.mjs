import assert from "node:assert/strict";
import test from "node:test";

import { extractEngineeringSpecification } from "./engineering-specification.ts";
import { semanticProcessorForSensor, semanticRoutePlans } from "./semantic-routing.ts";

const SAMPLE = `
# Musterprojekt Fahrzeugnetzwerk
- 100 Sensoren
- 50 Funktions-ECUs
- 1 zentrales Gateway
- LIN
- CAN-FD
- Automotive Ethernet
`;

function architecture() {
  const chains = extractEngineeringSpecification(SAMPLE).chains;
  return {
    sensors: chains.filter((chain) => chain.device_type === "SensorController"),
    processors: chains.filter((chain) => chain.device_type === "ECU"),
  };
}

function targetFor(sensorName) {
  const { sensors, processors } = architecture();
  const sensor = sensors.find((candidate) => candidate.hardware_name === sensorName);
  assert.ok(sensor, `Sensor ${sensorName} fehlt im Muster`);
  return semanticProcessorForSensor(sensor, processors)?.hardware_name;
}

test("Bremsdruck wird fachlich der Bremsregelung und nicht der Klima-ECU zugeordnet", () => {
  assert.equal(targetFor("RearLeftBrakePressureSensor"), "Bremsregelung-ECU");
});

test("repräsentative Sensorfamilien werden ihren fachlichen ECUs zugeordnet", () => {
  assert.equal(targetFor("CabinTemperatureSensor"), "Klimatisierung-ECU");
  assert.equal(targetFor("FrontLeftTirePressureSensor"), "Reifendruckkontrolle-ECU");
  assert.equal(targetFor("RearRightSuspensionTravelSensor"), "Fahrwerk-ECU");
  assert.equal(targetFor("SteeringAngleSensor"), "Lenkung-ECU");
  assert.equal(targetFor("FrontRadarDistanceSensor"), "Radarverarbeitung-ECU");
});

test("kein semantischer Treffer erzeugt keinen willkürlichen Erst-ECU-Fallback", () => {
  const { sensors, processors } = architecture();
  const unknown = {
    ...sensors[0],
    hardware_name: "UnknownQuantumSensor",
    hardware_description: "Unbekannte Messgröße ohne fachliche Zielangabe.",
    function_name: "UnknownQuantum_Erfassung",
    function_description: "Unbekannte Messgröße.",
    signal_name: "UnknownQuantum",
    signal_display_name: "UnknownQuantum",
  };
  assert.equal(semanticProcessorForSensor(unknown, processors), undefined);
});

test("die vollständige Referenzarchitektur bleibt über 25 Durchläufe deterministisch zugeordnet", () => {
  const { sensors, processors } = architecture();
  const expected = sensors.map((sensor) => semanticProcessorForSensor(sensor, processors)?.hardware_name);
  assert.equal(expected.filter(Boolean).length, 100);
  for (let pass = 1; pass <= 25; pass += 1) {
    assert.deepEqual(
      sensors.map((sensor) => semanticProcessorForSensor(sensor, processors)?.hardware_name),
      expected,
      `Durchlauf ${pass}`,
    );
  }
});

test("die Referenzarchitektur erzeugt genau 100 Sensor- und 50 Gateway-Pfade", () => {
  const specification = extractEngineeringSpecification(SAMPLE);
  const plans = semanticRoutePlans(specification.chains);
  const sensorPlans = plans.filter((plan) => plan.source.device_type === "SensorController");
  const ecuPlans = plans.filter((plan) => plan.source.device_type === "ECU");

  assert.equal(sensorPlans.length, 100);
  assert.equal(ecuPlans.length, 50);
  assert.equal(plans.some((plan) => plan.source.device_type === "Gateway"), false);
  assert.equal(ecuPlans.every((plan) => plan.destinations[0]?.device_type === "Gateway"), true);
});
