import assert from 'node:assert/strict';
import test from 'node:test';
import { parseProjectIntake, projectIntakeKey } from './project-intake.ts';
import { extractEngineeringSpecification } from './engineering-specification.ts';

test('intake retains the original editable requirement within its project', () => {
  const requirement = 'drei Sensoren, respary pi und Ventile';
  const raw = JSON.stringify({projectId: 'a', requirement});
  assert.equal(parseProjectIntake(raw, 'a'), requirement);
  assert.equal(parseProjectIntake(raw, 'b'), null);
  assert.notEqual(projectIntakeKey('a'), projectIntakeKey('b'));
});

test('confirmed embedded valve count does not select unrelated industry templates', () => {
  const request = 'ich möchte ein kleines Projekt: ich habe drei sensoren die temperatur messen und ein respary pi und aktoren die ventile steuern';
  const spec = extractEngineeringSpecification(request, {ecus:1, sensors:3, actuators:5, gateways:0}, 'embedded_systems', true);
  assert.equal(spec.domain, 'embedded_systems');
  assert.equal(spec.modelType, 'embedded_systems');
  assert.deepEqual(spec.chains.map(item => item.hardware_name), ['RaspberryPi', 'Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3', 'Ventilaktor1', 'Ventilaktor2', 'Ventilaktor3', 'Ventilaktor4', 'Ventilaktor5']);
  assert.ok(spec.chains.every(item => item.interface_type === 'Other'));
});

test('explicit industry and embedded connections cannot fall back to CAN', () => {
  for (const technology of ['ADC', 'DAC', 'GPIO', 'PWM', 'I2C']) {
    const spec = extractEngineeringSpecification(`Raspberry Pi mit ${technology}.`, {}, 'embedded_systems');
    assert.equal(spec.interfaceType, technology);
    assert.ok(spec.communicationSystems.includes(technology));
  }
  const spec = extractEngineeringSpecification('- Projekt-Modelltyp: automotive\nRaspberry Pi', {}, 'embedded_systems');
  assert.equal(spec.modelType, 'embedded_systems');
  assert.equal(spec.domain, 'embedded_systems');
});
test('invalid and excessive drafts cannot be handed to the wizard', () => {
  for (const raw of [null, 'oops', '{}', JSON.stringify({projectId: 'a', requirement: ' '}),
    JSON.stringify({projectId: 'a', requirement: 'x'.repeat(16001)})]) {
    assert.equal(parseProjectIntake(raw, 'a'), null);
  }
});

test('three temperature sensors and a Pi retain their identities without invented buses or controllers', () => {
  const request = 'ich möchte ein kleines Projekt: ich habe drei sensoren die temperatur messen und ein respary pi und aktoren die ventile steuern';
  const draft = extractEngineeringSpecification(request, {}, 'custom');
  assert.deepEqual(draft.chains.map(item => item.hardware_name), ['RaspberryPi', 'Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3']);
  assert.equal(draft.targetCounts.ecus, 1);
  assert.equal(draft.targetCounts.actuators, 0); // Unknown, not an invented one-to-one assignment.
  assert.ok(draft.chains.every(item => item.interface_type === 'Other'));
  assert.deepEqual(draft.chains.filter(item => item.device_type === 'SensorController').map(item => item.signal_name), ['Temperatur1', 'Temperatur2', 'Temperatur3']);
  const clarified = extractEngineeringSpecification(request + '\nZwei Ventile.', {}, 'custom');
  assert.deepEqual(clarified.chains.filter(item => item.device_type === 'ActuatorController').map(item => item.hardware_name), ['Ventilaktor1', 'Ventilaktor2']);
});
