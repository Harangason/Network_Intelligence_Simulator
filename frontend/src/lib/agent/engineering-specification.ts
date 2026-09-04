import { industryTemplateLabel, industryTemplateProfile } from "./industry-templates/index.ts";

/** Device roles belong to device_type; technical identifiers remain unchanged. */
export function normalizeHardwareName(value: string): string {
  const original = value.trim();
  return original.replace(/(?:[-_ ]?(?:ECU|Gateway|Sensor|Aktor|Aktuator|Actuator|Controller|Steuerger(?:ä|ae|a|�)t))+([-_ ]\d+)?$/i, "$1")
    .replace(/^[-_ ]+|[-_ ]+$/g, "") || original;
}

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
  configuration?: Record<string, unknown>;
  semantic?: Record<string, unknown>;
  data?: Record<string, unknown>;
  communication?: Record<string, unknown>;
  quality?: Record<string, unknown>;
  protocol_bindings?: Array<Record<string, unknown>>;
  transport_network_ref?: string;
  domain: string;
};

export type ExtractedEngineeringSpecification = {
  chains: ExtractedEngineeringChain[];
  domain: string;
  interfaceType: string;
  communicationSystems: string[];
  communicationSystemCounts: Record<string, number>;
  networkArchitecture: NetworkArchitectureMode;
  targetCounts: EngineeringTargetCounts;
};

const INTELLIGENT_DEVICE_TYPES = new Set([
  "ECU",
  "Gateway",
  "PLC",
  "RobotController",
  "EmbeddedController",
  "IndustrialPC",
  "FlightComputer",
  "BatteryManagementSystem",
  "EnergyController",
  "BuildingController",
]);

function requiresCompleteSignalModel(chain: ExtractedEngineeringChain) {
  if (INTELLIGENT_DEVICE_TYPES.has(chain.device_type)) return true;
  return /camera|kamera|vision|radar|lidar|scanner|ultrasonic|advanced[_ -]?imu/i.test(chain.hardware_name);
}

function companionSignal(
  chain: ExtractedEngineeringChain,
  suffix: string,
  overrides: Partial<ExtractedEngineeringChain>,
): ExtractedEngineeringChain {
  const base = identifier(chain.hardware_name);
  return {
    ...chain,
    signal_name: `${base}${suffix}`,
    signal_display_name: `${base}${suffix}`,
    start_bit: 0,
    ...overrides,
    configuration: {
      ...(chain.configuration ?? {}),
      generation_role: suffix.toUpperCase(),
    },
  };
}

/**
 * Class 3/4 devices need an inspectable minimum model instead of a single
 * placeholder signal. Message packing assigns the final offsets and DLC.
 */
export function expandEngineeringSignalModel(chains: ExtractedEngineeringChain[]) {
  return chains.flatMap((chain) => {
    if (!requiresCompleteSignalModel(chain)) return [chain];
    const candidates = [
      chain,
      companionSignal(chain, "Status", {
        length_bits: 4,
        data_type: "unsigned",
        factor: 1,
        offset_value: 0,
        unit: "code",
        min_value: 0,
        max_value: 15,
        semantic: { semantic_type: "STATE", meaning: "Betriebszustand" },
        data: {
          enum_values: { OFF: 0, INIT: 1, READY: 2, ACTIVE: 3, DEGRADED: 4, ERROR: 5 },
          default_value: "OFF",
          invalid_value: 15,
          reserved_values: [6, 7, 8, 9, 10, 11, 12, 13, 14],
        },
      }),
      companionSignal(chain, "Health", {
        length_bits: 3,
        data_type: "unsigned",
        factor: 1,
        offset_value: 0,
        unit: "code",
        min_value: 0,
        max_value: 7,
        semantic: { semantic_type: "ENUM", meaning: "Diagnosezustand" },
        data: {
          enum_values: { OK: 0, WARNING: 1, DEGRADED: 2, FAILED: 3 },
          default_value: "OK",
          invalid_value: 7,
          reserved_values: [4, 5, 6],
        },
      }),
      companionSignal(chain, "Quality", {
        length_bits: 8,
        data_type: "unsigned",
        factor: 0.5,
        offset_value: 0,
        unit: "%",
        min_value: 0,
        max_value: 100,
        semantic: { semantic_type: "NUMERIC", meaning: "Datenqualitaet" },
      }),
      companionSignal(chain, "AliveCounter", {
        length_bits: 4,
        data_type: "unsigned",
        factor: 1,
        offset_value: 0,
        unit: "count",
        min_value: 0,
        max_value: 15,
        semantic: { semantic_type: "COUNTER", meaning: "Lebendzaehler" },
      }),
      companionSignal(chain, "Mode", {
        length_bits: 4,
        data_type: "unsigned",
        factor: 1,
        offset_value: 0,
        unit: "code",
        min_value: 0,
        max_value: 15,
        semantic: { semantic_type: "ENUM", meaning: "Betriebsart" },
        data: {
          enum_values: { NORMAL: 0, SERVICE: 1, DIAGNOSTIC: 2, SAFE: 3 },
          default_value: "NORMAL",
          invalid_value: 15,
          reserved_values: [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
        },
      }),
    ];
    const seen = new Set<string>();
    return candidates.filter((candidate) => {
      const key = normalized(candidate.signal_name);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    }).slice(0, 5);
  });
}

export type NetworkArchitectureMode = "sensor_ecu_actuator" | "eva" | "ecu_gateway" | "gateway_ecu_segments" | "gateway_direct" | "hybrid_ai";

export type EngineeringHardwareCounts = {
  sensors: number;
  actuators: number;
  ecus: number;
  gateways: number;
};

export type EngineeringTargetCounts = EngineeringHardwareCounts & {
  explicit: boolean;
};

type ArchitectureTemplate = {
  hardwareName: string;
  deviceType: "SensorController" | "ActuatorController" | "ECU" | "Gateway";
  signalName: string;
  interfaceType: string;
  cycleMs: number;
  unit?: string;
  minValue?: number;
  maxValue?: number;
  factor?: number;
};

type HardwareOccurrence = {
  index: number;
  name: string;
};

function generatedSignalBitLength(input: {
  minValue?: number;
  maxValue?: number;
  factor?: number;
  offsetValue?: number;
  dataType?: "signed" | "unsigned";
}) {
  const min = typeof input.minValue === "number" && Number.isFinite(input.minValue) ? input.minValue : 0;
  const max = typeof input.maxValue === "number" && Number.isFinite(input.maxValue) ? input.maxValue : 255;
  const factor = typeof input.factor === "number" && Number.isFinite(input.factor) && input.factor !== 0 ? input.factor : 1;
  const offset = typeof input.offsetValue === "number" && Number.isFinite(input.offsetValue) ? input.offsetValue : 0;
  const rawValues = [min, max].map((value) => Math.round((value - offset) / factor));
  const rawMin = Math.min(...rawValues);
  const rawMax = Math.max(...rawValues);
  const signed = input.dataType === "signed" || rawMin < 0;
  for (let width = 1; width <= 64; width += 1) {
    if (signed) {
      if (rawMin >= -(2 ** (width - 1)) && rawMax < 2 ** (width - 1)) return width;
    } else if (rawMax < 2 ** width) {
      return width;
    }
  }
  return 64;
}

function generatedMessageDlc(lengthBits: number) {
  return Math.max(1, Math.ceil(Math.max(1, lengthBits) / 8));
}

const CAN_FD_PAYLOAD_CLASSES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64] as const;
const DEFAULT_INTERFACE_TARGET_LOAD_PERCENT = 60;

export function validPayloadBytes(interfaceType: string, requiredBytes: number) {
  const required = Math.max(0, Math.ceil(requiredBytes));
  const technology = normalized(interfaceType);
  if (technology.includes("canfd") || technology.includes("canxl")) {
    const candidate = CAN_FD_PAYLOAD_CLASSES.find((bytes) => bytes >= required);
    return candidate ?? null;
  }
  if (technology === "can" || technology.includes("lin")) return required <= 8 ? Math.max(1, required) : null;
  return Math.max(1, required);
}

function maxPayloadBytes(interfaceType: string) {
  const technology = normalized(interfaceType);
  if (technology.includes("canfd") || technology.includes("canxl")) return 64;
  if (technology === "can" || technology.includes("lin")) return 8;
  if (technology.includes("ethernet") || technology.includes("someip")) return 1400;
  return 64;
}

function estimateMessageLoadPercent(interfaceType: string, payloadBytes: number, cycleMs: number) {
  const technology = normalized(interfaceType);
  const cycleSeconds = Math.max(cycleMs, 1) / 1000;
  if (technology.includes("canfd") || technology.includes("canxl")) {
    const arbitrationBits = Math.ceil(55 * 1.2);
    const dataBits = Math.ceil((payloadBytes * 8 + 28) * 1.15);
    const transmitSeconds = arbitrationBits / 1_000_000 + dataBits / 2_000_000;
    return transmitSeconds / cycleSeconds * 100;
  }
  if (technology === "can") {
    const frameBits = Math.ceil((47 + payloadBytes * 8) * 1.2);
    return (frameBits / 500_000) / cycleSeconds * 100;
  }
  if (technology.includes("lin")) {
    return ((34 + payloadBytes * 10) / 19_200) / cycleSeconds * 100;
  }
  if (technology.includes("ethernet") || technology.includes("someip")) {
    const wireBytes = Math.max(84, payloadBytes + 74);
    return ((wireBytes * 8) / 100_000_000) / cycleSeconds * 100;
  }
  return (((payloadBytes + 24) * 8) / 1_000_000) / cycleSeconds * 100;
}

function messageGroupKey(chain: ExtractedEngineeringChain) {
  const communication = chain.communication ?? {};
  const consumers = Array.isArray(communication.consumers) ? communication.consumers.map(String).sort().join(",") : "";
  return [
    normalized(chain.hardware_name),
    normalized(chain.function_name),
    normalized(chain.interface_type),
    String(chain.cycle_ms),
    String(communication.priority ?? ""),
    consumers,
  ].join("|");
}

function packedMessageName(chain: ExtractedEngineeringChain, index: number) {
  const suffix = index === 0 ? "Data" : `Data${index + 1}`;
  return `${identifier(chain.function_name || chain.hardware_name)}${suffix}`;
}

function packedInterfaceName(chain: ExtractedEngineeringChain, channel: number) {
  return `${identifier(chain.hardware_name)}_${channel + 1}`;
}

export function packEngineeringChains(
  chains: ExtractedEngineeringChain[],
  targetLoadPercent = DEFAULT_INTERFACE_TARGET_LOAD_PERCENT,
) {
  const packed = chains.map((chain) => ({ ...chain }));
  const grouped = new Map<string, ExtractedEngineeringChain[]>();
  for (const chain of packed) {
    const key = messageGroupKey(chain);
    grouped.set(key, [...(grouped.get(key) ?? []), chain]);
  }

  type PackedMessage = {
    name: string;
    interfaceType: string;
    producerKey: string;
    hardwareName: string;
    cycleMs: number;
    usedBits: number;
    dlc: number;
    chains: ExtractedEngineeringChain[];
  };
  const messages: PackedMessage[] = [];

  for (const group of grouped.values()) {
    const ordered = [...group].sort((left, right) => left.signal_name.localeCompare(right.signal_name, "de-DE", { numeric: true, sensitivity: "base" }));
    const groupMessages: PackedMessage[] = [];
    for (const chain of ordered) {
      const maxBits = maxPayloadBytes(chain.interface_type) * 8;
      const signalBits = Math.max(1, chain.length_bits);
      let message = groupMessages.find((candidate) => candidate.usedBits + signalBits <= maxBits);
      if (!message) {
        message = {
          name: packedMessageName(chain, groupMessages.length),
          interfaceType: chain.interface_type,
          producerKey: normalized(chain.hardware_name),
          hardwareName: chain.hardware_name,
          cycleMs: chain.cycle_ms,
          usedBits: 0,
          dlc: 1,
          chains: [],
        };
        groupMessages.push(message);
        messages.push(message);
      }
      chain.message_name = message.name;
      chain.start_bit = message.usedBits;
      message.usedBits += signalBits;
      const dlc = validPayloadBytes(chain.interface_type, Math.ceil(message.usedBits / 8));
      message.dlc = dlc ?? maxPayloadBytes(chain.interface_type);
      message.chains.push(chain);
    }
  }

  const interfaceLoads = new Map<string, number[]>();
  messages.sort((left, right) => (
    left.producerKey.localeCompare(right.producerKey)
    || left.interfaceType.localeCompare(right.interfaceType)
    || left.name.localeCompare(right.name, "de-DE", { numeric: true, sensitivity: "base" })
  ));
  for (const message of messages) {
    const key = `${message.producerKey}|${normalized(message.interfaceType)}`;
    const loads = interfaceLoads.get(key) ?? [];
    const load = estimateMessageLoadPercent(message.interfaceType, message.dlc, message.cycleMs);
    let channel = loads.findIndex((currentLoad) => currentLoad + load <= targetLoadPercent);
    if (channel < 0) {
      channel = loads.length;
      loads.push(0);
    }
    loads[channel] += load;
    interfaceLoads.set(key, loads);
    const interfaceName = packedInterfaceName(message.chains[0], channel);
    const messageIdBase = 0x180 + messages.indexOf(message);
    for (const chain of message.chains) {
      chain.interface_name = interfaceName;
      chain.dlc = message.dlc;
      chain.message_id_hex = `0x${messageIdBase.toString(16).toUpperCase()}`;
      chain.configuration = {
        ...chain.configuration,
        packing_policy: "MINIMUM_VALID_SIZE",
        payload_used_bits: message.usedBits,
        payload_capacity_bits: message.dlc * 8,
        payload_free_bits: message.dlc * 8 - message.usedBits,
        payload_utilization: Number((message.usedBits / (message.dlc * 8)).toFixed(4)),
        interface_allocation_policy: "REUSE_EXISTING_CAPACITY_FIRST",
        projected_message_load_percent: Number(load.toFixed(4)),
        projected_interface_load_percent: Number(loads[channel].toFixed(4)),
      };
    }
  }

  return packed;
}

type SignalArchitectureInput = {
  signalName: string;
  hardwareName: string;
  interfaceType: string;
  cycleMs: number;
  dataType: "signed" | "unsigned";
  lengthBits: number;
  startBit: number;
  byteOrder: "little_endian";
  factor: number;
  offset: number;
  unit?: string;
  minValue?: number;
  maxValue?: number;
};

function generatedSignalSemanticType(input: SignalArchitectureInput) {
  const key = normalized(`${input.signalName} ${input.unit ?? ""}`);
  if ((input.lengthBits === 1 || (input.minValue === 0 && input.maxValue === 1)) && /status|flag|schaltausgang|stellglied|aktiv|enable|boolean/.test(key)) {
    return "BOOLEAN";
  }
  if ((input.lengthBits === 1 || (input.minValue === 0 && input.maxValue === 1)) && /erkannt|detected|presence|praesenz/.test(key)) {
    return "BOOLEAN";
  }
  if (/status|state|mode|zustand|diagnose|fehler|code/.test(key) || input.unit === "code") return "STATE";
  return "NUMERIC";
}

function stateDomain(input: SignalArchitectureInput) {
  const gateway = /gateway/.test(normalized(input.signalName));
  const enumValues = gateway
    ? { OK: 0, DEGRADED: 1, ROUTING_LIMITED: 2, ERROR: 3 }
    : { OK: 0, WARNING: 1, ERROR: 2, NOT_AVAILABLE: 3 };
  return {
    enum_values: enumValues,
    allowed_values: Object.keys(enumValues),
    reserved_values: [4, 5, 6, 7],
    invalid_values: [15],
    default_value: "OK",
    resolution: 1,
  };
}

function signalArchitectureMetadata(input: SignalArchitectureInput) {
  const semanticType = generatedSignalSemanticType(input);
  const isNumeric = semanticType === "NUMERIC";
  const valueDomain = semanticType === "BOOLEAN"
    ? {
        minimum: 0,
        maximum: 1,
        resolution: 1,
        allowed_values: [false, true],
        enum_values: { FALSE: 0, TRUE: 1 },
        invalid_values: [],
        reserved_values: [],
        default_value: false,
      }
    : semanticType === "STATE"
      ? stateDomain(input)
      : {
          minimum: input.minValue ?? null,
          maximum: input.maxValue ?? null,
          resolution: input.factor,
          allowed_values: [],
          enum_values: {},
          invalid_values: input.maxValue == null ? [] : [input.maxValue + input.factor],
          reserved_values: [],
          default_value: input.minValue != null && input.maxValue != null && input.minValue <= 0 && input.maxValue >= 0 ? 0 : input.minValue ?? null,
        };
  return {
    semantic: {
      semantic_type: semanticType,
      quantity: input.signalName,
      category: normalized(input.hardwareName),
      meaning: `${input.signalName} beschreibt ${input.hardwareName}.`,
      unit: input.unit ?? (isNumeric ? "" : "not_applicable"),
      generated_by: "engineering-specification-parser-v2",
      assumptions: isNumeric ? [] : ["Diskretes Signal wurde als explizite Value-Domain modelliert."],
    },
    data: valueDomain,
    configuration: {
      raw_datatype: input.dataType,
      bit_length: input.lengthBits,
      signed: input.dataType === "signed",
      factor: input.factor,
      offset: input.offset,
      endianness: input.byteOrder,
      start_bit: input.startBit,
      encoding_type: isNumeric ? "linear" : "coded",
      coding_rule: "MEANING_VALUE_DOMAIN_ENCODING_PACKING_TRANSPORT",
    },
    communication: {
      producer: input.hardwareName,
      consumers: [],
      cycle_time_ms: input.cycleMs,
      update_type: input.cycleMs <= 20 ? "cyclic_fast" : "cyclic",
    },
    quality: {
      confidence: isNumeric ? 0.92 : 0.86,
      semantic_complete: true,
      value_domain_complete: semanticType !== "NUMERIC" || (input.minValue != null && input.maxValue != null),
      encoding_complete: true,
      packing_complete: true,
      validation_status: "proposal",
    },
    protocol_bindings: [{
      protocol: input.interfaceType,
      binding_state: "proposal",
      signal_id: input.signalName,
    }],
  };
}

const INLINE_HARDWARE_PATTERN = /\b[\p{L}\d][\p{L}\d_-]*(?:sensor|actuator|aktuator|aktor|ecu|gateway|plc|controller|steuergeraet|steuergerät)\b/giu;
const GENERIC_INLINE_HARDWARE_LABELS = new Set([
  "sensor",
  "actuator", "aktuator", "aktor",
  "ecu",
  "gateway",
  "plc",
  "controller",
  "steuergeraet",
]);

const GENERIC_HARDWARE_LABELS = new Set([
  "hardware",
  "hardware objekte",
  "hardware objekt",
  "sensor",
  "sensors",
  "sensoren",
  "actuator", "actuators", "aktuator", "aktuatoren", "aktor", "aktoren",
  "ecu",
  "ecus",
  "gateway",
  "gateways",
  "plc",
  "controller",
  "steuergeraet",
  "funktion",
  "funktions",
  "funktions ecu",
  "funktions ecus",
]);

const PARAMETER_LABEL_PATTERN =
  /^(bereich|messbereich|signal|aufloesung|auflösung|schrittweite|sollwert|grenzwerte?|kommunikationsprotokoll|kreistellen|warnhinweis|mindest|maximum|minimum|parameter|technische parameter|funktions parameter|verwendung|aufgaben|eingänge?|eingaenge?|ausgänge?|ausgaenge?|mögliche werte|moegliche werte|beispielregeln?)/i;

const PROSE_HARDWARE_LABEL_PATTERN =
  /^(verwendung|verarbeitet|verarbeitung|kommunikation|verbindung|beispiel|beispielsweise|aufgaben?|eingänge?|eingaenge?|ausgänge?|ausgaenge?)\b/i;

const DIRECT_CREATION_PATTERN =
  /\b(lege|leg|erstelle|erstell\w*|erzeuge|generiere|registriere|anlegen|aufbauen)\b/i;

const COUNT_WORDS: Record<string, number> = {
  ein: 1,
  eine: 1,
  einem: 1,
  einen: 1,
  einer: 1,
  eins: 1,
  zwei: 2,
  drei: 3,
  vier: 4,
  fuenf: 5,
  funf: 5,
  sechs: 6,
  sieben: 7,
  acht: 8,
  neun: 9,
  zehn: 10,
};

const COUNT_TOKEN = "(\\d+|ein|eine|einem|einen|einer|eins|zwei|drei|vier|fuenf|funf|sechs|sieben|acht|neun|zehn)";

export function extractNetworkArchitectureMode(text: string): NetworkArchitectureMode {
  const explicit = text.match(/Netzarchitektur-ID:\s*(sensor_ecu_actuator|eva|ecu_gateway|gateway_ecu_segments|gateway_direct|hybrid_ai)\b/i)?.[1]
    ?.toLowerCase() as NetworkArchitectureMode | undefined;
  if (explicit) return explicit;
  if (/Variante\s*0|Sensor\s*[-–>]+\s*ECU\s*[-–>]+\s*Aktor|Sensor\s+ECU\s+Aktor/i.test(text)) return "sensor_ecu_actuator";
  if (/Variante\s*4|Gateway-Segmente|Gateway.*(?:bis\s+zu\s+)?6\s+ECU|6\s+ECU.*Gateway/i.test(text)) return "gateway_ecu_segments";
  if (/KI-Kombination|Kombination\s+aus\s+Variante\s*2\s*(?:\+|und)\s*3/i.test(text)) return "hybrid_ai";
  if (/Variante\s*3|Gateway-direkt/i.test(text)) return "gateway_direct";
  if (/Variante\s*2|ECU-vermittelt/i.test(text)) return "ecu_gateway";
  if (/Variante\s*1|einfaches?\s+EVA/i.test(text)) return "eva";
  return "gateway_direct";
}

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

function countValue(value: string) {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : COUNT_WORDS[value] ?? 0;
}

function specificationBody(text: string) {
  const marker = /Konkrete Aufgabe des Nutzers[^\r\n]*:/i.exec(text);
  if (!marker) return text;
  const body = text.slice(marker.index + marker[0].length);
  const end = body.search(/\r?\n\r?\n(?:Verbindliche Kanonisierung bei der Projektanlage:|Starte jetzt)/i);
  return end >= 0 ? body.slice(0, end) : body;
}

function requestedCount(text: string, nounPattern: string, modifierPattern = "") {
  const modifiers = modifierPattern ? `(?:(?:${modifierPattern})\\s+){0,2}` : "";
  const countBeforePattern = new RegExp(`\\b${COUNT_TOKEN}\\s+${modifiers}${nounPattern}\\b`, "g");
  const countAfterPattern = new RegExp(`\\b${modifiers}${nounPattern}\\b\\s*(?:anzahl\\s*)?(?::|=|-)?\\s*${COUNT_TOKEN}\\b`, "g");
  // Numbered UI choices and adjacent lines are not hardware quantity statements.
  return text.split(/\r?\n/).reduce((maximum, line) => {
    const source = normalized(line
      .replace(/^\s*#{1,6}\s+/, "")
      .replace(/^\s*\d+[.)]\s+/, "")
      .replace(/\bVariante\s+\d+(?:\s*(?:\+|und)\s*\d+)?/gi, "Variante"));
    const before = [...source.matchAll(countBeforePattern)].reduce((count, match) => Math.max(count, countValue(match[1] ?? "")), maximum);
    return [...source.matchAll(countAfterPattern)].reduce((count, match) => Math.max(count, countValue(match[1] ?? "")), before);
  }, 0);
}

export function extractEngineeringTargetCounts(text: string): EngineeringTargetCounts {
  const body = specificationBody(text);
  const sensors = requestedCount(body, "sensor(?:en|s)?", "technische|physikalische|logische|fahrzeugrelevante");
  const actuators = requestedCount(body, "(?:actuator(?:s)?|aktuator(?:en)?|aktor(?:en)?)", "technische|physikalische|logische|einfache");
  const ecus = requestedCount(body, "ecu(?:s)?", "funktions|zentrale|typische|weitere");
  const gateways = requestedCount(body, "gateway(?:s)?", "zentralen|zentrales|zentraler|zentrale|einziges|einzigen");
  return {
    sensors,
    actuators,
    ecus,
    gateways,
    explicit: sensors > 0 || actuators > 0 || ecus > 0 || gateways > 0,
  };
}

function chainCounts(chains: ExtractedEngineeringChain[]) {
  return chains.reduce(
    (counts, chain) => {
      if (chain.device_type === "SensorController") counts.sensors += 1;
      else if (chain.device_type === "ActuatorController") counts.actuators += 1;
      else if (chain.device_type === "Gateway") counts.gateways += 1;
      else if (chain.device_type === "ECU") counts.ecus += 1;
      return counts;
    },
    { sensors: 0, actuators: 0, ecus: 0, gateways: 0 },
  );
}

function systemInterfaceType(name: string, domain: string) {
  const key = normalized(name);
  if (domain === "industrial_automation") {
    if (/motion|antrieb|servo|roboter|foerder|safety|sicher/.test(key)) return "EtherCAT";
    if (/hmi|prozess|produktions|condition|qualitaet|pruef/.test(key)) return "ProfiNET";
    return "ModbusTCP";
  }
  if (domain === "embedded_systems") {
    if (/display|storage|pcie|edge|usb/.test(key)) return "USB";
    if (/sensor|clock|secure|i2c/.test(key)) return "I2C";
    if (/motor|power|spi/.test(key)) return "SPI";
    return "UART";
  }
  if (domain === "aerospace") {
    if (/display|mission|weather|payload|health|redundancy/.test(key)) return "Ethernet";
    if (/flight|engine|landing|autopilot|actuator|sensor/.test(key)) return "MIL_STD_1553";
    return "ARINC";
  }
  if (domain === "rail") {
    if (/passenger|wayside|event|energy/.test(key)) return "Ethernet";
    return "CAN";
  }
  if (domain === "marine") {
    if (/radar|navigation|communication|dynamic|alarm/.test(key)) return "Ethernet";
    return "CAN";
  }
  if (domain === "building_automation") {
    if (/leittechnik|sicherheits|brand|park/.test(key)) return "Ethernet";
    return "ModbusTCP";
  }
  if (domain === "energy") {
    if (/microgrid|mess|last|lade|netz/.test(key)) return "Ethernet";
    return "ModbusTCP";
  }
  if (domain === "robotics_ros") {
    if (/perception|localization|mapping|vision|task|interface/.test(key)) return "Ethernet";
    return "CAN";
  }
  if (domain === "generic_networking") return "Ethernet";
  if (/infotainment|telematik|diagnose|fahrerassistenz|radar|kamera|zentralrechner|konnektivitaet/i.test(name)) {
    return "Ethernet";
  }
  if (/tuer|sitz|licht|keyless|wischer|schiebedach|heckklappe|soundsystem|headup/i.test(name)) {
    return "LIN";
  }
  return "CAN_FD";
}

function architectureTemplates(domain: string): ArchitectureTemplate[] {
  const profile = industryTemplateProfile(domain);
  const sensorTemplates = profile.sensorTemplates.map((template) => ({
    hardwareName: template.hardwareName,
    deviceType: "SensorController" as const,
    signalName: template.signalName,
    interfaceType: /camera|kamera|vision|radar|lidar|scanner|ultrasonic/i.test(template.hardwareName)
      ? template.interfaceType
      : "LIN",
    cycleMs: template.cycleMs,
    unit: template.unit,
    minValue: template.minValue,
    maxValue: template.maxValue,
    factor: template.factor,
  }));
  const ecus = profile.systemVariants.map((name) => {
    const interfaceType = systemInterfaceType(name, domain);
    return {
    hardwareName: name,
    deviceType: "ECU" as const,
    signalName: `${identifier(baseName(name))}Status`,
      interfaceType,
      cycleMs: interfaceType === "LIN" ? 100 : interfaceType === "Ethernet" ? 20 : 10,
    unit: "code",
    minValue: 0,
    maxValue: 255,
    factor: 1,
    };
  });
  const actuators = profile.systemVariants.flatMap((name) => ["Stellglied", "Schaltausgang"].map((kind) => {
    const interfaceType = "LIN";
    return {
    hardwareName: `${baseName(name)}${kind}Actuator`,
    deviceType: "ActuatorController" as const,
    signalName: `${identifier(baseName(name))}${kind}Status`,
      interfaceType,
      cycleMs: interfaceType === "LIN" ? 100 : 20,
    unit: kind === "Stellglied" ? "%" : "code",
    minValue: 0,
    maxValue: kind === "Stellglied" ? 100 : 1,
    factor: kind === "Stellglied" ? 0.1 : 1,
    };
  }));
  return [
    ...sensorTemplates,
    ...actuators,
    ...ecus,
    {
      hardwareName: profile.gatewayName ?? "System-Gateway",
      deviceType: "Gateway",
      signalName: "GatewayStatus",
      interfaceType: "Ethernet",
      cycleMs: 20,
      unit: "code",
      minValue: 0,
      maxValue: 255,
      factor: 1,
    },
  ];
}

function chainFromTemplate(template: ArchitectureTemplate, index: number, domain: string): ExtractedEngineeringChain {
  const hardwareId = identifier(template.hardwareName);
  const industryLabel = industryTemplateLabel(domain);
  const dataType = (template.minValue ?? 0) < 0 ? "signed" : "unsigned";
  const lengthBits = generatedSignalBitLength({
    minValue: template.minValue,
    maxValue: template.maxValue,
    factor: template.factor,
    dataType,
  });
  const functionSuffix = template.deviceType === "SensorController"
    ? "Erfassung"
    : template.deviceType === "Gateway"
      ? "Kommunikation"
      : "Steuerung";
  return {
    hardware_name: template.hardwareName,
    hardware_description: `Aus dem geforderten ${industryLabel}-Skalierungsziel abgeleiteter Systemrahmen mit Rolle ${template.deviceType}.`,
    device_type: template.deviceType,
    function_name: `${hardwareId}_${functionSuffix}`,
    function_description: `Fachfunktion fuer ${template.hardwareName} im skalierten ${industryLabel}-Musterprojekt.`,
    interface_name: `${hardwareId}_${template.interfaceType}`,
    interface_type: template.interfaceType,
    message_name: `${hardwareId}Data`,
    message_id_hex: `0x${(0x180 + index).toString(16).toUpperCase()}`,
    direction: "tx",
    cycle_ms: template.cycleMs,
    dlc: generatedMessageDlc(lengthBits),
    signal_name: template.signalName,
    signal_display_name: template.signalName,
    start_bit: 0,
    length_bits: lengthBits,
    byte_order: "little_endian",
    data_type: dataType,
    factor: template.factor ?? 1,
    offset_value: 0,
    unit: template.unit,
    min_value: template.minValue,
    max_value: template.maxValue,
    ...signalArchitectureMetadata({
      signalName: template.signalName,
      hardwareName: template.hardwareName,
      interfaceType: template.interfaceType,
      cycleMs: template.cycleMs,
      dataType,
      lengthBits,
      startBit: 0,
      byteOrder: "little_endian",
      factor: template.factor ?? 1,
      offset: 0,
      unit: template.unit,
      minValue: template.minValue,
      maxValue: template.maxValue,
    }),
    domain,
  };
}

function canonicalSystemName(name: string, domain: string) {
  const profile = industryTemplateProfile(domain);
  const sourceName = normalizeHardwareName(name);
  const sourceKey = normalized(sourceName);
  const ignored = new Set((profile.ignoredSystemNames ?? []).map((item) => normalized(normalizeHardwareName(item))));
  if (ignored.has(sourceKey)) return null;
  const alias = Object.entries(profile.systemAliases ?? {}).find(
    ([candidate]) => normalized(normalizeHardwareName(candidate)) === sourceKey,
  );
  return alias?.[1] ?? sourceName;
}

function canonicalizeRecognizedSystems(chains: ExtractedEngineeringChain[], domain: string) {
  const canonicalized = chains.flatMap((chain) => {
    if (chain.device_type !== "ECU") return [chain];
    const canonicalName = canonicalSystemName(chain.hardware_name, domain);
    if (!canonicalName) return [];
    if (canonicalName === chain.hardware_name) return [chain];
    const oldIdentifier = identifier(chain.hardware_name);
    const newIdentifier = identifier(canonicalName);
    const replaceIdentifier = (value: string) => value.startsWith(oldIdentifier)
      ? `${newIdentifier}${value.slice(oldIdentifier.length)}`
      : value;
    return [{
      ...chain,
      hardware_name: canonicalName,
      function_name: replaceIdentifier(chain.function_name),
      interface_name: `${newIdentifier}_${chain.interface_type}`,
      message_name: replaceIdentifier(chain.message_name),
      signal_name: replaceIdentifier(chain.signal_name),
      signal_display_name: replaceIdentifier(chain.signal_display_name),
      semantic: {
        ...(chain.semantic ?? {}),
        category: normalized(canonicalName),
      },
      communication: {
        ...(chain.communication ?? {}),
        producer: canonicalName,
      },
    }];
  });

  const byIdentity = new Map<string, ExtractedEngineeringChain>();
  canonicalized.forEach((chain) => {
    const key = `${chain.device_type}:${normalized(normalizeHardwareName(chain.hardware_name))}`;
    const current = byIdentity.get(key);
    if (!current) {
      byIdentity.set(key, chain);
      return;
    }
    const quality = (candidate: ExtractedEngineeringChain) => {
      const descriptionLength = candidate.hardware_description.trim().length;
      return (descriptionLength > 0 && descriptionLength <= 320 ? 1000 : 0) - descriptionLength;
    };
    if (quality(chain) > quality(current)) byIdentity.set(key, chain);
  });
  return [...byIdentity.values()];
}

function expandArchitectureChains(
  recognizedChains: ExtractedEngineeringChain[],
  requested: EngineeringTargetCounts,
  domain: string,
  communicationSystems: string[],
  overrides: Partial<EngineeringHardwareCounts> = {},
) {
  const canonicalRecognizedChains = canonicalizeRecognizedSystems(recognizedChains, domain);
  const recognizedCounts = chainCounts(canonicalRecognizedChains);
  const targets: EngineeringTargetCounts = {
    sensors: requested.sensors || recognizedCounts.sensors,
    actuators: requested.actuators || recognizedCounts.actuators,
    ecus: requested.ecus || recognizedCounts.ecus,
    gateways: requested.gateways || recognizedCounts.gateways,
    ...overrides,
    explicit: requested.explicit || Object.keys(overrides).length > 0,
  };
  const retainedCounts = { sensors: 0, actuators: 0, ecus: 0, gateways: 0 };
  const chains = targets.explicit
    ? canonicalRecognizedChains.filter((chain) => {
      const category = chain.device_type === "SensorController"
        ? "sensors"
        : chain.device_type === "ActuatorController" ? "actuators"
        : chain.device_type === "Gateway"
          ? "gateways"
          : chain.device_type === "ECU"
            ? "ecus"
            : null;
      if (!category) return true;
      if (retainedCounts[category] >= targets[category]) return false;
      retainedCounts[category] += 1;
      return true;
    })
    : [...canonicalRecognizedChains];
  const names = new Set(chains.map((chain) => normalized(normalizeHardwareName(chain.hardware_name))));
  if (!targets.explicit) return { chains, targets };

  const templates = architectureTemplates(domain);
  const targetFor = (deviceType: ArchitectureTemplate["deviceType"]) => (
    deviceType === "SensorController" ? targets.sensors : deviceType === "ActuatorController" ? targets.actuators : deviceType === "Gateway" ? targets.gateways : targets.ecus
  );
  for (const template of templates) {
    const current = chainCounts(chains);
    const currentCount = template.deviceType === "SensorController"
      ? current.sensors
      : template.deviceType === "ActuatorController" ? current.actuators
      : template.deviceType === "Gateway"
        ? current.gateways
        : current.ecus;
    if (currentCount >= targetFor(template.deviceType)) continue;
    const key = normalized(normalizeHardwareName(template.hardwareName));
    if (names.has(key)) continue;
    const allowedInterfaceType = communicationSystems.some((system) => communicationSystemAllowsTemplateInterface(system, template.interfaceType))
      ? template.interfaceType
      : communicationSystems.length
        ? communicationSystems[chains.length % communicationSystems.length]
        : undefined;
    chains.push(chainFromTemplate(
      allowedInterfaceType ? { ...template, interfaceType: allowedInterfaceType } : template,
      chains.length,
      domain,
    ));
    names.add(key);
  }
  // Additional instances keep the same technical template and a stable unique name.
  for (const deviceType of ["SensorController", "ActuatorController", "ECU", "Gateway"] as const) {
    const candidates = templates.filter((template) => template.deviceType === deviceType);
    let current = chains.filter((chain) => chain.device_type === deviceType).length;
    for (let instance = 0; current < targetFor(deviceType); instance += 1) {
      const template = candidates[instance % candidates.length];
      const hardwareName = `${template.hardwareName}-${2 + Math.floor(instance / candidates.length)}`;
      if (names.has(normalized(normalizeHardwareName(hardwareName)))) continue;
      const interfaceType = communicationSystems.some((system) => communicationSystemAllowsTemplateInterface(system, template.interfaceType)) || !communicationSystems.length
        ? template.interfaceType : communicationSystems[instance % communicationSystems.length];
      chains.push(chainFromTemplate({ ...template, hardwareName, interfaceType }, chains.length, domain));
      names.add(normalized(normalizeHardwareName(hardwareName)));
      current += 1;
    }
  }
  return { chains, targets };
}

function communicationSystemAllowsTemplateInterface(system: string, interfaceType: string) {
  return system === interfaceType || (system === "SOME_IP" && interfaceType === "Ethernet");
}

function headingLabel(line: string) {
  const bold = line.match(/^\s*(?:(?:[-*]|\d+\.)\s+)?\*\*(.+?)\*\*(?:\s*:|\s*$)/)?.[1];
  if (bold) return cleanLabel(bold);
  const bullet = line.match(/^\s*(?:[-*]|\d+\.)\s+(.+?)\s*$/)?.[1];
  if (!bullet) return "";
  // Compact specifications often put type and parameters on the same bullet.
  // Only the leading label identifies the hardware participant.
  return cleanLabel(bullet.split(/\s*[:,]\s*/, 1)[0] ?? "");
}

function isCountedHardwareGroup(value: string) {
  const key = normalized(value);
  return new RegExp(
    `^${COUNT_TOKEN}\\s+(?:(?:technische|physikalische|logische|fahrzeugrelevante|funktions|zentrale|zentralen|zentrales|zentraler|typische|weitere|einziges|einzigen)\\s+){0,2}(?:sensor(?:en|s)?|actuator(?:s)?|aktuator(?:en)?|aktor(?:en)?|ecu(?:s)?|gateway(?:s)?)$`,
  ).test(key);
}

function hardwareName(label: string) {
  const rawName = cleanLabel(label);
  const exampleName = rawName.replace(/^(?:beispiel|beispielsweise)\s+/i, "").trim();
  const name = exampleName && exampleName !== rawName && /\b[\p{L}\d][\p{L}\d_-]*(?:sensor|actuator|aktuator|aktor|ecu|gateway|plc|controller|steuergeraet|steuergerät)\b/iu.test(exampleName)
    ? exampleName
    : rawName;
  const key = normalized(name);
  if (!key || GENERIC_HARDWARE_LABELS.has(key)) return "";
  if (PROSE_HARDWARE_LABEL_PATTERN.test(key)) return "";
  const typeMentions = key.match(/\b(?:sensor(?:en|s)?|actuator(?:s)?|aktuator(?:en)?|aktor(?:en)?|ecu(?:s)?|gateway(?:s)?|plc(?:s)?|controller(?:s)?|steuergeraet(?:e)?)\b/g) ?? [];
  const countedGroup = isCountedHardwareGroup(name);
  if (typeMentions.length > 1 || countedGroup) return "";
  return /(?:sensor|actuator|aktuator|aktor|ecu|gateway|plc|controller|steuergeraet)$/i.test(key.replace(/\s+/g, ""))
    ? name
    : "";
}

function inlineHardwareNames(line: string) {
  if (isCountedHardwareGroup(cleanLabel(line))) return [];
  const names = line.match(INLINE_HARDWARE_PATTERN) ?? [];
  return names
    .map((name) => cleanLabel(name))
    .filter((name) => !GENERIC_INLINE_HARDWARE_LABELS.has(normalized(name)))
    .filter((name) => Boolean(hardwareName(name)));
}

function naturalLanguageHardwareNames(line: string) {
  const key = normalized(line);
  if (!DIRECT_CREATION_PATTERN.test(key)) return [];
  if (!(/\b(?:hardware|knoten|konten|ecu|gateway|sensor|aktor|aktuator)\b/.test(key) || /kamera|camera|radar|lidar/.test(key))) return [];
  const names = [...line.matchAll(/\b([\p{L}\d_-]*(?:kamera|camera|radar|lidar)[\p{L}\d_-]*)\b/giu)]
    .map((match) => cleanLabel(match[1] ?? ""))
    .filter(Boolean);
  return [...new Map(names.map((name) => [normalized(name), name])).values()];
}

function impliedHardwareNames(line: string) {
  const key = normalized(line);
  const names: string[] = [];
  if (/\b(?:sensor|sensoren)\b/.test(key) && /\bmotorstrom\b/.test(key)) {
    names.push("Motorstromsensor");
  }
  if (/\bgateway\b/.test(key) && /\b(?:verbindet|koppelt|vermittelt|uebertraegt|ueberbrueckt)\b/.test(key)) {
    names.push("System-Gateway");
  }
  return names;
}

function deviceType(name: string) {
  const key = normalized(name);
  if (key.includes("gateway")) return "Gateway";
  if (key.includes("sensor") || key.includes("kamera") || key.includes("camera") || key.includes("radar") || key.includes("lidar")) return "SensorController";
  if (/actuator|aktuator|aktor/.test(key)) return "ActuatorController";
  if (key.includes("plc")) return "PLC";
  if (key.includes("controller")) return "GenericDevice";
  return "ECU";
}

function protocolFrom(text: string) {
  const key = normalized(text);
  if (/\blin\b/.test(key)) return "LIN";
  if (key.includes("can fd") || key.includes("canfd")) return "CAN_FD";
  if (/\bsome ip\b|\bsomeip\b/.test(key)) return "Ethernet";
  if (key.includes("arinc 429") || key.includes("arinc429")) return "ARINC";
  if (key.includes("mil std 1553") || key.includes("milstd1553")) return "MIL_STD_1553";
  if (key.includes("ethercat")) return "EtherCAT";
  if (key.includes("profinet")) return "ProfiNET";
  if (key.includes("automotive ethernet") || key.includes("ethernet")) return "Ethernet";
  if (key.includes("modbus tcp")) return "ModbusTCP";
  if (key.includes("modbus rtu")) return "ModbusRTU";
  if (/\bspi\b/.test(key)) return "SPI";
  if (/\bi2c\b/.test(key)) return "I2C";
  if (/\buart\b/.test(key)) return "UART";
  if (/\b(?:usb|pcie|rs485|rs232)\b/.test(key)) return key.match(/\b(?:usb|pcie|rs485|rs232)\b/)?.[0].toUpperCase() ?? "Other";
  if (key.includes("opc ua")) return "OPCUA";
  return "CAN";
}

export function extractCommunicationSystems(text: string) {
  const key = normalized(text);
  const systems: string[] = [];
  if (/\blin\b/.test(key)) systems.push("LIN");
  if (/\bcan fd\b|\bcanfd\b/.test(key)) systems.push("CAN_FD");
  else if (/\bcan\b/.test(key)) systems.push("CAN");
  if (/\bautomotive ethernet\b|\bethernet\b/.test(key)) systems.push("Ethernet");
  if (/\bsome ip\b|\bsomeip\b/.test(key)) systems.push("SOME_IP");
  if (/\barinc 429\b|\barinc429\b/.test(key)) systems.push("ARINC");
  if (/\bmil std 1553\b|\bmilstd1553\b/.test(key)) systems.push("MIL_STD_1553");
  if (/\bethercat\b/.test(key)) systems.push("EtherCAT");
  if (/\bprofinet\b/.test(key)) systems.push("ProfiNET");
  if (/\bmodbus tcp\b/.test(key)) systems.push("ModbusTCP");
  if (/\bmodbus rtu\b|\bmodbusrtu\b/.test(key)) systems.push("ModbusRTU");
  if (/\bspi\b/.test(key)) systems.push("SPI");
  if (/\bi2c\b/.test(key)) systems.push("I2C");
  if (/\buart\b/.test(key)) systems.push("UART");
  if (/\busb\b/.test(key)) systems.push("USB");
  if (/\bpcie\b/.test(key)) systems.push("PCIe");
  if (/\brs485\b/.test(key)) systems.push("RS485");
  if (/\brs232\b/.test(key)) systems.push("RS232");
  if (/\bopc ua\b/.test(key)) systems.push("OPCUA");
  return [...new Set(systems)];
}

function canonicalCommunicationSystem(value: string) {
  const key = normalized(value);
  const compact = key.replace(/\s+/g, "");
  if (/\blin\b/.test(key) || compact === "lin") return "LIN";
  if (/\bcan fd\b|\bcanfd\b/.test(key) || compact === "canfd") return "CAN_FD";
  if (/\bautomotive ethernet\b|\bethernet\b/.test(key) || compact === "eth") return "Ethernet";
  if (/\bsome ip\b/.test(key) || compact === "someip") return "SOME_IP";
  if (/\barinc 429\b/.test(key) || compact === "arinc429") return "ARINC";
  if (/\bmil std 1553\b/.test(key) || compact === "milstd1553") return "MIL_STD_1553";
  if (/\bethercat\b/.test(key)) return "EtherCAT";
  if (/\bprofinet\b/.test(key)) return "ProfiNET";
  if (/\bmodbus tcp\b/.test(key) || compact === "modbustcp") return "ModbusTCP";
  if (/\bmodbus rtu\b/.test(key) || compact === "modbusrtu") return "ModbusRTU";
  if (/\bspi\b/.test(key)) return "SPI";
  if (/\bi2c\b/.test(key)) return "I2C";
  if (/\buart\b/.test(key)) return "UART";
  if (/\busb\b/.test(key)) return "USB";
  if (/\bpcie\b/.test(key)) return "PCIe";
  if (/\brs485\b/.test(key)) return "RS485";
  if (/\brs232\b/.test(key)) return "RS232";
  if (/\bopc ua\b/.test(key) || compact === "opcua") return "OPCUA";
  if (/\bcan\b/.test(key)) return "CAN";
  return "";
}

const COMMUNICATION_SYSTEM_PATTERN = "(?:automotive\\s+ethernet|ethernet|some\\s*ip|someip|can\\s*fd|canfd|can|lin|arinc\\s*429|arinc429|mil\\s*std\\s*1553|milstd1553|ethercat|profinet|modbus\\s*rtu|modbusrtu|modbus\\s*tcp|spi|i2c|uart|usb|pcie|rs485|rs232|opc\\s*ua)";

function looksLikeBitrateSuffix(value: string) {
  return /^\s*(?:k?bit|m?bit|kbps|mbps|baud|bd|ms|byte|bytes|b)\b/i.test(value);
}

export function extractCommunicationSystemCounts(text: string): Record<string, number> {
  const counts: Record<string, number> = {};
  const countBeforePattern = new RegExp(`\\b${COUNT_TOKEN}\\s*(?:x\\s*)?${COMMUNICATION_SYSTEM_PATTERN}\\b`, "gi");
  const countAfterPattern = new RegExp(`\\b${COMMUNICATION_SYSTEM_PATTERN}\\b\\s*(?:bus(?:se)?|netz(?:e)?|segmente?|anzahl)?\\s*(?::|=|-)?\\s*${COUNT_TOKEN}\\b`, "gi");

  specificationBody(text).split(/\r?\n/).forEach((line) => {
    const source = normalized(line.replace(/^\s*#{1,6}\s+/, "").replace(/^\s*\d+[.)]\s+/, ""));
    for (const match of source.matchAll(countBeforePattern)) {
      const system = canonicalCommunicationSystem(match[0].replace(match[1] ?? "", ""));
      const value = countValue(match[1] ?? "");
      if (system && value > 0) counts[system] = Math.max(counts[system] ?? 0, value);
    }
    for (const match of source.matchAll(countAfterPattern)) {
      if (looksLikeBitrateSuffix(source.slice((match.index ?? 0) + match[0].length))) continue;
      const system = canonicalCommunicationSystem(match[0]);
      const value = countValue(match[1] ?? "");
      if (system && value > 0) counts[system] = Math.max(counts[system] ?? 0, value);
    }
  });

  for (const system of extractCommunicationSystems(text)) {
    counts[system] ??= 1;
  }
  return counts;
}

function domainFrom(text: string) {
  const explicitIndustry = normalized(text.match(/\bindustrie\s*:\s*([^\r\n]+)/i)?.[1] ?? "");
  if (explicitIndustry) {
    if (/embedded/.test(explicitIndustry)) return "embedded_systems";
    if (/aerospace|defense|defence|avionik/.test(explicitIndustry)) return "aerospace";
    if (/\brail\b|bahn|zug|train/.test(explicitIndustry)) return "rail";
    if (/marine|schiff|ship|vessel|maritim/.test(explicitIndustry)) return "marine";
    if (/building|gebaeude|gebäude|knx|bacnet|hlk/.test(explicitIndustry)) return "building_automation";
    if (/industrial|factory|fertigung|produktion|plc|profinet|ethercat/.test(explicitIndustry)) return "industrial_automation";
    if (/\benergy\b|energie/.test(explicitIndustry)) return "energy";
    if (/robotics|robotik|\bros\b/.test(explicitIndustry)) return "robotics_ros";
    if (/generic networking|networking/.test(explicitIndustry)) return "generic_networking";
    if (/automotive|fahrzeug/.test(explicitIndustry)) return "automotive";
  }
  const key = normalized(text);
  if (/industrial|plc|profinet|ethercat/.test(key)) return "industrial_automation";
  if (/aerospace|arinc|avionik/.test(key)) return "aerospace";
  if (/\brail\b|bahn|zug|train/.test(key)) return "rail";
  if (/marine|schiff|ship|vessel|maritim/.test(key)) return "marine";
  if (/building automation|gebaeude|gebäude|knx|bacnet|hlk/.test(key)) return "building_automation";
  if (/\benergy\b|energie|microgrid|wechselrichter|schaltanlage|transformator/.test(key)) return "energy";
  if (/robotics|robotik|\bros\b|manipulator|motion planner/.test(key)) return "robotics_ros";
  if (/generic networking|router|switch|firewall|loadbalancer|vpn/.test(key)) return "generic_networking";
  if (/automotive|fahrzeug|ecu|can fd|kamera|camera|radar|lidar|umfeld/.test(key)) return "automotive";
  if (/\bembedded\b|\bi2c\b|\bspi\b|\buart\b|\bpcie\b|\busb\b/.test(key)) return "embedded_systems";
  return "generic";
}

function numeric(value: string | undefined) {
  if (!value) return undefined;
  const result = Number(value.replace(",", "."));
  return Number.isFinite(result) ? result : undefined;
}

function rangeFrom(text: string) {
  const match = text
    .replace(/−/g, "-")
    .match(/(-?\d+(?:[,.]\d+)?)\s*(?:°\s*c|a|u\s*\/\s*min|\/\s*min)?\s*(?:bis|–|—)\s*\+?(-?\d+(?:[,.]\d+)?)/i);
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
  return normalizeHardwareName(name)
    .replace(/[-_\s]*(sensor|ecu|gateway|plc|controller|steuergeraet)$/i, "")
    .replace(/[^a-zA-Z0-9äöüÄÖÜß]+/g, " ")
    .trim() || name;
}

function identifier(value: string) {
  const words = value.replace(/[^a-zA-Z0-9äöüÄÖÜß]+/g, " ").trim().split(/\s+/);
  return words.map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join("");
}

function functionName(name: string, contexts: string[], roleHint = name) {
  for (const line of contexts) {
    const explicit = cleanLabel(line).match(/^\s*(?:[-*]\s*)?funktion(?:sname)?\s*:\s*(.+?)\s*$/i)?.[1];
    if (explicit) return `${identifier(name)}_${identifier(explicit)}`;
    const inline = cleanLabel(line).match(/\bfunktion(?:sname)?\s*(?::|=|-)?\s+(.+?)(?:\s+mit\b|\s+und\b|[.;,]|$)/i)?.[1];
    if (inline) return `${identifier(name)}_${identifier(inline)}`;
  }
  const key = normalized(`${name} ${roleHint}`);
  if (key.includes("sensor")) return `${identifier(name)}_Erfassung`;
  if (key.includes("gateway")) return `${identifier(name)}_Kommunikation`;
  return `${identifier(name)}_Steuerung`;
}

function signalName(name: string, context: string) {
  const key = normalized(name);
  const contextKey = normalized(context);
  if (/\bobjekt(?:e|en|s)?\b/.test(contextKey) && /\berkenn/.test(contextKey)) return "ObjektErkannt";
  if (/\bball|baelle|balle\b/.test(contextKey) && /\berkenn/.test(contextKey)) return "ObjektErkannt";
  if (key.includes("drehzahl")) return "Drehzahl";
  if (key.includes("motorstrom")) return "Motorstrom";
  if (key.includes("thermal")) return "Solltemperatur";
  if (key.includes("motion")) return "Temperaturgrenzwert";
  if (key.includes("temperatur")) return "Temperatur";
  if (key.includes("druck")) return "Druck";
  if (/warnhinweis/i.test(context)) return `${identifier(baseName(name))}Warnung`;
  if (key.includes("gateway")) return "GatewayStatus";
  return `${identifier(baseName(name))}Status`;
}

function generatedPhysicalDefaults(name: string) {
  const key = normalized(name);
  if (key.includes("temperatur")) return { min: -40, max: 215, unit: "degC" };
  if (key.includes("druck")) return { min: 0, max: 250, unit: "bar" };
  if (key.includes("drehzahl")) return { min: 0, max: 8000, unit: "rpm" };
  if (key.includes("strom")) return { min: -200, max: 200, unit: "A" };
  if (key.includes("winkel")) return { min: -180, max: 180, unit: "deg" };
  if (key.includes("geschwindigkeit") || key.includes("speed")) {
    return { min: 0, max: 300, unit: "km/h" };
  }
  if (key.includes("position")) return { min: 0, max: 100, unit: "%" };
  return { min: undefined, max: undefined, unit: undefined };
}

export function extractEngineeringSpecification(text: string, overrides: Partial<EngineeringHardwareCounts> = {}): ExtractedEngineeringSpecification {
  const lines = specificationBody(text).split(/\r?\n/);
  const occurrences = lines.flatMap((line, index): HardwareOccurrence[] => {
    const headingName = hardwareName(headingLabel(line));
    const names = [headingName, ...inlineHardwareNames(line), ...naturalLanguageHardwareNames(line), ...impliedHardwareNames(line)].filter(Boolean);
    return [...new Map(names.map((name) => [normalized(normalizeHardwareName(name)), name])).values()].map((name) => ({ index, name }));
  });
  const contexts = new Map<string, { name: string; lines: string[] }>();
  occurrences.forEach((occurrence, occurrenceIndex) => {
    const nextIndex = occurrences[occurrenceIndex + 1]?.index ?? lines.length;
    const key = normalized(normalizeHardwareName(occurrence.name));
    const existing = contexts.get(key) ?? { name: occurrence.name, lines: [] };
    existing.lines.push(...lines.slice(occurrence.index, Math.max(occurrence.index + 1, nextIndex)));
    contexts.set(key, existing);
  });

  const domain = domainFrom(text);
  const interfaceType = protocolFrom(text);
  const communicationSystems = extractCommunicationSystems(text);
  const communicationSystemCounts = extractCommunicationSystemCounts(text);
  const networkArchitecture = extractNetworkArchitectureMode(text);
  const recognizedChains = [...contexts.values()].map((entry, index): ExtractedEngineeringChain => {
    const context = entry.lines.map((line) => cleanLabel(line)).filter(Boolean).join("; ");
    const hardwareName = normalizeHardwareName(entry.name);
    const signal = signalName(hardwareName, context);
    const defaults = generatedPhysicalDefaults(signal);
    const unit = unitFrom(context) ?? defaults.unit;
    const factor = factorFrom(context, unit);
    const range = rangeFrom(context);
    const objectDetectionSignal = signal === "ObjektErkannt";
    const minValue = range.min ?? (objectDetectionSignal ? 0 : defaults.min);
    const maxValue = range.max ?? (objectDetectionSignal ? 1 : defaults.max);
    const hardwareId = identifier(hardwareName);
    const chainInterfaceType = interfaceType === "CAN" && /kamera|camera|radar|lidar|umfeld|objekt/i.test(`${hardwareName} ${context}`)
      ? "Ethernet"
      : interfaceType;
    const dataType = (minValue ?? 0) < 0 ? "signed" : "unsigned";
    const lengthBits = generatedSignalBitLength({
      minValue,
      maxValue,
      factor,
      dataType,
    });
    return {
      hardware_name: hardwareName,
      hardware_description: context.slice(0, 1000),
      device_type: deviceType(entry.name),
      function_name: functionName(hardwareName, entry.lines, entry.name),
      function_description: `Aus Nutzerspezifikation abgeleitete Funktion. ${context}`.slice(0, 1000),
      interface_name: `${hardwareId}_${chainInterfaceType}`,
      interface_type: chainInterfaceType,
      message_name: `${hardwareId}Data`,
      message_id_hex: `0x${(0x180 + index).toString(16).toUpperCase()}`,
      direction: "tx",
      cycle_ms: 10,
      dlc: generatedMessageDlc(lengthBits),
      signal_name: signal,
      signal_display_name: signal,
      start_bit: 0,
      length_bits: lengthBits,
      byte_order: "little_endian",
      data_type: dataType,
      factor,
      offset_value: 0,
      unit,
      min_value: minValue,
      max_value: maxValue,
      ...signalArchitectureMetadata({
        signalName: signal,
        hardwareName,
        interfaceType: chainInterfaceType,
        cycleMs: 10,
        dataType,
        lengthBits,
        startBit: 0,
        byteOrder: "little_endian",
        factor,
        offset: 0,
        unit,
        minValue,
        maxValue,
      }),
      domain,
    };
  });

  const requestedTargets = extractEngineeringTargetCounts(text);
  const expanded = expandArchitectureChains(
    recognizedChains,
    requestedTargets,
    domain,
    communicationSystems,
    { ...confirmedHardwareCounts(text), ...overrides },
  );

  return {
    chains: packEngineeringChains(
      expanded.chains.map((chain) => ({ ...chain, hardware_name: normalizeHardwareName(chain.hardware_name) })),
    ),
    domain,
    interfaceType,
    communicationSystems,
    communicationSystemCounts,
    networkArchitecture,
    targetCounts: expanded.targets,
  };
}

export function confirmedHardwareCounts(text: string): Partial<EngineeringHardwareCounts> {
  const header = text.split(/Konkrete Aufgabe des Nutzers/i, 1)[0];
  const raw = header.match(/^- Hardware-Sollwerte:\s*(\{[^\r\n]+\})\s*$/m)?.[1];
  if (!raw) return {};
  const counts = JSON.parse(raw) as EngineeringHardwareCounts;
  for (const key of ["sensors", "actuators", "ecus", "gateways"] as const) {
    if (!Number.isSafeInteger(counts[key]) || counts[key] < 0 || counts[key] > 1000) {
      throw new Error(`Ungueltiger Hardware-Sollwert: ${key}`);
    }
  }
  return counts;
}

export function isEngineeringReviewRequest(text: string) {
  const task = text.split(/Konkrete Aufgabe des Nutzers\s*:/i).at(-1)?.trim() ?? text.trim();
  return /^(?:bewerte|pr[uü]fe|pruefe|review|evaluate)\b/i.test(task);
}

export function isEngineeringAnalysisWorkRequest(text: string) {
  const task = text.split(/Konkrete Aufgabe des Nutzers\s*:/i).at(-1)?.trim() ?? text.trim();
  return /^(?:analysiere|analysieren|analyse|analyze|diagnose|untersuche)\b/i.test(task);
}

export function isStructuredEngineeringSpecification(text: string) {
  if (isEngineeringReviewRequest(text)) return false;
  const extracted = extractEngineeringSpecification(text);
  const parameterEvidence = /(messbereich|auflösung|aufloesung|schrittweite|sollwert|grenzwert|kommunikationsprotokoll|funktions.parameter)/i.test(text);
  return extracted.chains.length >= 2 || (extracted.chains.length === 1 && parameterEvidence);
}
