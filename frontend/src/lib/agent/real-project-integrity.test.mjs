import test from 'node:test';
import assert from 'node:assert/strict';
import {extractEngineeringSpecification} from './engineering-specification.ts';
import {buildEquipmentClusters} from './equipment-clustering.ts';

test('real counts cannot invent sensor types and CAN', () => {
  const spec = extractEngineeringSpecification('Ich möchte drei Sensoren.', {sensors:3, ecus:0, actuators:0, gateways:0}, 'custom', true);
  assert.equal(spec.chains.length, 0);
  assert.equal(spec.targetCounts.sensors, 3);
  assert.equal(spec.interfaceType, 'Other');
});
test('inflected valves cannot insert template owners', () => {
  const spec = extractEngineeringSpecification('Projekt mit einem Raspberry-Pi und drei Temperatursensoren und zwei Ventilen', {ecus:1,sensors:3,actuators:2,gateways:0}, 'embedded_systems', true);
  assert.deepEqual(spec.chains.map(c=>c.hardware_name), ['RaspberryPi','Temperatursensor1','Temperatursensor2','Temperatursensor3','Ventilaktor1','Ventilaktor2']);
  assert.ok(spec.chains.every(c=>c.interface_type === 'Other'));
});
test('zero controllers gives a missing-controller finding with recovery', () => {
  const spec = extractEngineeringSpecification('drei Temperatursensoren', {}, 'embedded_systems');
  const clusters = buildEquipmentClusters(spec.chains, [], 'embedded_systems');
  assert.equal(clusters.flatMap(c=>c.unassigned).length, 3);
  assert.ok(clusters.flatMap(c=>c.unassigned).every(d=>/Kein Controller vorhanden/.test(d.reason)));
  const amended = extractEngineeringSpecification('drei Temperatursensoren\nController namens "RaspberryPi".', {}, 'embedded_systems');
  assert.equal(buildEquipmentClusters(amended.chains, [], 'embedded_systems').flatMap(c=>c.unassigned).length, 0);
});
