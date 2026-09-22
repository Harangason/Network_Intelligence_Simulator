import { test } from 'node:test';
import assert from 'node:assert/strict';
import { selectSensorMeasurement, sensorMeasurement, sensorMeasurementSelections } from './sensor-measurements.ts';
import { extractEngineeringSpecification } from './engineering-specification.ts';

test('PT100 is recognized as a temperature sensor', () => {
  assert.equal(sensorMeasurement('PT100')?.id, 'temperature');
});

test('flow and IO-Link survive the S02 sensor wording', () => {
  assert.equal(sensorMeasurement('Durchfluss 0–100 l/min')?.id, 'flow');
  const result = extractEngineeringSpecification(`1 PLC
2 IO-Link-Sensoren:
- Durchfluss 0–100 l/min, 20 ms
- Druck 0–16 bar, 20 ms`);
  const sensors = result.chains.filter(c => c.device_type === 'SensorController');
  assert.equal(sensors.length, 2);
  assert.ok(sensors.every(sensor => sensor.interface_type === 'IO_LINK'));
  assert.equal(sensors.find(sensor => /Durchfluss/.test(sensor.hardware_name))?.unit, 'l/min');
});

test('measurement choice resolves a generic sensor slot and preserves independent connections', () => {
  const original = '3 Sensoren und ein RaspberryPi\n- Geräteanschlüsse: {"Sensor2":"I2C","RaspberryPi":"I2C"}';
  let text = selectSensorMeasurement(original, 'Sensor2', 'torque');
  text = selectSensorMeasurement(text, 'Sensor1', 'temperature');
  const result = extractEngineeringSpecification(text, {}, 'embedded_systems');
  const sensors = result.chains.filter(c => c.device_type === 'SensorController');
  assert.equal(sensors.length, 2);
  assert.equal(result.targetCounts.sensors, 3);
  const torque = sensors.find(c => c.hardware_name === 'Sensor2');
  assert.equal(torque.unit, 'Nm');
  assert.equal(torque.interface_type, 'I2C');
  assert.equal(torque.configuration.sensor_measurement, 'torque');
  assert.match(torque.signal_name, /^Drehmoment/);
  assert.equal(sensors.find(c => c.hardware_name === 'Sensor1').interface_type, 'Other');
});

test('changing an existing sensor measurement keeps identity and connection but changes semantics', () => {
  const text = '3 Temperatursensoren und ein RaspberryPi\n- Geräteanschlüsse: {"Temperatursensor1":"I2C"}';
  const changed = extractEngineeringSpecification(selectSensorMeasurement(text, 'Temperatursensor1', 'torque'));
  const sensor = changed.chains.find(c => c.hardware_name === 'Temperatursensor1');
  assert.equal(sensor.unit, 'Nm');
  assert.equal(sensor.interface_type, 'I2C');
  assert.match(sensor.function_name, /DrehmomentErfassung$/);
  assert.equal(sensor.min_value, -10000);
  assert.equal(sensor.max_value, 10000);
  assert.equal(changed.chains.filter(c => c.device_type === 'SensorController').length, 3);
  assert.equal(changed.chains.find(c => c.hardware_name === 'Temperatursensor2').unit, 'degC');
});

test('malformed and unsupported measurement choices never create devices', () => {
  for (const json of ['null', '[]', '{"Sensor1":"unknown"}', '{broken}']) {
    assert.deepEqual(sensorMeasurementSelections(`- Sensor-Messgrößen: ${json}`), {});
  }
  assert.equal(selectSensorMeasurement('3 Sensoren', 'Sensor1', 'unknown'), '3 Sensoren');
});
