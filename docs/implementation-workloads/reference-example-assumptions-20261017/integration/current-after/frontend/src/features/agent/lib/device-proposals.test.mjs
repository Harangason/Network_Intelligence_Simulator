import assert from 'node:assert/strict';
import test from 'node:test';
import { proposedDeviceConnection } from './device-connections.ts';
import { proposedActuatorCommand } from './actuator-commands.ts';

test('multi-bus machine proposals use only selected networks and keep unknown roles open', () => {
  const selected = ['ProfiNET', 'EtherCAT', 'Ethernet'];
  assert.equal(proposedDeviceConnection('Position1', selected)?.technology, 'EtherCAT');
  assert.equal(proposedDeviceConnection('Motor Drives1', selected)?.technology, 'EtherCAT');
  assert.equal(proposedDeviceConnection('Ventilaktor1', selected)?.technology, 'ProfiNET');
  assert.equal(proposedDeviceConnection('Gateway', selected)?.technology, 'Ethernet');
  assert.equal(proposedDeviceConnection('Unbekannt1', selected), null);
  assert.equal(proposedDeviceConnection('Motor Drives1', ['ProfiNET', 'Ethernet']), null);
});

test('actuator proposals distinguish switching from position control', () => {
  assert.equal(proposedActuatorCommand('Ventilaktor1')?.choice, 'OPEN_CLOSE');
  assert.equal(proposedActuatorCommand('Linearantriebe1', 'Stellposition 0–100 %')?.choice, 'POSITION');
  assert.equal(proposedActuatorCommand('Unknown1'), null);
});

test('drive names do not substitute a position preset for unspecified or different command quantities', () => {
  for (const name of ['Antriebs ', 'Antriebsmotor', 'Motor', 'Servo', 'Linearantriebe1', 'MotionActuator', 'Luefter', 'Fan', 'Steering'])
    assert.equal(proposedActuatorCommand(name), null, name);
  for (const purpose of ['Drehmomentanforderung', 'Requested torque in Nm', 'Drehzahlsollwert', 'Rotational speed in rpm'])
    assert.equal(proposedActuatorCommand('Positionsantrieb', purpose), null, purpose);
  assert.equal(proposedActuatorCommand('Servomotor', 'Position in Grad von -90 bis 90'), null);
});

test('relative position evidence and explicit generic presets remain reviewable candidates', () => {
  assert.equal(proposedActuatorCommand('Servo', 'Stellposition 0–100 %')?.choice, 'POSITION');
  assert.equal(proposedActuatorCommand('Servo', 'Relative position in percent')?.choice, 'POSITION');
  assert.equal(proposedActuatorCommand('Antrieb', 'Position 0..100 %')?.choice, 'POSITION');
  assert.equal(proposedActuatorCommand('SystemStellglied')?.choice, 'POSITION');
  assert.equal(proposedActuatorCommand('SystemSchaltausgang')?.choice, 'OPEN_CLOSE');
});
