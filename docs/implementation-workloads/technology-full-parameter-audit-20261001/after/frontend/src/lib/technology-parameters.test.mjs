import test from 'node:test';
import assert from 'node:assert/strict';
import { localEvidenceFieldRequired, booleanParameterValue, conditionalParameterDefault, technologyParameterValues, technologyParameterUnverified, confirmTechnologyParameters, confirmNetworkParameters, groupPreflightFindings } from './technology-parameters.ts';
const lin = { id: 'lin', parameter_schema: [{ key: 'bitrate', type: 'number', scope: 'network', unit: 'bit/s', default: 19200 }, { key: 'payload_bytes', default: 8 }] };
const can = { id: 'can_fd', parameter_schema: [{ key: 'arbitration_bitrate', default: 500000 }, { key: 'data_bitrate', default: 2000000 }] };
const parameters = { technology: 'can_fd', bitrate: 2000000, arbitration_bitrate: 500000, data_bitrate: 2000000,
  technology_defaults: { lin: { bitrate: 19200 } }, defaults_source: 'technology-registry', networks: [{ id: 'lin-1', technology: 'LIN' }, { id: 'lin-2', technology: 'LIN' }, { id: 'can-1', technology: 'CAN_FD' }],
  simulation_scope: { mode: 'ALL' }, spatial_architecture: { id: 'keep' } };

test('device evidence requirements follow controller, target and transaction scopes without inventing facts', () => {
  const address = {key:'slave_address',required_scopes:['TARGET_PORT','TRANSACTION']};
  const transaction = {key:'transfer_bits_bound',required_scopes:['TRANSACTION']};
  assert.equal(localEvidenceFieldRequired(address,{evidence_scope:'CONTROLLER_PORT'}),false);
  assert.equal(localEvidenceFieldRequired(address,{evidence_scope:'TARGET_PORT'}),true);
  assert.equal(localEvidenceFieldRequired(transaction,{evidence_scope:'TARGET_PORT'}),false);
  assert.equal(localEvidenceFieldRequired(transaction,{}),true); // Legacy means transaction, never controller inference.
  assert.equal(localEvidenceFieldRequired({key:'arbitration_bound_us',optional:true},{multi_master:false}),false);
  assert.equal(localEvidenceFieldRequired({key:'arbitration_bound_us',optional:true},{multi_master:true}),true);
  assert.equal(localEvidenceFieldRequired({key:'master_node_id'},{}),true);
});

test('unknown device boolean is not silently confirmed as false or parsed false as true', () => {
  assert.equal(booleanParameterValue({}, ''), null);
  assert.equal(booleanParameterValue({}, null), null);
  assert.equal(booleanParameterValue({}, 'false'), false);
  assert.equal(booleanParameterValue({}, 'true'), true);
  assert.throws(() => booleanParameterValue({}, 'on'));
  assert.equal(booleanParameterValue({default:false}, null), false);
  assert.equal(booleanParameterValue({default:false}, 'on'), true);
  const saved = confirmTechnologyParameters({}, {id:'avb',parameter_schema:[{key:'avb_as_capable',type:'boolean'}]},
    {avb_as_capable:booleanParameterValue({}, '')});
  assert.equal('avb_as_capable' in saved.technology_parameters.avb.values, false);
});

test('conditional standards require known conditions and preserve actual saved values', () => {
  const timeout = { key:'bacnet_apdu_timeout_ms', type:'number', scope:'route', conditional_defaults:[
    {when:{bacnet_apdu_timeout_modifiable:true}, value:3000},
    {when:{bacnet_apdu_timeout_modifiable:false}, value:60000}] };
  const profile = {id:'bacnet_ip', parameter_schema:[{key:'bacnet_apdu_timeout_modifiable',type:'boolean',scope:'route'}, timeout]};
  assert.equal(conditionalParameterDefault(timeout, {}), undefined);
  assert.equal(conditionalParameterDefault(timeout, {bacnet_apdu_timeout_modifiable:'false'}), undefined);
  assert.equal(conditionalParameterDefault(timeout, {bacnet_apdu_timeout_modifiable:false}), 60000);
  assert.equal(technologyParameterValues({}, profile).bacnet_apdu_timeout_ms, undefined);
  const known = {technology:'bacnet_ip',bacnet_apdu_timeout_modifiable:true};
  assert.equal(technologyParameterValues(known, profile).bacnet_apdu_timeout_ms, 3000);
  const saved = confirmTechnologyParameters({}, profile, {bacnet_apdu_timeout_modifiable:false,bacnet_apdu_timeout_ms:3000});
  assert.equal(technologyParameterValues(saved, profile).bacnet_apdu_timeout_ms, 3000);
  assert.equal(technologyParameterUnverified(known, 'bacnet_apdu_timeout_ms', 'bacnet_ip'), true);
  assert.equal(conditionalParameterDefault({conditional_defaults:[{when:{},value:1},{when:{},value:2}]}, {}), undefined);
});

test('SC connection purpose chooses its own conditional subprotocol and preserves explicit saved choices', () => {
  const protocol = {key:'sc_websocket_subprotocol',type:'select',scope:'network',conditional_defaults:[
    {when:{sc_connection_type:'HUB'},value:'hub.bsc.bacnet.org'},
    {when:{sc_connection_type:'DIRECT'},value:'dc.bsc.bacnet.org'}]};
  const sc = {id:'bacnet_sc',parameter_schema:[{key:'sc_connection_type',type:'select',default:'HUB'},protocol]};
  assert.equal(technologyParameterValues({},sc).sc_websocket_subprotocol,'hub.bsc.bacnet.org');
  const actual = confirmTechnologyParameters({},sc,{sc_connection_type:'DIRECT',sc_websocket_subprotocol:'dc.bsc.bacnet.org'});
  assert.equal(technologyParameterValues(actual,sc).sc_websocket_subprotocol,'dc.bsc.bacnet.org');
  assert.equal(technologyParameterUnverified({},'sc_websocket_subprotocol','bacnet_sc'),true);
  const foreign = {technology:'bacnet_ip',sc_connection_type:'DIRECT',bacnet_udp_port:47808};
  assert.equal(technologyParameterValues(foreign,sc).sc_websocket_subprotocol,'hub.bsc.bacnet.org');
});

test('retired fields keep their confirmed historical values while leaving active parameters', () => {
  const schema = { id: 'adc', parameter_schema: [{key:'cycle_ms', default:100}] };
  const proof = {source:'USER_CONFIRMED', status:'CONFIRMED', value:256};
  const old = {technology:'adc', queue_size:256, cycle_ms:10,
    parameter_provenance:{queue_size:proof}, technology_parameters:{adc:{values:{queue_size:256,cycle_ms:10},provenance:{queue_size:proof}}}};
  const before = structuredClone(old);
  const saved = confirmTechnologyParameters(old,schema,{cycle_ms:10});
  assert.equal('queue_size' in saved,false);
  assert.deepEqual(saved.technology_parameters.adc.values,{cycle_ms:10});
  assert.equal(saved.technology_parameters.adc.retired_parameters.values.queue_size,256);
  assert.deepEqual(saved.technology_parameters.adc.retired_parameters.provenance.queue_size,proof);
  assert.deepEqual(old,before);
  assert.deepEqual(confirmTechnologyParameters(saved,schema,{cycle_ms:10}).technology_parameters.adc.retired_parameters,
    saved.technology_parameters.adc.retired_parameters);
});

test('historical global proof survives even when no scoped group was recorded', () => {
  const schema = {id:'adc',parameter_schema:[{key:'cycle_ms'}]};
  const proof = {source:'USER_CONFIRMED',status:'CONFIRMED',value:256};
  const saved = confirmTechnologyParameters({technology:'adc',queue_size:256,parameter_provenance:{queue_size:proof}},schema,{cycle_ms:10});
  assert.equal('queue_size' in saved,false);
  assert.equal(saved.technology_parameters.adc.retired_parameters.values.queue_size,256);
  assert.deepEqual(saved.technology_parameters.adc.retired_parameters.provenance.queue_size,proof);
});

test('a proof naming a foreign technology cannot confirm the selected profile', () => {
  const technology = {id:'can',parameter_schema:[{key:'bitrate',type:'number',unit:'bit/s',default:10000}]};
  const proof = {source:'USER_CONFIRMED',status:'CONFIRMED',value:250000,technology:'nmea2000'};
  const global = {technology:'can',bitrate:250000,parameter_provenance:{bitrate:proof}};
  assert.equal(technologyParameterUnverified(global,'bitrate','can'),true);
  assert.equal(technologyParameterValues(global,technology).bitrate,10000);
  const scoped = {technology:'can',technology_parameters:{can:{values:{bitrate:250000},provenance:{bitrate:proof}}}};
  assert.equal(technologyParameterUnverified(scoped,'bitrate','can'),true);
  assert.equal(technologyParameterValues(scoped,technology).bitrate,10000);
});
test('LIN projection never inherits CAN-FD rate or its phases', () => {
  assert.deepEqual(technologyParameterValues(parameters, lin), { bitrate: 19200, payload_bytes: 8 });
  assert.equal(technologyParameterUnverified(parameters, 'bitrate', 'lin'), true);
});
test('known profile modes propose their lowest operating rate without confirming it', () => {
  const bitrateField = { key: 'bitrate', type: 'number', scope: 'network', unit: 'bit/s' };
  const cases = [
    [{ id: 'i2c', parameter_schema: [{...bitrateField, default:100000}], rate_model: { minimum_bps: 1 }, parameter_proposals: { options: [{ mode: 'Fast', maximum: 400000 }, { mode: 'Standard', maximum: 100000 }] } }, 100000],
    [{ id: 'lin', parameter_schema: [{ ...bitrateField, default: 9600 }], rate_model: { minimum_bps: 1, typical_bps: [19200, 9600] } }, 9600],
    [{ id: 'can', parameter_schema: [{ ...bitrateField, default: 10000 }], rate_model: { minimum_bps: 10000 } }, 10000],
    [{ id: 'ethernet', parameter_schema: [{ ...bitrateField, default: 10000000 }], rate_model: { allowed_bps: [1000000000, 10000000] } }, 10000000],
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
test('blank optional device facts are never persisted as confirmed values', () => {
  const radio = { id: '5g', parameter_schema: [{ key: 'nr_direction', type: 'select' },
    { key: 'nr_carrier_count', type: 'number' }, { key: 'retransmission_enabled', type: 'boolean' }] };
  const saved = confirmTechnologyParameters({}, radio, { nr_direction: '', nr_carrier_count: null, retransmission_enabled: false });
  assert.deepEqual(saved.technology_parameters['5g'].values, { retransmission_enabled: false });
  assert.equal('nr_direction' in saved.parameter_provenance, false);
  assert.equal('nr_carrier_count' in saved.parameter_provenance, false);
  assert.equal(technologyParameterUnverified(saved, 'nr_direction', '5g'), true);
});
test('the server schema owns review values and replaces obsolete unconfirmed rates only', () => {
  const i2c = { id: 'i2c', parameter_schema: [{key:'bitrate', unit:'bit/s', default:100000, min:1}], parameter_proposals:{candidate:400000} };
  assert.equal(technologyParameterValues({technology:'i2c', bitrate:0}, i2c).bitrate, 100000);
  assert.equal(technologyParameterValues({technology:'i2c', bitrate:400000, parameter_provenance:{bitrate:{status:'REVIEW_REQUIRED'}}}, i2c).bitrate, 100000);
  const saved = confirmTechnologyParameters({}, i2c, {bitrate:400000});
  assert.equal(technologyParameterValues(saved, i2c).bitrate, 400000);
  assert.equal(technologyParameterUnverified(saved,'bitrate','i2c'),false);
  const nmea = {id:'nmea2000', parameter_schema:[{key:'bitrate',unit:'bit/s',default:250000,allowed_bps:[250000]}]};
  assert.equal(technologyParameterValues({technology:'ethernet',bitrate:1000000000},nmea).bitrate,250000);
  assert.equal(technologyParameterValues({technology:'nmea2000',bitrate:1000000000},nmea).bitrate,250000);
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
test('changing a single-bus project preserves earlier scoped corrections and clears foreign global fields', () => {
  const old = confirmTechnologyParameters({}, { id: '5g', parameter_schema: [{key:'nr_direction'}] }, {nr_direction:'UL'});
  const saved = confirmTechnologyParameters(old, lin, {bitrate:9600});
  assert.equal('nr_direction' in saved, false);
  assert.equal('nr_direction' in saved.parameter_provenance, false);
  assert.equal(saved.technology_parameters['5g'].values.nr_direction, 'UL');
  assert.equal(old.nr_direction, 'UL');
});
test('changed global values and missing proofs remain unverified', () => {
  const saved = confirmTechnologyParameters({}, lin, {bitrate:9600});
  saved.bitrate = 19200;
  delete saved.technology_parameters;
  assert.equal(technologyParameterUnverified(saved, 'bitrate', 'lin'), true);
  assert.equal(technologyParameterUnverified({technology:'lin',bitrate:9600}, 'bitrate', 'lin'), true);
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
