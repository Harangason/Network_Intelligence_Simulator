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
  assert.equal(proposedActuatorCommand('Linearantriebe1')?.choice, 'POSITION');
  assert.equal(proposedActuatorCommand('Unknown1'), null);
});
