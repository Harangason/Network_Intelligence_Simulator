import assert from 'node:assert/strict';
import test from 'node:test';
import { networkLabel, branchPath } from './network-names.ts';

test('generated bus labels are short while user names remain intact', () => {
  assert.equal(networkLabel('Antriebsstrang_01-S01'), 'Antriebsstrang_01');
  assert.equal(networkLabel('Antriebsstrang_01-S02'), 'Antriebsstrang_02');
  assert.equal(networkLabel('Fahrwerk_Fahrdynamik_03-S02'), 'Fahrwerk_Fahrdynamik_02');
  assert.equal(networkLabel('Antriebsstrang_01-IO-abgasnachbehandlung-lin-S01'), 'Abgasnachbehandlung LIN 01');
  assert.equal(networkLabel('Antriebsstrang_01-IO-abgasnachbehandlung-lin-S01', 'can_fd'), 'Abgasnachbehandlung CAN-FD 01');
  assert.equal(networkLabel('Mein Bus mit eigenem Namen'), 'Mein Bus mit eigenem Namen');
});

test('aligned gateway branch has no zero-length segment at its arrowhead', () => {
  assert.equal(branchPath([{x:10,y:10},{x:10,y:40},{x:10,y:40}]), 'M 10 10 L 10 40');
});
