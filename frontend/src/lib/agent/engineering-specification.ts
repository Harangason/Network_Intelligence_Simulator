export type ExtractedEngineeringChain = {
  hardware_name: string;
  hardware_description: string;
  device_type: string;
  function_name: string;
  function_description: string;
  interface_name: string;
  interface_type: string;
  message_name: string;
  message_id_hex: string;
  direction: "tx";
  cycle_ms: number;
  dlc: number;
  signal_name: string;
  signal_display_name: string;
  start_bit: number;
  length_bits: number;
  byte_order: "little_endian";
  data_type: "signed" | "unsigned";
  factor: number;
  offset_value: number;
  unit?: string;
  min_value?: number;
  max_value?: number;
  domain: string;
};

export type ExtractedEngineeringSpecification = {
  chains: ExtractedEngineeringChain[];
  domain: string;
  interfaceType: string;
};

type HardwareOccurrence = {
  index: number;
  name: string;
};

const GENERIC_HARDWARE_LABELS = new Set([
  "hardware objekte",
  "hardware objekt",
  "sensors",
  "sensoren",
  "ecus",
  "gateways",
]);

const PARAMETER_LABEL_PATTERN =
  /^(messbereich|aufloesung|auflösung|schrittweite|sollwert|grenzwerte?|kommunikationsprotokoll|kreistellen|warnhinweis|mindest|maximum|minimum|parameter|technische parameter|funktions parameter)/i;

function cleanLabel(value: string) {
  return value
    .replace(/[*_`#]/g, "")
    .replace(/\s*:\s*$/, "")
    .replace(/\s+/g, " ")
    .trim();
}

function normalized(value: string) {
  return value
    .toLowerCase()
    .replace(/ä/g, "ae")
    .replace(/ö/g, "oe")
    .replace(/ü/g, "ue")
    .replace(/ß/g, "ss")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function headingLabel(line: string) {
  const bold = line.match(/\*\*(.+?)\*\*/)?.[1];
  if (bold) return cleanLabel(bold);
  const bullet = line.match(/^\s*(?:[-*]|\d+\.)\s+(.+?)\s*$/)?.[1];
  if (!bullet) return "";
  // Compact specifications often put type and parameters on the same bullet.
  // Only the leading label identifies the hardware participant.
  return cleanLabel(bullet.split(/\s*[:,]\s*/, 1)[0] ?? "");
}

function hardwareName(label: string) {
  const name = cleanLabel(label);
  const key = normalized(name);
  if (!key || GENERIC_HARDWARE_LABELS.has(key)) return "";
  if (/^(gateway|central gateway|can fd gateway)$/i.test(name)) return name;
  return /(?:sensor|ecu|gateway|plc|controller|steuergeraet)$/i.test(key.replace(/\s+/g, ""))
    ? name
    : "";
}

function deviceType(name: string) {
  const key = normalized(name);
  if (key.includes("gateway")) return "Gateway";
  if (key.includes("sensor")) return "SensorController";
  if (key.includes("plc")) return "PLC";
  if (key.includes("controller")) return "GenericDevice";
  return "ECU";
}

function protocolFrom(text: string) {
  const key = normalized(text);
  if (key.includes("can fd") || key.includes("canfd")) return "CAN_FD";
  if (key.includes("ethercat")) return "EtherCAT";
  if (key.includes("profinet")) return "ProfiNET";
  if (key.includes("automotive ethernet") || key.includes("ethernet")) return "Ethernet";
  if (key.includes("modbus tcp")) return "ModbusTCP";
  if (key.includes("opc ua")) return "OPCUA";
  return "CAN";
}

function domainFrom(text: string) {
  const key = normalized(text);
  if (/automotive|fahrzeug|ecu|can fd/.test(key)) return "automotive";
  if (/industrial|plc|profinet|ethercat/.test(key)) return "industrial_automation";
  if (/aerospace|arinc|avionik/.test(key)) return "aerospace";
  return "generic";
}

function numeric(value: string | undefined) {
  if (!value) return undefined;
  const result = Number(value.replace(",", "."));
  return Number.isFinite(result) ? result : undefined;
}

function rangeFrom(text: string) {
  const match = text.match(/(-?\d+(?:[,.]\d+)?)\s*(?:°\s*c|a|u\s*\/\s*min|\/\s*min)?\s*(?:bis|–|—)\s*\+?(-?\d+(?:[,.]\d+)?)/i);
  return { min: numeric(match?.[1]), max: numeric(match?.[2]) };
}

function factorFrom(text: string, unit: string | undefined) {
  const match = text.match(/(?:auflösung|aufloesung|schrittweite)\s*:?\s*(-?\d+(?:[,.]\d+)?)/i);
  const explicit = numeric(match?.[1]);
  if (explicit !== undefined) return explicit;
  return unit === "degC" || unit === "A" ? 0.1 : 1;
}

function unitFrom(text: string) {
  if (/°\s*c/i.test(text)) return "degC";
  if (/u\s*\/\s*min|\/\s*min/i.test(text)) return "rpm";
  if (/(^|\s)\d+(?:[,.]\d+)?\s*a\b/i.test(text)) return "A";
  return undefined;
}

function baseName(name: string) {
  return name
    .replace(/[-_\s]*(sensor|ecu|gateway|plc|controller|steuergeraet)$/i, "")
    .replace(/[^a-zA-Z0-9äöüÄÖÜß]+/g, " ")
    .trim() || name;
}

function identifier(value: string) {
  const words = value.replace(/[^a-zA-Z0-9äöüÄÖÜß]+/g, " ").trim().split(/\s+/);
  return words.map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join("");
}

function functionName(name: string, contexts: string[]) {
  for (const line of contexts) {
    const label = headingLabel(line);
    if (!label || hardwareName(label) || PARAMETER_LABEL_PATTERN.test(normalized(label))) continue;
    if (GENERIC_HARDWARE_LABELS.has(normalized(label))) continue;
    if (/^(hardware objekte|technische parameter|funktions parameter)$/i.test(normalized(label))) continue;
    return `${identifier(name)}_${identifier(label)}`;
  }
  const key = normalized(name);
  if (key.includes("sensor")) return `${identifier(name)}_Erfassung`;
  if (key.includes("gateway")) return `${identifier(name)}_Kommunikation`;
  return `${identifier(name)}_Steuerung`;
}

function signalName(name: string, context: string) {
  const key = normalized(name);
  if (key.includes("drehzahl")) return "Drehzahl";
  if (key.includes("motorstrom")) return "Motorstrom";
  if (key.includes("thermal")) return "Solltemperatur";
  if (key.includes("motion")) return "Temperaturgrenzwert";
  if (key.includes("temperatur")) return "Temperatur";
  if (/warnhinweis/i.test(context)) return `${identifier(baseName(name))}Warnung`;
  if (key.includes("gateway")) return "GatewayStatus";
  return `${identifier(baseName(name))}Status`;
}

export function extractEngineeringSpecification(text: string): ExtractedEngineeringSpecification {
  const lines = text.split(/\r?\n/);
  const occurrences = lines.flatMap((line, index): HardwareOccurrence[] => {
    const name = hardwareName(headingLabel(line));
    return name ? [{ index, name }] : [];
  });
  const contexts = new Map<string, { name: string; lines: string[] }>();
  occurrences.forEach((occurrence, occurrenceIndex) => {
    const nextIndex = occurrences[occurrenceIndex + 1]?.index ?? lines.length;
    const key = normalized(occurrence.name);
    const existing = contexts.get(key) ?? { name: occurrence.name, lines: [] };
    existing.lines.push(...lines.slice(occurrence.index, nextIndex));
    contexts.set(key, existing);
  });

  const domain = domainFrom(text);
  const interfaceType = protocolFrom(text);
  const chains = [...contexts.values()].map((entry, index): ExtractedEngineeringChain => {
    const context = entry.lines.map((line) => cleanLabel(line)).filter(Boolean).join("; ");
    const range = rangeFrom(context);
    const unit = unitFrom(context);
    const factor = factorFrom(context, unit);
    const signal = signalName(entry.name, context);
    const hardwareId = identifier(entry.name);
    return {
      hardware_name: entry.name,
      hardware_description: context.slice(0, 1000),
      device_type: deviceType(entry.name),
      function_name: functionName(entry.name, entry.lines),
      function_description: `Aus Nutzerspezifikation abgeleitete Funktion. ${context}`.slice(0, 1000),
      interface_name: `${hardwareId}_${interfaceType}`,
      interface_type: interfaceType,
      message_name: `${hardwareId}Data`,
      message_id_hex: `0x${(0x180 + index).toString(16).toUpperCase()}`,
      direction: "tx",
      cycle_ms: 10,
      dlc: 8,
      signal_name: signal,
      signal_display_name: signal,
      start_bit: 0,
      length_bits: 16,
      byte_order: "little_endian",
      data_type: (range.min ?? 0) < 0 ? "signed" : "unsigned",
      factor,
      offset_value: 0,
      unit,
      min_value: range.min,
      max_value: range.max,
      domain,
    };
  });

  return { chains, domain, interfaceType };
}

export function isStructuredEngineeringSpecification(text: string) {
  const extracted = extractEngineeringSpecification(text);
  const parameterEvidence = /(messbereich|auflösung|aufloesung|schrittweite|sollwert|grenzwert|kommunikationsprotokoll|funktions.parameter)/i.test(text);
  return extracted.chains.length >= 2 || (extracted.chains.length === 1 && parameterEvidence);
}
