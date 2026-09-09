import test from 'node:test';
import assert from 'node:assert/strict';
import { conciseGeneratedName, messageBusNames, technologyLabel } from './engineering-names.ts';

test('generated suffixes disappear without dropping real message purpose', () => {
  assert.equal(conciseGeneratedName('Function', 'Allradsteuerung_Steuerung'), 'Allradsteuerung');
  assert.equal(conciseGeneratedName('Interface', 'RearLeftBrakeTemperature_1'), 'RearLeftBrakeTemperature');
  assert.equal(conciseGeneratedName('Message', 'FrontRightBrakeTemperatureSensorErfassungData'), 'Front Right Brake Temperature');
  assert.equal(conciseGeneratedName('Message', 'FrontkameraUmfelderfassungData'), 'Frontkamera Umfelderfassung');
  assert.equal(technologyLabel('CAN_FD'), 'CAN-FD');
});

test('message bus comes from physical bindings, including additional transmitters', () => {
  const objects = new Map([['port1', { network_ref: 'net1', name: 'MisleadingDevice_1' }], ['port2', { network_ref: 'net2' }]]);
  const message = { hardware_interface_id: 'port1', interface_id: 'logical', configuration: { physical_transmit_bindings: [{ hardware_interface_id: 'port2' }] } };
  assert.equal(messageBusNames(message, objects, { net1: 'Antrieb_01', net2: 'Antrieb_02', logical: 'Wrong interface' }), 'Antrieb_01, Antrieb_02');
  assert.equal(messageBusNames({ hardware_interface_id: 'unknown' }, objects, {}), 'Nicht zugeordnet');
});
