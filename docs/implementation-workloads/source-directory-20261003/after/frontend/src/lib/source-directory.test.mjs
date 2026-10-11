import test from 'node:test';
import assert from 'node:assert/strict';
import { sourceRows, displaySourceDate } from './source-directory.ts';

const row = (id, abbreviation, name, date = null) => ({id, name, publisher: 'Publisher', url: 'https://example.org/' + id,
  accessed_at: date, revisions: [], rights: {label: 'Ungeklärt'}, technologies: [{id, abbreviation, name: abbreviation}]});
const rows = [row('ethernet', 'ETHERNET', 'Ethernet specification', '2026-10-01'), row('can', 'CAN', 'CAN documentation'), row('i2c', 'I2C', 'I2C specification', '2026-09-29')];

test('default bus order and reversible column sort retain input and stable ties', () => {
  assert.deepEqual(sourceRows(rows, '').map(r => r.id), ['can', 'ethernet', 'i2c']);
  assert.deepEqual(sourceRows(rows, '', 'abbreviation', true).map(r => r.id), ['i2c', 'ethernet', 'can']);
  assert.deepEqual(rows.map(r => r.id), ['ethernet', 'can', 'i2c']);
});
test('fuzzy bus/source search handles typo, multi-term and no match', () => {
  assert.deepEqual(sourceRows(rows, 'ethernt').map(r => r.id), ['ethernet']);
  assert.deepEqual(sourceRows(rows, 'ethernt publisher').map(r => r.id), ['ethernet']);
  assert.deepEqual(sourceRows(rows, 'zzzzzz'), []);
  assert.equal(sourceRows(rows, '   ').length, 3);
});
test('technical provenance paragraphs cannot make every short fuzzy bus query match', () => {
  const unrelated = {...row('zigbee', 'ZIGBEE', 'Zigbee documentation'), revisions: ['Previously recorded individual technical source review; publication rights assessed separately; no Ethernet fallback']};
  assert.deepEqual(sourceRows([...rows, unrelated], 'ethernt').map(r => r.id), ['ethernet']);
});
test('unknown access dates remain last in both directions and are not fabricated', () => {
  for (const descending of [true, false]) assert.equal(sourceRows(rows, '', 'accessed_at', descending).at(-1).id, 'can');
  assert.equal(displaySourceDate(null), 'Nicht dokumentiert');
  assert.equal(displaySourceDate('2026-10-03'), '3.10.2026');
});
