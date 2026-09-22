export const SENSOR_MEASUREMENTS = [
  { id: 'image_frame', label: 'Bilddaten', unit: 'byte', match: /kamera|camera|vision/i,
    dataComplexity: 'IMAGE_STREAM', semanticType: 'BYTE_ARRAY', elementType: 'IMAGE', payloadBytes: 1400, defaultCycleMs: 33 },
  { id: 'point_cloud', label: 'Punktwolke', unit: 'byte', match: /lidar|laser.?scanner/i,
    dataComplexity: 'POINT_CLOUD', semanticType: 'BYTE_ARRAY', elementType: 'POINT_CLOUD', payloadBytes: 1400, defaultCycleMs: 100 },
  { id: 'inertial_vector', label: 'Inertialdaten', unit: 'byte', match: /\bimu\b|inertial/i,
    dataComplexity: 'MULTI_VALUE', semanticType: 'BYTE_ARRAY', elementType: 'ARRAY', payloadBytes: 24, defaultCycleMs: 10 },
  { id: 'safety_state', label: 'Sicherheitszustand', unit: 'code', match: /sicherheit|safety/i },
  { id: 'temperature', label: 'Temperatur', unit: 'degC', match: /temperatur|temperature|pt100/i },
  { id: 'speed', label: 'Drehzahl', unit: 'rpm', match: /drehzahl|rotationalspeed/i },
  { id: 'torque', label: 'Drehmoment', unit: 'Nm', match: /drehmoment|torque/i },
  { id: 'pressure', label: 'Druck', unit: 'bar', match: /druck|pressure/i },
  { id: 'flow', label: 'Durchfluss', unit: 'l/min', match: /durchfluss|flow/i },
  { id: 'current', label: 'Strom', unit: 'A', match: /strom|current/i },
  { id: 'voltage', label: 'Spannung', unit: 'V', match: /spannung|voltage/i },
  { id: 'position', label: 'Position', unit: '%', match: /position|encoder/i },
  { id: 'angle', label: 'Winkel', unit: 'deg', match: /winkel|angle/i },
  { id: 'force', label: 'Kraft', unit: 'N', match: /kraft|force/i },
  { id: 'humidity', label: 'Luftfeuchtigkeit', unit: '%', match: /feucht|humidity/i },
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
