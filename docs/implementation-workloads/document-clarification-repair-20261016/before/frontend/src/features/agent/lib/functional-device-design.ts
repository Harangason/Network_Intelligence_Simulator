import type { ExtractedEngineeringChain } from './engineering-specification.ts';
import { SENSOR_MEASUREMENTS, sensorMeasurement, sensorMeasurementSelections, sensorMeasurementContract } from './sensor-measurements.ts';

/** Functional roles are independent of industry, device class and transport. */
export function perceptionRole(name: string) {
  if (/kamera|camera|vision|bildverarbeitung/i.test(name)) return 'image_frame';
  if (/lidar|laser.?scanner/i.test(name)) return 'point_cloud';
  if (/radar/i.test(name)) return 'object_list';
  if (/ultraschall|ultrasonic/i.test(name)) return 'distance';
  return null;
}

export function perceptionConsumer(name: string) {
  return /fahrerassistenz|autonom|navigation|motion.?planning|bewegungsplanung|sensorfusion|perception.?fusion/i.test(name);
}

export function usesFunctionalDeviceDesign(prompt: string) {
  return /^- Funktionaler Generierungsvertrag:\s*sensor-actuator-v1\s*$/m.test(prompt)
    || !/per Wizard-Uebernehmen bestaetigt/.test(prompt)
    || /^- Generierungsmodus:\s*EXAMPLE_PROJECT\s*$/m.test(prompt);
}

// Bounded, editable wire design; no detected objects or measured values are invented.
export const OBJECT_LIST_SCHEMA = {
  version: 1, design_evidence: 'ILLUSTRATIVE_WIRE_DESIGN', processing_evidence: 'NONE', field_validity: 'REQUIRES_REVIEW', byte_order: 'little_endian', max_objects: 32, payload_bytes: 1168,
  header_bytes: 16, object_bytes: 36, coordinate_frame: 'SOURCE_LOCAL_REQUIRES_REVIEW',
  header: [
    { name: 'frame_id', offset_bytes: 0, bits: 32, type: 'unsigned' },
    { name: 'timestamp', offset_bytes: 4, bits: 64, type: 'unsigned', unit: 'us', time_base: 'SOURCE_CLOCK_REQUIRES_REVIEW' },
    { name: 'object_count', offset_bytes: 12, bits: 16, type: 'unsigned', maximum: 32 },
    { name: 'coordinate_frame_id', offset_bytes: 14, bits: 16, type: 'unsigned' },
  ],
  fields: [
    { name: 'object_id', offset_bytes: 0, bits: 32, type: 'unsigned' },
    { name: 'validity_flags', offset_bytes: 4, bits: 16, type: 'unsigned', vocabulary: 'REQUIRES_REVIEW' },
    { name: 'classification', offset_bytes: 6, bits: 16, type: 'unsigned', vocabulary: 'REQUIRES_REVIEW' },
    { name: 'confidence', offset_bytes: 8, bits: 32, type: 'float', maximum: 1 },
    ...['x', 'y', 'z', 'velocity_x', 'velocity_y', 'velocity_z'].map((name, index) => ({ name, offset_bytes: 12 + index * 4,
      bits: 32, type: 'float', unit: name.startsWith('velocity') ? 'm/s' : 'm' })),
  ],
};

/** Enrich only new drafts. Explicit measurements and imported encodings win. */
export function completeFunctionalDeviceDesign(chains: ExtractedEngineeringChain[], prompt = '', includeOutputs = true) {
  if (!usesFunctionalDeviceDesign(prompt)) return chains;
  const choices = sensorMeasurementSelections(prompt);
  const devices = new Map(chains.map(chain => [chain.hardware_name, chain]));
  const result = chains.map(chain => {
    if (chain.device_type !== 'SensorController' || chain.configuration?.generation_role) return chain;
    const owner = String(chain.configuration?.functional_owner ?? '');
    const explicit = choices[chain.hardware_name] ?? chain.configuration?.sensor_measurement;
    const inferred = explicit || sensorMeasurement(chain.hardware_name, chain.signal_name)?.id
      || (/^Sensor\d+$/i.test(chain.hardware_name) ? perceptionRole(owner) : null);
    const measurement = SENSOR_MEASUREMENTS.find(item => item.id === inferred);
    const base = { ...chain,
      ...(measurement && 'payloadBytes' in measurement ? { device_class: chain.device_class ?? 3,
        data_complexity: measurement.dataComplexity, payload_element_type: measurement.elementType } : {}),
      configuration: { ...chain.configuration, measurement_contract: sensorMeasurementContract(chain.hardware_name, { name: chain.signal_name, unit: measurement && 'payloadBytes' in measurement ? 'byte' : chain.unit, min_value: measurement && 'payloadBytes' in measurement ? undefined : chain.min_value, max_value: measurement && 'payloadBytes' in measurement ? undefined : chain.max_value, factor: chain.factor, length_bits: measurement && 'payloadBytes' in measurement ? measurement.payloadBytes * 8 : chain.length_bits, data_type: chain.data_type, cycle_ms: chain.cycle_ms }, measurement?.id), functional_device_contract: {
      version: 1, role: 'SENSOR', measurement: measurement?.id ?? null, owner_name: owner || null,
      evidence: (chain.configuration?.functional_device_contract as { evidence?: string } | undefined)?.evidence
        ?? (explicit ? 'explicit_measurement' : 'semantic_draft_requires_review'),
    } } };
    if (!explicit && measurement?.id === 'distance' && /^Sensor\d+$/i.test(chain.hardware_name)) {
      return { ...base, signal_name: `Abstand_${chain.hardware_name}`, signal_display_name: `Abstand_${chain.hardware_name}`,
        length_bits: 17, dlc: 3, start_bit: 0, factor: 0.01, offset_value: 0, unit: 'm', min_value: 0, max_value: 1000,
        semantic: { semantic_type: 'NUMERIC', meaning: 'Gemessener Abstand', unit: 'm' },
        data: { minimum: 0, maximum: 1000, resolution: 0.01 },
        configuration: { ...base.configuration, sensor_measurement: 'distance',
          measurement_source: 'functional_owner_draft_requires_review', encoding_type: 'linear',
          raw_datatype: 'unsigned', bit_length: 17, factor: 0.01, offset: 0 },
      } satisfies ExtractedEngineeringChain;
    }
    if (!measurement || !('payloadBytes' in measurement) || chain.semantic?.semantic_type === 'BYTE_ARRAY') return base;
    return { ...base, device_class: chain.device_class ?? 3,
      signal_name: `${measurement.label}_${chain.hardware_name}`, signal_display_name: `${measurement.label}_${chain.hardware_name}`,
      data_complexity: measurement.dataComplexity, payload_element_type: measurement.elementType,
      length_bits: measurement.payloadBytes * 8, start_bit: 0, dlc: measurement.payloadBytes,
      factor: 1, offset_value: 0, unit: 'byte', min_value: undefined, max_value: undefined,
      semantic: { semantic_type: 'BYTE_ARRAY', meaning: measurement.label, unit: 'not_applicable' },
      data: { payload_bytes: measurement.payloadBytes },
      quality: { ...chain.quality, value_domain_complete: true },
      configuration: { ...base.configuration, structured_payload: 'structured_payload' in base.configuration.measurement_contract ? base.configuration.measurement_contract.structured_payload : undefined, sensor_measurement: measurement.id, encoding_type: 'raw',
        measurement_source: 'functional_owner_draft_requires_review' },
    } satisfies ExtractedEngineeringChain;
  });
  if (!includeOutputs) return result;
  for (const device of devices.values()) {
    if (device.device_type === 'SensorController' || device.device_type === 'ActuatorController' || device.device_type === 'Gateway') continue;
    const role = perceptionRole(`${device.hardware_name} ${device.function_name}`);
    const sensors = [...devices.values()].filter(item => item.device_type === 'SensorController'
      && item.configuration?.functional_owner === device.hardware_name).map(item => item.hardware_name);
    const actuators = [...devices.values()].filter(item => item.device_type === 'ActuatorController'
      && item.configuration?.functional_owner === device.hardware_name).map(item => item.hardware_name);
    if (!role) {
      if (sensors.length || actuators.length) {
        for (let index = 0; index < result.length; index++) {
          const item = result[index];
          if (item.hardware_name !== device.hardware_name) continue;
          result[index] = { ...item, configuration: { ...item.configuration, functional_device_contract: {
            version: 1, role: 'PROCESSOR', input_names: sensors, actuator_names: actuators,
            evidence: 'confirmed_device_ownership_processing_logic_requires_review',
          } } };
        }
      }
      continue;
    }
    const name = `${device.hardware_name}Objektdaten`;
    const existing = result.findIndex(item => item.hardware_name === device.hardware_name && item.signal_name === name);
    if (existing >= 0) {
      const output = result[existing];
      if ((output.configuration?.functional_device_contract as { role?: string } | undefined)?.role === 'PERCEPTION') {
        result[existing] = { ...output, configuration: { ...output.configuration, functional_device_contract: {
          ...(output.configuration!.functional_device_contract as Record<string, unknown>), input_names: sensors, actuator_names: actuators,
        } } };
      }
      continue;
    }
    result.push({ ...device, function_name: `${device.hardware_name}_Objektverarbeitung`,
      function_description: 'Messdaten verarbeiten und strukturierte Objektdaten bereitstellen; Algorithmus, Eingang, Objektvokabular und Zeit-/Koordinatenbezug fachlich bestätigen.',
      message_name: name, signal_name: name, signal_display_name: name,
      payload_element_type: 'OBJECT', length_bits: OBJECT_LIST_SCHEMA.payload_bytes * 8,
      start_bit: 0, dlc: OBJECT_LIST_SCHEMA.payload_bytes, factor: 1, offset_value: 0,
      unit: 'byte', min_value: undefined, max_value: undefined,
      semantic: { semantic_type: 'BYTE_ARRAY', meaning: 'Verarbeitete Objektdaten', unit: 'not_applicable' },
      data: { payload_bytes: OBJECT_LIST_SCHEMA.payload_bytes },
      configuration: { ...device.configuration, generation_role: 'FUNCTION_OUTPUT', functional_output_template: true,
        communication_contract: { scope: 'FUNCTION_OUTPUT' }, encoding_type: 'raw',
        structured_payload: OBJECT_LIST_SCHEMA, processing_contract: { algorithm: null, evidence: 'NONE',
          input_kind: role, classification: 'UNKNOWN', cartesian_kinematics: 'UNKNOWN',
          coordinate_transform: null, timing: null, simulation_design: true },
        functional_device_contract: { version: 1, role: 'PERCEPTION', required_measurement: role,
          accepted_measurements: role === 'object_list' ? ['object_list', 'radar_detections']
            : role === 'image_frame' ? ['image_frame', 'object_list']
              : role === 'point_cloud' ? ['point_cloud', 'object_list'] : ['distance'],
          input_names: sensors, actuator_names: actuators, output_signal: name, evidence: 'semantic_draft_requires_review' },
        design_evidence: 'illustrative_template_requires_review' },
    });
  }
  return result;
}
