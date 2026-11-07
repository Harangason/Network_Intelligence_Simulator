import test from 'node:test';
import assert from 'node:assert/strict';
import { documentReviewSource } from './document-clarification.ts';
import { selectDeviceConnectionInTask } from './device-connections.ts';
import { selectSensorMeasurements } from './sensor-measurements.ts';

test('device reviews preserve specification identity across multiple system selections', () => {
  const source = 'Zwei Systeme mit KlimaECU, MotorECU und Temperatursensoren.';
  const first = selectDeviceConnectionInTask(source, 'KlimaECU', 'LIN');
  const second = selectSensorMeasurements(selectDeviceConnectionInTask(first, 'MotorECU', 'CAN_FD'), { Temperatur: 'temperature' });
  assert.equal(documentReviewSource(first), source);
  assert.equal(documentReviewSource(second), source);
  assert.notEqual(documentReviewSource(second + '\nEin neuer Teilnehmer.'), source);
});
