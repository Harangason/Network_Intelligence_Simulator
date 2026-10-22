import { test } from 'node:test';
import assert from 'node:assert/strict';
import { completeFunctionalDeviceDesign, OBJECT_LIST_SCHEMA } from './functional-device-design.ts';
import { buildEquipmentClusters } from './equipment-clustering.ts';
import { packEngineeringChains, expandEngineeringSignalModel } from './engineering-specification.ts';
import { sensorMeasurement } from './sensor-measurements.ts';

const chain = (name, type, domain = 'custom', configuration = {}) => ({
  hardware_name: name, hardware_description: '', device_type: type, function_name: `${name}Function`,
  function_description: '', interface_name: `${name}_Ethernet`, interface_type: 'Ethernet', message_name: `${name}Data`,
  message_id_hex: '0x180', direction: 'tx', cycle_ms: 33, dlc: 1, signal_name: `${name}Value`,
  signal_display_name: `${name}Value`, start_bit: 0, length_bits: 8, byte_order: 'little_endian',
  data_type: 'unsigned', factor: 1, offset_value: 0, min_value: 0, max_value: 255, configuration, domain,
});

test('radar distance remains a scalar quantity; only declared object lists receive the object encoding', () => {
  assert.equal(sensorMeasurement('FrontRadarDistance')?.id, 'distance');
  assert.equal(sensorMeasurement('RadarObjectList')?.id, 'object_list');
  const source = { ...chain('FrontRadarDistance', 'SensorController', 'robotics_ros', { functional_owner: 'RadarProcessing' }),
    signal_name: 'Distance', unit: 'm', length_bits: 16, min_value: 0, max_value: 655.35, factor: 0.01 };
  const result = completeFunctionalDeviceDesign([source, chain('RadarProcessing', 'IndustrialPC', 'robotics_ros')]);
  const sensor = result.find(item => item.hardware_name === source.hardware_name);
  assert.equal(sensor.length_bits, source.length_bits);
  assert.equal(sensor.unit, 'm');
  assert.equal(sensor.configuration.functional_device_contract.measurement, 'distance');
  assert.deepEqual(result.find(item => item.configuration.functional_output_template).configuration.functional_device_contract.accepted_measurements, ['object_list', 'radar_detections']);
});

test('placeholder camera inputs and processed objects work independently of industry and device names', () => {
  for (const domain of ['automotive', 'robotics_ros', 'aerospace', 'building_automation', 'custom']) {
    const input = [chain('Kameraverarbeitung', 'IndustrialPC', domain),
      chain('Sensor1', 'SensorController', domain, { functional_owner: 'Kameraverarbeitung' }),
      chain('AutonomeNavigation', 'IndustrialPC', domain)];
    const result = completeFunctionalDeviceDesign(input);
    const sensor = result.find(item => item.hardware_name === 'Sensor1');
    assert.equal(sensor.configuration.sensor_measurement, 'image_frame');
    assert.equal(sensor.semantic.semantic_type, 'BYTE_ARRAY');
    assert.equal(sensor.interface_type, 'Ethernet');
    const output = result.find(item => item.configuration.functional_output_template);
    assert.equal(output.configuration.communication_contract.scope, 'FUNCTION_OUTPUT');
    assert.deepEqual(output.configuration.functional_device_contract.input_names, ['Sensor1']);
    assert.equal(output.data.payload_bytes, OBJECT_LIST_SCHEMA.header_bytes + OBJECT_LIST_SCHEMA.max_objects * OBJECT_LIST_SCHEMA.object_bytes);
    const packed = packEngineeringChains(expandEngineeringSignalModel(result));
    assert.ok(packed.some(item => item.signal_name === sensor.signal_name && item.semantic.semantic_type === 'BYTE_ARRAY'));
    const message = packed.find(item => item.signal_name === output.signal_name);
    assert.equal(message.dlc, 1168);
    assert.equal(packed.filter(item => item.message_name === message.message_name).length, 1);
    const clusters = buildEquipmentClusters(result, [{ id: 'Ethernet', label: 'Ethernet' }], domain);
    const route = clusters.flatMap(item => item.functionalRoutes).find(item => item.source === 'Kameraverarbeitung' && item.target === 'AutonomeNavigation');
    assert.deepEqual(route.signals, [output.signal_name]);
    assert.equal(route.review_status, 'REVIEW_REQUIRED');
    assert.deepEqual(completeFunctionalDeviceDesign(result), result);
  }
});

test('explicit scalar choice is not converted into camera data and an unknown sensor stays unresolved', () => {
  const result = completeFunctionalDeviceDesign([
    chain('Sensor1', 'SensorController', 'custom', { functional_owner: 'Kameraverarbeitung', sensor_measurement: 'temperature' }),
    chain('Sensor2', 'SensorController'), chain('Gateway', 'Gateway'),
  ]);
  assert.equal(result[0].configuration.functional_device_contract.measurement, 'temperature');
  assert.equal(result[0].length_bits, 8);
  assert.equal(result[1].configuration.functional_device_contract.measurement, null);
  assert.equal(result.length, 3);
});

test('missing sensors and consumers produce open functional review issues without inventing devices', () => {
  const input = [chain('CameraProcessing', 'IndustrialPC')];
  const clusters = buildEquipmentClusters(input, [{ id: 'Ethernet', label: 'Ethernet' }], 'custom');
  assert.ok(clusters.flatMap(item => item.functionalIssues).some(message => /Messdateneingang/.test(message)));
  assert.ok(clusters.flatMap(item => item.functionalIssues).some(message => /Empfänger/.test(message)));
  assert.equal(clusters.flatMap(item => item.functionalRoutes).length, 0);
});

test('imported reviewed signal encodings stay unchanged', () => {
  const input = [chain('Kameraverarbeitung', 'ECU'), chain('Sensor1', 'SensorController')];
  assert.equal(completeFunctionalDeviceDesign(input, 'per Wizard-Uebernehmen bestaetigt'), input);
});

test('a generic controller with source-scoped camera processing gets a reviewable object output', () => {
  for (const domain of ['automotive', 'robotics_ros', 'building_automation', 'custom']) {
    const input = [chain('ControlAlpha', 'ECU', domain, { source_scoped_functions: [
      { name: 'Kamera auswerten', source_quote: 'Kamera auswerten' },
    ] }), chain('Kamera', 'SensorController', domain, { functional_owner: 'ControlAlpha', sensor_measurement: 'image_frame' })];
    const result = completeFunctionalDeviceDesign(input);
    const output = result.find(item => item.configuration.functional_output_template);
    assert.ok(output);
    assert.equal(output.hardware_name, 'ControlAlpha');
    assert.deepEqual(output.configuration.functional_device_contract.input_names, ['Kamera']);
    assert.equal(output.configuration.functional_device_contract.source_functions[0].source_quote, 'Kamera auswerten');
    assert.equal(output.configuration.processing_contract.evidence, 'NONE');
  }
});

test('object outputs keep an explicitly selected narrow transport and remain oversized for validation', () => {
  const source = { ...chain('RadarProcessing', 'IndustrialPC'), interface_type: 'CAN', interface_name: 'explicit_CAN' };
  const result = completeFunctionalDeviceDesign([source]);
  const output = result.find(item => item.configuration.functional_output_template);
  assert.equal(output.interface_type, 'CAN');
  assert.equal(output.length_bits, 1168 * 8);
  assert.equal(OBJECT_LIST_SCHEMA.header.find(field => field.name === 'timestamp').time_base, 'SOURCE_CLOCK_REQUIRES_REVIEW');
});

test('co-located perception and planning remain distinct reviewed functions without a fake external receiver', () => {
  const host = chain('ControlAlpha', 'ECU', 'robotics_ros', { source_scoped_functions: [
    { name: 'Kamera auswerten', source_quote: 'Kamera auswerten' },
    { name: 'Motion Planning', source_quote: 'Motion Planning' },
  ] });
  const clusters = buildEquipmentClusters([host, chain('Kamera', 'SensorController', 'robotics_ros',
    { functional_owner: 'ControlAlpha', sensor_measurement: 'image_frame' })], [], 'robotics_ros');
  const branch = clusters.flatMap(cluster => cluster.controllers).find(controller => controller.name === 'ControlAlpha');
  assert.ok(branch.functions.some(fn => fn.name === 'ControlAlpha_Motion Planning' && fn.signals.length === 0));
  assert.equal(clusters.flatMap(cluster => cluster.functionalRoutes).length, 0);
  assert.ok(clusters.flatMap(cluster => cluster.functionalIssues).some(issue => issue.includes('innerhalb desselben Controllers') && issue.includes('Motion Planning')));
});
