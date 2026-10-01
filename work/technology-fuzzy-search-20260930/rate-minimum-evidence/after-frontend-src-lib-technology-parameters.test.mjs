import test from 'node:test';
import assert from 'node:assert/strict';
import { technologyParameterValues, technologyParameterUnverified, confirmTechnologyParameters, confirmNetworkParameters, groupPreflightFindings } from './technology-parameters.ts';
const lin = { id: 'lin', parameter_schema: [{ key: 'bitrate', type: 'number', scope: 'network', unit: 'bit/s', default: 19200 }, { key: 'payload_bytes', default: 8 }] };
const can = { id: 'can_fd', parameter_schema: [{ key: 'arbitration_bitrate', default: 500000 }, { key: 'data_bitrate', default: 2000000 }] };
const parameters = { technology: 'can_fd', bitrate: 2000000, arbitration_bitrate: 500000, data_bitrate: 2000000,
  technology_defaults: { lin: { bitrate: 19200 } }, defaults_source: 'technology-registry', networks: [{ id: 'lin-1', technology: 'LIN' }, { id: 'lin-2', technology: 'LIN' }, { id: 'can-1', technology: 'CAN_FD' }],
  simulation_scope: { mode: 'ALL' }, spatial_architecture: { id: 'keep' } };
test('LIN projection never inherits CAN-FD rate or its phases', () => {
  assert.deepEqual(technologyParameterValues(parameters, lin), { bitrate: 19200, payload_bytes: 8 });
  assert.equal(technologyParameterUnverified(parameters, 'bitrate', 'lin'), true);
});
test('known profile modes propose their lowest operating rate without confirming it', () => {
  const bitrateField = { key: 'bitrate', type: 'number', scope: 'network', unit: 'bit/s' };
  const cases = [
    [{ id: 'i2c', parameter_schema: [bitrateField], rate_model: { minimum_bps: 1 }, parameter_proposals: { options: [{ mode: 'Fast', maximum: 400000 }, { mode: 'Standard', maximum: 100000 }] } }, 100000],
    [{ id: 'lin', parameter_schema: [{ ...bitrateField, default: 19200 }], rate_model: { minimum_bps: 1, typical_bps: [19200, 9600] } }, 9600],
    [{ id: 'can', parameter_schema: [{ ...bitrateField, default: 500000 }], rate_model: { minimum_bps: 10000 } }, 10000],
    [{ id: 'ethernet', parameter_schema: [{ ...bitrateField, default: 1000000000 }], rate_model: { allowed_bps: [1000000000, 10000000] } }, 10000000],
  ];
  for (const [technology, expected] of cases) {
    assert.equal(technologyParameterValues({}, technology).bitrate, expected);
    assert.equal(technologyParameterUnverified({}, 'bitrate', technology.id), true);
  }
  const i2c = cases[0][0];
  assert.equal(technologyParameterValues({ technology: 'i2c', bitrate: 400000 }, i2c).bitrate, 400000);
  const confirmed = confirmTechnologyParameters({}, i2c, { bitrate: 400000 });
  assert.equal(technologyParameterValues(confirmed, i2c).bitrate, 400000);
  assert.equal(technologyParameterUnverified(confirmed, 'bitrate', 'i2c'), false);
});
test('device-dependent clock without a known operating mode remains open', () => {
  const spi = { id: 'spi', parameter_schema: [{ key: 'bitrate', type: 'number', unit: 'bit/s' }], rate_model: { minimum_bps: 1 } };
  assert.equal(technologyParameterValues({}, spi).bitrate, undefined);
});
test('declared confirmed LIN values survive switching and preserve mixed inventory', () => {
  const saved = confirmTechnologyParameters(parameters, lin, { bitrate: 9600, payload_bytes: 8 });
  assert.equal(saved.technology, 'can_fd'); assert.equal(saved.bitrate, 2000000);
  assert.deepEqual(saved.networks, parameters.networks); assert.deepEqual(saved.simulation_scope, parameters.simulation_scope);
  assert.equal(technologyParameterValues(saved, lin).bitrate, 9600); assert.equal(technologyParameterUnverified(saved, 'bitrate', 'lin'), false);
  assert.equal(technologyParameterValues(saved, can).data_bitrate, 2000000);
});
test('a simple project technology change clears incompatible phases', () => {
  const saved = confirmTechnologyParameters({ ...parameters, networks: [] }, lin, { bitrate: 19200, payload_bytes: 8 });
  assert.equal(saved.technology, 'lin'); assert.equal(saved.bitrate, 19200); assert.equal('data_bitrate' in saved, false); assert.equal('arbitration_bitrate' in saved, false);
});
test('CAN-FD data rate maps to calculation bitrate without losing nominal phase', () => {
  const saved = confirmTechnologyParameters(parameters, can, { arbitration_bitrate: 250000, data_bitrate: 4000000 });
  assert.equal(saved.bitrate, 4000000); assert.equal(saved.arbitration_bitrate, 250000);
});
test('a pending global profile proposal remains unverified', () => {
  assert.equal(technologyParameterUnverified({ technology: 'lin', bitrate: 19200, parameter_provenance: { bitrate: { source: 'TECHNOLOGY_PROFILE_REVIEW_PROPOSAL', status: 'REVIEW_REQUIRED' } } }, 'bitrate', 'lin'), true);
});
test('changed value invalidates an old confirmation', () => {
  const saved = confirmTechnologyParameters(parameters, lin, { bitrate: 19200, payload_bytes: 8 });
  saved.technology_parameters.lin.values.bitrate = 9600;
  assert.equal(technologyParameterUnverified(saved, 'bitrate', 'lin'), true);
});
test('explicit selection updates only the selected LIN network', () => {
  const saved = confirmNetworkParameters(parameters, lin, ['lin-2'], { bitrate: 19200, payload_bytes: 8 });
  assert.equal(saved.networks[1].bitrate, 19200); assert.equal(saved.networks[0].bitrate, undefined); assert.deepEqual(saved.networks[2], parameters.networks[2]);
  assert.equal(parameters.networks[1].bitrate, undefined); assert.deepEqual(saved.spatial_architecture, parameters.spatial_architecture);
});
test('deleted, foreign technology and empty selections reject before writes', () => {
  for (const ids of [[], ['removed'], ['lin-1', 'can-1']]) assert.throws(() => confirmNetworkParameters(parameters, lin, ids, { bitrate: 19200 }));
});
test('group related capacity/communication findings by exact object, preserving details', () => {
  const first = { object_type: 'Network', object_id: 'lin-1', code: 'CAPACITY_RATE_UNVERIFIED', message: 'Rate fehlt' };
  const groups = groupPreflightFindings([first, first, { ...first, code: 'COMMUNICATION_UNVERIFIED', message: 'Timing offen' }, { ...first, object_id: 'lin-2' }]);
  assert.equal(groups.length, 2); assert.equal(groups[0].findings.length, 2); assert.equal(groups[0].rateMissing, true);
});

test('pending scoped evidence remains unverified and partial rate confirmation preserves physical fields', () => {
  const saved = confirmTechnologyParameters(parameters, lin, { bitrate: 19200, payload_bytes: 8 });
  saved.technology_parameters.lin.provenance.bitrate.status = 'REVIEW_REQUIRED';
  assert.equal(technologyParameterUnverified(saved, 'bitrate', 'lin'), true);
  const profile = { ...lin, parameter_schema: [...lin.parameter_schema, {key: 'termination', scope: 'network'}] };
  const original = { ...parameters, networks: [{id:'lin-1',technology:'LIN',termination:'existing'}] };
  const updated = confirmNetworkParameters(original, profile, ['lin-1'], {bitrate:19200});
  assert.equal(updated.networks[0].termination, 'existing');
});
