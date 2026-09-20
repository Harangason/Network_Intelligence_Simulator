import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { extractEngineeringSpecification, extractEngineeringTargetCounts } from './engineering-specification.ts';

const fixture = JSON.parse(readFileSync(new URL('../../../../tests/fixtures/industry40.json', import.meta.url)));
for (const scenario of fixture.cases) {
  test(scenario.id + ': preserve explicitly stated hardware quantities', () => {
    const actual = extractEngineeringSpecification(scenario.input, {}, 'custom').targetCounts;
    for (const [role, count] of Object.entries(scenario.counts)) {
      if (count !== null) assert.equal(actual[role], count, role);
    }
  });
}

test('typed groups add, repeated totals and network assignments do not duplicate devices', () => {
  assert.equal(extractEngineeringTargetCounts('12 Encoder\n4 Safety Sensoren').sensors, 16);
  assert.equal(extractEngineeringTargetCounts('16 Strom-/Spannungssensoren\nCAN-FD für 8 Sensoren').sensors, 16);
  assert.equal(extractEngineeringTargetCounts('100 Sensoren\n20 Temperatursensoren\n100 Sensoren insgesamt').sensors, 100);
  assert.equal(extractEngineeringTargetCounts('1 Gateway\n1 Gateway mit Ethernet').gateways, 1);
});

test('an abstract coupling and technology names do not declare gateway hardware', () => {
  assert.equal(extractEngineeringTargetCounts('1 zentrale Kopplung\nCAN-FD und Ethernet').gateways, 0);
});

test('S04-A creates identities for the explicitly counted gateway and fan actuators', () => {
  const input = `1 Controller
4 Temperatursensoren über LIN
3 Lüfteraktoren über LIN
1 Gateway mit LIN- und Ethernet-Port

LIN:
19,2 kbit/s
Sensoren 500 ms
Lüfterstatus 250 ms

Ethernet:
100 Mbit/s

Funktionen:
ZoneTemperatureAcquire
FanControl
ThermalStatus`;
  const specification = extractEngineeringSpecification(input, {}, 'custom', true);
  const identities = new Map(specification.chains.map(chain => [chain.hardware_name, chain.device_type]));

  assert.equal([...identities.values()].filter(type => type === 'Gateway').length, 1);
  assert.equal([...identities.values()].filter(type => type === 'ActuatorController').length, 3);
  assert.deepEqual(
    [...identities.entries()].filter(([, type]) => type === 'ActuatorController').map(([name]) => name).sort(),
    ['Luefteraktor1', 'Luefteraktor2', 'Luefteraktor3'],
  );
});
