import assert from 'node:assert/strict';
import test from 'node:test';
import { parameterTechnologySelection, registeredTechnologies } from './technology-catalog-selection.ts';

const catalog = { domains: [
  { id: 'automotive', technologies: [{ id: 'can_fd' }, { id: 'ethernet' }] },
  { id: 'embedded_systems', technologies: [{ id: 'i2c' }, { id: 'ethernet' }] },
] };

test('registered technologies remain selectable across industries without duplicate IDs', () => {
  assert.deepEqual(registeredTechnologies(catalog).map(item => item.id), ['can_fd', 'ethernet', 'i2c']);
});

test('confirmed custom wizard retains its industry and proposes its single I2C bus', () => {
  const context = { agent_wizard_status: { confirmed_at: '2026-09-30T11:32:50Z', model_type: 'custom',
    communication_system_counts: [{ id: 'i2c', count: 1 }] } };
  assert.deepEqual(parameterTechnologySelection({}, context), { domainId: 'custom', technologyId: 'i2c' });
  assert.deepEqual(parameterTechnologySelection({ industry: 'robotics_ros', technology: 'ethercat' }, context),
    { domainId: 'robotics_ros', technologyId: 'ethercat' });
});

test('unconfirmed or mixed requests do not silently choose Automotive or a bus', () => {
  assert.deepEqual(parameterTechnologySelection({}, {}), { domainId: '', technologyId: '' });
  const context = { agent_wizard_status: { confirmed_at: '2026-09-30T11:32:50Z', model_type: 'custom',
    communication_system_counts: [{ id: 'i2c', count: 1 }, { id: 'spi', count: 1 }] } };
  assert.deepEqual(parameterTechnologySelection({}, context), { domainId: 'custom', technologyId: '' });
});
