export const SENSOR_MEASUREMENTS = [
  { id: 'object_list', label: 'Objektdaten', unit: 'byte', match: /object.?list|objekt.?liste|radar.*(?:objekt|object|track)/i,
    dataComplexity: 'STRUCTURED_OBJECT_LIST', semanticType: 'BYTE_ARRAY', elementType: 'OBJECT', payloadBytes: 1168, defaultCycleMs: 50 },
  { id: 'image_frame', label: 'Bilddaten', unit: 'byte', match: /kamera|camera|vision/i,
    dataComplexity: 'IMAGE_STREAM', semanticType: 'BYTE_ARRAY', elementType: 'IMAGE', payloadBytes: 1400, defaultCycleMs: 33 },
  { id: 'point_cloud', label: 'Punktwolke', unit: 'byte', match: /lidar|laser.?scanner/i,
    dataComplexity: 'POINT_CLOUD', semanticType: 'BYTE_ARRAY', elementType: 'POINT_CLOUD', payloadBytes: 1400, defaultCycleMs: 100 },
  { id: 'inertial_vector', label: 'Inertialdaten', unit: 'byte', match: /\bimu\b|inertial/i,
    dataComplexity: 'MULTI_VALUE', semanticType: 'BYTE_ARRAY', elementType: 'ARRAY', payloadBytes: 24, defaultCycleMs: 10 },
  { id: 'radar_detections', label: 'Radar-Detektionen', unit: 'byte', match: /radar.*(?:detection|detektion|returns)/i,
    dataComplexity: 'MULTI_VALUE', semanticType: 'BYTE_ARRAY', elementType: 'ARRAY', payloadBytes: 1168, defaultCycleMs: 50 },
  { id: 'navigation_fix', label: 'Navigationsmessung', unit: 'byte', match: /gnss|gps|navigation.?fix/i,
    dataComplexity: 'MULTI_VALUE', semanticType: 'BYTE_ARRAY', elementType: 'ARRAY', payloadBytes: 64, defaultCycleMs: 100 },
  { id: 'selector_state', label: 'Wahlzustand', unit: 'code', match: /gear.?selector|gangwahl|selector.?state/i },
  { id: 'linear_speed', label: 'Lineare Geschwindigkeit', unit: 'm/s', match: /linear.?speed|vehicle.?speed|ground.?speed|airspeed|geschwindigkeit/i },
  { id: 'relative_position', label: 'Relative Stellung', unit: '%', match: /pedal.?position|accelerator.?position|throttle.?position|clutch.?position|valve.?position|damper.?position|relative.?position/i },
  { id: 'safety_state', label: 'Sicherheitszustand', unit: 'code', match: /sicherheit|safety/i },
  { id: 'temperature', label: 'Temperatur', unit: 'degC', match: /temperatur|temperature|pt100/i },
  { id: 'speed', label: 'Drehzahl', unit: 'rpm', match: /drehzahl|rotational.?speed|(?:wheel|engine|motor|transmission.?input|transmission.?output|turbo).?speed/i },
  { id: 'torque', label: 'Drehmoment', unit: 'Nm', match: /drehmoment|torque/i },
  { id: 'pressure', label: 'Druck', unit: 'bar', match: /druck|pressure/i },
  { id: 'flow', label: 'Durchfluss', unit: 'l/min', match: /durchfluss|flow/i },
  { id: 'current', label: 'Strom', unit: 'A', match: /strom|current/i },
  { id: 'voltage', label: 'Spannung', unit: 'V', match: /spannung|voltage/i },
  { id: 'position', label: 'Physische Position', unit: 'm', match: /position|encoder/i },
  { id: 'angle', label: 'Winkel', unit: 'deg', match: /winkel|angle/i },
  { id: 'force', label: 'Kraft', unit: 'N', match: /kraft|force/i },
  { id: 'suspension_travel', label: 'Federweg', unit: 'mm', match: /suspension.?travel|federweg/i },
  { id: 'wheel_load', label: 'Radlast', unit: 'N', match: /wheel.?load|radlast/i },
  { id: 'tire_wear', label: 'Reifenverschleiß', unit: '%', match: /tire.?wear|reifenverschlei(?:ß|ss)/i },
  { id: 'angular_rate', label: 'Drehrate', unit: 'deg/s', match: /(?:yaw|pitch|roll).?rate|gier.?rate|nick.?rate|roll.?rate/i },
  { id: 'humidity', label: 'Luftfeuchtigkeit', unit: '%', match: /feucht|humidity/i },
  { id: 'co2', label: 'CO2-Konzentration', unit: 'ppm', match: /\bco2\b|kohlendioxid/i },
  { id: 'presence', label: 'Präsenz', unit: 'state', match: /präsenz|praesenz|presence|anwesenheit/i },
  { id: 'ph', label: 'pH-Wert', unit: 'pH', match: /(?:^|[^a-z])ph(?:[^a-z]|$)|ph.wert/i },
  { id: 'conductivity', label: 'Leitfähigkeit', unit: 'uS/cm', match: /leitfähigkeit|leitfaehigkeit|conductivity/i },
  { id: 'fill_level', label: 'Füllstand', unit: '%', match: /füllstand|fuellstand|fill.?level|(?:coolant|fuel|oil|urea|washer.?fluid).?level/i },
  { id: 'distance', label: 'Abstand', unit: 'm', match: /abstand|distance/i },
  { id: 'acceleration', label: 'Beschleunigung', unit: 'm/s²', match: /beschleunigung|acceleration/i },
] as const;

export function sensorMeasurement(name: string, signal = '') {
  return SENSOR_MEASUREMENTS.find(item => item.match.test(signal))
    ?? SENSOR_MEASUREMENTS.find(item => item.match.test(name));
}

export function sensorMeasurementSelections(text: string): Record<string, string> {
  const raw = text.match(/^- Sensor-Messgrößen:\s*(\{[^\r\n]*\})\s*$/m)?.[1];
  try {
    const value: unknown = JSON.parse(raw ?? '{}');
    if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
    return Object.fromEntries(Object.entries(value).filter(([name, id]) =>
      /^[\p{L}\d][\p{L}\d _-]{0,99}$/u.test(name) && SENSOR_MEASUREMENTS.some(item => item.id === id)));
  } catch { return {}; }
}

export function selectSensorMeasurement(text: string, name: string, id: string) {
  return selectSensorMeasurements(text, { [name]: id });
}

export function selectSensorMeasurements(text: string, values: Record<string, string>) {
  const selections = sensorMeasurementSelections(text);
  let changed = false;
  for (const [name, id] of Object.entries(values)) {
    if (!/^[\p{L}\d][\p{L}\d _-]{0,99}$/u.test(name) || !SENSOR_MEASUREMENTS.some(item => item.id === id)) continue;
    if (selections[name] === id) continue;
    selections[name] = id;
    changed = true;
  }
  if (!changed) return text;
  return `${text.replace(/\n?^- Sensor-Messgrößen:[^\r\n]*$/gm, '').trim()}\n- Sensor-Messgrößen: ${JSON.stringify(selections)}`;
}

/** Same catalogue for every industry. Wire envelopes are simulation drafts, not device specifications. */
export function sensorMeasurementContract(name: string, signal: { name?: string; unit?: string; min_value?: number | null;
  max_value?: number | null; factor?: number; length_bits?: number; data_type?: string; cycle_ms?: number;
  configuration?: Record<string, unknown> } = {}, selected?: string) {
  const profile = SENSOR_MEASUREMENTS.find(item => item.id === selected) ?? sensorMeasurement(name, signal.name);
  const axis = /longitudinal|laengs/i.test(name) ? 'x' : /lateral|quer/i.test(name) ? 'y'
    : /vertical|vertikal/i.test(name) ? 'z' : /yaw|gier/i.test(name) ? 'z'
      : /pitch|nick/i.test(name) ? 'y' : /roll/i.test(name) ? 'x' : null;
  const common = { version: 1, profile_id: profile?.id ?? null,
    quantity: profile?.label ?? 'UNKNOWN', unit: signal.unit ?? profile?.unit ?? 'UNKNOWN',
    provenance: 'SIMULATION_DESIGN_REQUIRES_DEVICE_REVIEW',
    instrument_range: null, uncertainty: null, resolution: signal.factor ?? null,
    encoding: { bits: signal.length_bits ?? null, raw_type: signal.data_type ?? null,
      factor: signal.factor ?? null, minimum: signal.min_value ?? null, maximum: signal.max_value ?? null },
    measurement_time: { timestamp_source: null, clock: null, synchronization: null },
    acquisition: { sample_period_ms: null, source: 'UNKNOWN' },
    transport: { period_ms: signal.cycle_ms ?? null, source: 'CANONICAL_MESSAGE_ONLY' },
    reference_frame: { id: null, axis, source: 'NAME_HINT_REQUIRES_REVIEW' },
    validity: { source: null, invalid_encoding: null, stale_after_ms: null },
    open_requirements: ['device_range', 'uncertainty', 'measurement_timestamp', 'sampling_rate', 'validity'],
  };
  if (!profile || !('payloadBytes' in profile)) return { ...common,
    ...(profile?.id === 'selector_state' ? { state_vocabulary: null, physical_position: false } : {}) };
  const schema = profile.id === 'image_frame' ? {
    kind: 'IMAGE_FRAME', width: null, height: null, pixel_encoding: null, row_stride_bytes: null,
    frame_bytes: null, optical_frame: null, acquisition_timestamp: null,
    transport_fragment_bytes: profile.payloadBytes, complete_frame: false,
  } : profile.id === 'point_cloud' ? {
    kind: 'POINT_CLOUD', fields: ['x', 'y', 'z'].map(name => ({ name, unit: 'm', type: 'float32' })),
    point_stride_bytes: 12, width: null, height: null, point_count: null, cloud_bytes: null,
    coordinate_frame: null, acquisition_timestamp: null, transport_fragment_bytes: profile.payloadBytes, complete_cloud: false,
  } : profile.id === 'inertial_vector' ? {
    kind: 'INERTIAL_VECTOR', fields: ['acceleration_x', 'acceleration_y', 'acceleration_z', 'angular_velocity_x',
      'angular_velocity_y', 'angular_velocity_z'].map(name => ({ name, type: 'float32',
        unit: name.startsWith('acceleration') ? 'm/s2' : 'rad/s' })),
    payload_bytes: 24, orientation: null, covariance: null, coordinate_frame: null, acquisition_timestamp: null,
  } : profile.id === 'navigation_fix' ? {
    kind: 'NAVIGATION_FIX', fields: [{ name: 'latitude', unit: 'deg', type: 'float64' },
      { name: 'longitude', unit: 'deg', type: 'float64' }, { name: 'altitude', unit: 'm', type: 'float64' },
      ...['velocity_x', 'velocity_y', 'velocity_z'].map(name => ({ name, unit: 'm/s', type: 'float64' })),
      { name: 'timestamp', unit: 'us', type: 'uint64' }, { name: 'fix_status', type: 'uint32' },
      { name: 'position_uncertainty', unit: 'm', type: 'float32' }], payload_bytes: 64,
    geodetic_datum: null, altitude_datum: null, velocity_frame: null, fix_vocabulary: null,
  } : profile.id === 'radar_detections' ? {
    kind: 'RADAR_DETECTIONS', header_bytes: 16, record_bytes: 24, max_records: 48, payload_bytes: 1168,
    header: [{ name: 'timestamp', type: 'uint64', unit: 'us' }, { name: 'frame_id', type: 'uint32' },
      { name: 'detection_count', type: 'uint16' }, { name: 'validity_flags', type: 'uint16' }],
    fields: [{ name: 'range', unit: 'm' }, { name: 'azimuth', unit: 'rad' }, { name: 'elevation', unit: 'rad' },
      { name: 'radial_velocity', unit: 'm/s' }, { name: 'amplitude', unit: 'UNKNOWN' },
      { name: 'range_variance', unit: 'm2' }].map(field => ({ ...field, type: 'float32' })),
    coordinate_frame: null, time_base: null, classification_supported: false, cartesian_velocity_supported: false,
  } : { kind: 'OBJECT_LIST', object_count: null, coordinate_frame: null, time_base: null,
    fields: null, transport_envelope_bytes: profile.payloadBytes };
  return { ...common, structured_payload: { ...schema, byte_order: 'little_endian',
    provenance: 'ILLUSTRATIVE_WIRE_DESIGN', measured_data_evidence: 'NONE' } };
}
