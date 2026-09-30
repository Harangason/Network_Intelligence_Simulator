import test from 'node:test';
import assert from 'node:assert/strict';
import { actuatorCommandLabel, actuatorCommands, proposedActuatorCommand, resolvedActuatorCommands, selectActuatorCommand, unresolvedActuatorCommands, ACTUATOR_COMMANDS } from './actuator-commands.ts';

test('default commands are serialized for new drafts while explicit and imported contracts survive', () => {
  const nodes = ['TelematikSchaltausgang', 'TelematikStellglied'].map(hardware_name => ({ hardware_name, device_type: 'ActuatorController' }));
  assert.deepEqual(resolvedActuatorCommands(nodes, ''), { TelematikSchaltausgang: ACTUATOR_COMMANDS.OPEN_CLOSE, TelematikStellglied: ACTUATOR_COMMANDS.POSITION });
  const custom = { length_bits: 8, data: { enum_values: { OPEN: 23 } } };
  const source = '- Aktor-Befehle: ' + JSON.stringify({ TelematikSchaltausgang: custom });
  assert.deepEqual(resolvedActuatorCommands(nodes, source).TelematikSchaltausgang, custom);
  assert.deepEqual(resolvedActuatorCommands(nodes, 'per Wizard-Uebernehmen bestaetigt'), {});
});

test('named generic actuator roles use the requested command proposals', () => {
  assert.equal(proposedActuatorCommand('TelematikSchaltausgang').choice, 'OPEN_CLOSE');
  assert.equal(proposedActuatorCommand('TelematikStellglied').choice, 'POSITION');
  assert.equal(proposedActuatorCommand('TelematikStellgliedActuator').choice, 'POSITION');
  assert.equal(proposedActuatorCommand('Unbekannt'), null);
  assert.equal(proposedActuatorCommand('Ventilaktor1', 'ein Aktor zum proportional schließen eines Ventil').choice, 'POSITION');
  assert.equal(proposedActuatorCommand('Ventilaktor1', 'ein Aktor zum Schließen eines Ventil').choice, 'OPEN_CLOSE');
});

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
