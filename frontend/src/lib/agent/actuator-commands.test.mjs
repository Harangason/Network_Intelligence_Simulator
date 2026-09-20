import test from 'node:test';
import assert from 'node:assert/strict';
import { actuatorCommandLabel, actuatorCommands, selectActuatorCommand, unresolvedActuatorCommands, ACTUATOR_COMMANDS } from './actuator-commands.ts';

const valves = ['Ventilaktor1', 'Ventilaktor2'].map(hardware_name => ({ hardware_name, device_type: 'ActuatorController' }));
test('each valve needs its own explicit command and selection preserves the other device', () => {
  const source = '4 Sensoren Druck + Temperatur, 2 Aktoren als Ventile, ein Raspberry Pi';
  assert.deepEqual(unresolvedActuatorCommands(valves, source), ['Ventilaktor1', 'Ventilaktor2']);
  const first = selectActuatorCommand(source, 'Ventilaktor1', 'OPEN_CLOSE');
  assert.deepEqual(unresolvedActuatorCommands(valves, first), ['Ventilaktor2']);
  const complete = selectActuatorCommand(first, 'Ventilaktor2', 'POSITION');
  assert.deepEqual(unresolvedActuatorCommands(valves, complete), []);
  assert.deepEqual(actuatorCommands(complete), { Ventilaktor1: ACTUATOR_COMMANDS.OPEN_CLOSE, Ventilaktor2: ACTUATOR_COMMANDS.POSITION });
});
test('draft command selection is available for every actuator role', () => {
  assert.equal(actuatorCommandLabel('ACTUATOR', 'PWMVentil', 'Ventil'), 'Ventilbefehl');
  assert.equal(actuatorCommandLabel('ACTUATOR', 'DCMotorcontroller', 'Stellposition'), 'Aktorbefehl');
  assert.equal(actuatorCommandLabel('ACTUATOR', 'Relaisausgang', 'Auf / Zu'), 'Aktorbefehl');
  assert.equal(actuatorCommandLabel('SENSOR', 'Drucksensor', 'Druck'), '');
});
test('custom encodings from notes survive a selection for another actuator', () => {
  const custom = { length_bits: 8, data: { enum_values: { CLOSED: 12, OPEN: 99 } } };
  const source = `- Weitere Hinweise: - Aktor-Befehle: ${JSON.stringify({ Ventilaktor1: custom })}`;
  const next = selectActuatorCommand('Auftrag', 'Ventilaktor2', 'OPEN_CLOSE', source);
  assert.deepEqual(actuatorCommands(next).Ventilaktor1, custom);
  assert.deepEqual(unresolvedActuatorCommands(valves, next), []);
});
test('only known explicit simulator templates satisfy the command requirement', () => {
  assert.deepEqual(unresolvedActuatorCommands([{ ...valves[0], configuration: { actuator_command_template: { source: 'unrecognized' } } }], ''), ['Ventilaktor1']);
  assert.deepEqual(unresolvedActuatorCommands([{ ...valves[0], configuration: { actuator_command_template: { source: 'wizard-generic-actuator-v1' } } }], ''), []);
});
