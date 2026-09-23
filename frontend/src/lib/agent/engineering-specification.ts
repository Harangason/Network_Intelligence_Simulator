import { industryTemplateLabel, industryTemplateProfile } from "./industry-templates/index.ts";
import { conciseGeneratedName } from "../engineering-names.ts";
import { automotiveFunctionOutputs } from "./industry-templates/automotive-functions.ts";
import { SENSOR_MEASUREMENTS, sensorMeasurementSelections } from './sensor-measurements.ts';
import inventoryVocabulary from './inventory-vocabulary.json' with { type: 'json' };

export function addAutomotiveFunctionOutputs(chains: ExtractedEngineeringChain[], domain: string): ExtractedEngineeringChain[] {
  if (domain !== "automotive") return chains;
  const result = [...chains];
  const usedIds = new Set(chains.map(chain => Number(chain.message_id_hex)));
  let nextId = 0x180;
  for (const [host, functionName, signal, unit, minValue, maxValue, factor] of automotiveFunctionOutputs) {
    const owner = chains.find(chain => chain.hardware_name === host && !/Sensor|Actuator|Gateway/.test(chain.device_type));
    if (!owner || result.some(chain => chain.hardware_name === host && chain.signal_name === signal)) continue;
    while (usedIds.has(nextId)) nextId++;
    if (nextId > 0x7ff) break;
    const output = chainFromTemplate({ hardwareName: host, deviceType: owner.device_type as ArchitectureTemplate["deviceType"],
      signalName: signal, interfaceType: owner.interface_type, cycleMs: 100,
      unit, minValue, maxValue, factor }, nextId - 0x180, domain);
    usedIds.add(nextId++);
    result.push({ ...owner, ...output, hardware_description: owner.hardware_description,
      interface_name: owner.interface_name, function_name: functionName,
      function_description: `${functionName}: berechneter Funktionsausgang auf ${host}. Editierbare Entwurfsvorgabe; Eingangsdaten und fachliche Anforderungen prüfen.`,
      message_name: `${host}_${signal}`, configuration: { ...output.configuration,
        functional_output_template: true, design_evidence: "illustrative_template_requires_review" } });
  }
  return result;
}

type IndustryGenerationPath = (chains: ExtractedEngineeringChain[], domain: string) => ExtractedEngineeringChain[];

const INDUSTRY_GENERATION_PATHS: Readonly<Record<string, IndustryGenerationPath>> = Object.freeze({
  automotive: addAutomotiveFunctionOutputs,
});

/**
 * Apply only the selected industry's optional enrichment path. Shared signal
 * expansion and bus packing stay outside this dispatcher and therefore cannot
 * accidentally activate an Automotive template for another industry.
 */
export function applyIndustryGenerationPath(
  chains: ExtractedEngineeringChain[],
  domain: string,
): ExtractedEngineeringChain[] {
  const path = INDUSTRY_GENERATION_PATHS[domain];
  return path ? path(chains, domain) : chains;
}

/** Device roles belong to device_type; technical identifiers remain unchanged. */
export function normalizeHardwareName(value: string): string {
  const original = value.trim();
  return original.replace(/(?:[-_ ]?(?:ECU|Gateway|Sensor|Aktor|Aktuator|Actuator|Controller|Steuerger(?:ä|ae|a|�)t))+([-_ ]\d+)?$/i, "$1")
    .replace(/^[-_ ]+|[-_ ]+$/g, "") || original;
}

export type ExtractedEngineeringChain = {
  device_class?: number;
  hardware_name: string;
  hardware_description: string;
  device_type: string;
  data_complexity?: string;
  payload_element_type?: string;
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
  modelType: string;
  interfaceType: string;
  communicationSystems: string[];
  communicationSystemCounts: Record<string, number>;
  networkArchitecture: NetworkArchitectureMode;
  targetCounts: EngineeringTargetCounts;
};

export type EngineeringDomainEvidence = {
  domain: string;
  confidence: number;
  markers: string[];
};

function extractProjectModelType(text: string, fallback: string) {
  const value = text.match(/^- Projekt-Modelltyp:\s*([^\r\n]+)$/mi)?.[1]?.trim();
  return value ? value.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") : fallback;
}

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

const ENGINEERING_CONTROLLER_DEVICE_TYPES = new Set([
  "ECU",
  "PLC",
  "RobotController",
  "EmbeddedController",
  "IndustrialPC",
  "FlightComputer",
  "BatteryManagementSystem",
  "EnergyController",
  "BuildingController",
]);

type EngineeringControllerDeviceType = "ECU" | "PLC" | "RobotController" | "EmbeddedController" | "IndustrialPC" | "FlightComputer" | "EnergyController" | "BuildingController";

export function isEngineeringControllerDevice(deviceType: string) {
  return ENGINEERING_CONTROLLER_DEVICE_TYPES.has(deviceType);
}

export function controllerDeviceTypeForModel(modelType: string): EngineeringControllerDeviceType {
  if (modelType === "industrial_automation" || modelType === "process_industry") return "PLC";
  if (modelType === "robotics_ros") return "RobotController";
  if (modelType === "aerospace") return "FlightComputer";
  if (modelType === "energy") return "EnergyController";
  if (modelType === "building_automation") return "BuildingController";
  if (modelType === "embedded_systems" || modelType === "iot_wireless") return "EmbeddedController";
  if (modelType === "generic_networking" || modelType === "custom") return "IndustrialPC";
  return "ECU";
}

function requiresCompleteSignalModel(chain: ExtractedEngineeringChain) {
  if (chain.device_class != null) return chain.device_class >= 2;
  if (INTELLIGENT_DEVICE_TYPES.has(chain.device_type)) return true;
  return /camera|kamera|vision|radar|lidar|scanner|ultrasonic|advanced[_ -]?imu/i.test(chain.hardware_name);
}

function companionSignal(
  chain: ExtractedEngineeringChain,
  suffix: string,
  overrides: Partial<ExtractedEngineeringChain>,
): ExtractedEngineeringChain {
  const base = identifier(chain.hardware_name);
  const result = {
    ...chain,
    signal_name: `${base}${suffix}`,
    signal_display_name: `${base}${suffix}`,
    start_bit: 0,
    ...overrides,
  };
  // Companion signals have their own domain and encoding, never the parent's.
  const metadata = signalArchitectureMetadata({ signalName: result.signal_name, hardwareName: result.hardware_name,
    interfaceType: result.interface_type, cycleMs: result.cycle_ms, dataType: result.data_type,
    lengthBits: result.length_bits, startBit: 0, byteOrder: "little_endian", factor: result.factor,
    offset: result.offset_value, unit: result.unit, minValue: result.min_value, maxValue: result.max_value });
  return { ...result, ...metadata, semantic: overrides.semantic ?? metadata.semantic,
    data: overrides.data ?? metadata.data,
    configuration: { ...chain.configuration, ...metadata.configuration, generation_role: suffix.toUpperCase() } };

}

/**
 * Class 3/4 devices need an inspectable minimum model instead of a single
 * placeholder signal. Message packing assigns the final offsets and DLC.
 */
export function expandEngineeringSignalModel(chains: ExtractedEngineeringChain[]) {
  return chains.flatMap((chain) => {
    if (!requiresCompleteSignalModel(chain)) return [chain];
    const candidates = [
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
      chain,
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
  deviceType: "SensorController" | "ActuatorController" | "Gateway" | EngineeringControllerDeviceType;
  signalName: string;
  interfaceType: string;
  cycleMs: number;
  unit?: string;
  minValue?: number;
  maxValue?: number;
  factor?: number;
  functionalOwner?: string;
  coverageRole?: string;
};

type HardwareOccurrence = {
  index: number;
  name: string;
  declaredType?: string;
  declaredInterface?: string;
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
    return ((34 + (payloadBytes + 1) * 10) / 19_200) / cycleSeconds * 100;
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
  const name = conciseGeneratedName('Message', `${identifier(chain.function_name || chain.hardware_name)}Data`);
  return index === 0 ? name : `${name} Teil ${index + 1}`;
}

function packedInterfaceName(chain: ExtractedEngineeringChain, channel: number) {
  return `${identifier(chain.hardware_name)}${channel === 0 ? '' : ` Kanal ${channel + 1}`}`;
}

export function packEngineeringChains(
  chains: ExtractedEngineeringChain[],
  targetLoadPercent = DEFAULT_INTERFACE_TARGET_LOAD_PERCENT,
) {
  const packed = chains.map((chain) => ({ ...chain, function_name: conciseGeneratedName('Function', chain.function_name) }));
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
      chain.configuration = { ...chain.configuration, start_bit: chain.start_bit, bit_length: chain.length_bits,
        factor: chain.factor, offset: chain.offset_value, raw_datatype: chain.data_type, signed: chain.data_type === "signed" };
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
  // Physical quantity wins over words such as Status or Quality in a name.
  if (input.unit && !["code", "bool", "boolean", "enum", "state", "not_applicable", "1"].includes(input.unit.toLowerCase())) return "NUMERIC";
  const key = normalized(`${input.signalName} ${input.hardwareName} ${input.unit ?? ""}`);
  if ((input.lengthBits === 1 || (input.minValue === 0 && input.maxValue === 1)) && /status|flag|schaltausgang|stellglied|aktiv|enable|boolean/.test(key)) {
    return "BOOLEAN";
  }
  if ((input.lengthBits === 1 || (input.minValue === 0 && input.maxValue === 1)) && /erkannt|detected|presence|praesenz/.test(key)) {
    return "BOOLEAN";
  }
  if (/status|state|mode|zustand|diagnose|fehler|code/.test(key) || input.unit === "code") return "STATE";
  return "NUMERIC";
}

function generatedArchitectureBitLength(input: Omit<SignalArchitectureInput, "lengthBits" | "startBit" | "byteOrder">) {
  const calculated = generatedSignalBitLength({
    minValue: input.minValue,
    maxValue: input.maxValue,
    factor: input.factor,
    offsetValue: input.offset,
    dataType: input.dataType,
  });
  const semanticType = generatedSignalSemanticType({
    ...input,
    lengthBits: calculated,
    startBit: 0,
    byteOrder: "little_endian",
  });
  // The canonical state domain reserves four additional codes. Its eight
  // addressable values therefore require three bits even when min/max only
  // describe the four nominal states.
  return semanticType === "STATE" ? Math.max(3, calculated) : calculated;
}

function stateDomain(input: SignalArchitectureInput) {
  const gateway = /gateway/.test(normalized(input.signalName));
  const enumValues = gateway
    ? { OK: 0, DEGRADED: 1, ROUTING_LIMITED: 2, ERROR: 3 }
    : { OK: 0, WARNING: 1, ERROR: 2, NOT_AVAILABLE: 3 };
  return {
    enum_values: enumValues,
    allowed_values: Object.keys(enumValues),
    reserved_values: [4, 5, 6],
    invalid_values: [7],
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
          invalid_values: [],
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
      generated_by: "engineering-specification-parser-v3",
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
  "funktionscontroller",
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
  "funktionscontroller",
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
  const targets = extractEngineeringTargetCounts(text);
  if (targets.ecus > 1 && /(?:gateway\s*\/\s*edge\s+controller|zentrale\s+kopplung)/i.test(text)) return "gateway_ecu_segments";
  return defaultNetworkArchitectureMode(
    /\bgateway\b|\buebergeordnete?\s+kommunikationsanbindung\b/.test(normalized(text)) ? 1 : 0,
  );
}

export function defaultNetworkArchitectureMode(gatewayCount: number): NetworkArchitectureMode {
  return gatewayCount > 0 ? "gateway_direct" : "sensor_ecu_actuator";
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
  const countAfterPattern = new RegExp(`\\b${modifiers}${nounPattern}\\b\\s*(?:anzahl|countsep)\\s*${COUNT_TOKEN}\\b`, "g");
  const countAfterBareLinePattern = new RegExp(`^${modifiers}${nounPattern}\\s+${COUNT_TOKEN}$`, "g");
  // Numbered UI choices and adjacent lines are not hardware quantity statements.
  return text.split(/\r?\n/).reduce((maximum, line) => {
    const source = normalized(line
      .replace(/^\s*#{1,6}\s+/, "")
      .replace(/^\s*\d+[.)]\s+/, "")
      .replace(/[:=]|(?:^|\s)-(?:\s*)(?=\d|ein\b|eine\b|zwei\b|drei\b|vier\b|fuenf\b|funf\b|sechs\b|sieben\b|acht\b|neun\b|zehn\b)/gi, " countsep ")
      .replace(/\bVariante\s+\d+(?:\s*(?:\+|und)\s*\d+)?/gi, "Variante"));
    const before = [...source.matchAll(countBeforePattern)].reduce((count, match) => Math.max(count, countValue(match[1] ?? "")), maximum);
    const after = [...source.matchAll(countAfterPattern)].reduce((count, match) => Math.max(count, countValue(match[1] ?? "")), before);
    return [...source.matchAll(countAfterBareLinePattern)].reduce((count, match) => Math.max(count, countValue(match[1] ?? "")), after);
  }, 0);
}

// Repeated mentions of a group are not additional hardware. Distinct typed
// groups are additive; a declared category total precedes its breakdown.
function inventoryCount(text: string, nouns: string, modifiers: string, generic: RegExp) {
  const groups = new Map<string, number>();
  const before = new RegExp("\\b" + COUNT_TOKEN + "\\s+((?:(?:" + modifiers + ")\\s+){0,3}(?:" + nouns + "))\\b", "g");
  let declared = 0;
  for (const line of text.split(/\r?\n/)) {
    const source = normalized(line.replace(/^\s*\d+[.)]\s+/, "").replace(/\bVariante\s+\d+/gi, "Variante")
      .replace(/([a-zäöü]+)-\/([a-zäöü]+)/gi, "$1$2"));
    for (const match of source.matchAll(before)) {
      const label = match[2];
      const count = countValue(match[1]);
      if (generic.test(label)) declared = Math.max(declared, count);
      else groups.set(label, Math.max(groups.get(label) ?? 0, count));
    }
  }
  return Math.max(declared, [...groups.values()].reduce((sum, count) => sum + count, 0));
}

export function extractEngineeringTargetCounts(text: string): EngineeringTargetCounts {
  const body = specificationBody(text);
  const modifiers = inventoryVocabulary.modifiers;
  const sensors = Math.max(requestedCount(body, "sensor(?:en|s)?"), inventoryCount(body,
    inventoryVocabulary.roles.sensors.nouns, modifiers, new RegExp(inventoryVocabulary.roles.sensors.generic)));
  const actuators = Math.max(requestedCount(body, "(?:actuator(?:s)?|aktuator(?:en)?|aktor(?:en)?)", modifiers), inventoryCount(body,
    inventoryVocabulary.roles.actuators.nouns, modifiers, new RegExp(inventoryVocabulary.roles.actuators.generic)));
  const additionalCompute = inventoryCount(body, inventoryVocabulary.roles.ecus.additional_compute, "", /a^/);
  const ecus = Math.max(
    requestedCount(body, "ecu(?:s)?", "funktions|zentrale|typische|weitere"),
    inventoryCount(body, inventoryVocabulary.roles.ecus.nouns, modifiers, new RegExp(inventoryVocabulary.roles.ecus.generic)),
  ) + additionalCompute;
  const centralCoupling = sensors > 0 || actuators > 0 || ecus > 0
    ? requestedCount(body, "(?:zentrale|zentralen|zentrales|zentraler)\\s+(?:kopplung|koppelstelle)(?:en)?")
    : 0;
  const gateways = Math.max(
    requestedCount(body, "gateway(?:s)?", modifiers + "|einziges|einzigen"),
    requestedCount(body, "(?:uebergeordnete|übergeordnete)\\s+kommunikationsanbindung(?:en)?"),
    centralCoupling,
  );
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
      else if (isEngineeringControllerDevice(chain.device_type)) counts.ecus += 1;
      return counts;
    },
    { sensors: 0, actuators: 0, ecus: 0, gateways: 0 },
  );
}

function systemInterfaceType(name: string, domain: string) {
  const key = normalized(name);
  if (domain === "industrial_automation" || domain === "process_industry") {
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
  if (domain === "iot_wireless") return "WiFi";
  if (domain === "custom") return "Ethernet";
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
  const automotiveSensorOwner = (name: string) => {
    if (domain !== "automotive") return undefined;
    const rules: Array<[RegExp, string]> = [
      [/brake/i, "Bremsregelung"],
      [/suspension|damper/i, "Daempferregelung"],
      [/tirepressure|tiretemperature|tirewear/i, "Reifendruckkontrolle"],
      [/wheelangle|steering/i, "Lenkung"],
      [/wheelspeed|wheelacceleration|wheelload|wheeltorque|longitudinal|lateral|vertical|yaw|pitch|roll/i, "Stabilitaetsregelung"],
      [/transmission|clutch|gearselector/i, "Getriebesteuerung"],
      [/fuel/i, "Kraftstoffsystem"],
      [/urea|exhaust|egr/i, "Abgasnachbehandlung"],
      [/battery|cellvoltage/i, "Batteriemanagement"],
      [/dclink|inverter/i, "Invertersteuerung"],
      [/motorspeed|motorcurrent|motortemperature/i, "Elektromotorsteuerung"],
      [/alternator|accessory|lowvoltage/i, "Bordnetzmanagement"],
      [/cabin|ambienttemperature|refrigerant/i, "Klimatisierung"],
      [/camera/i, "Kameraverarbeitung"],
      [/radar/i, "Radarverarbeitung"],
      [/ultrasonic/i, "Ultraschallverarbeitung"],
      [/washer|rain/i, "Wischersteuerung"],
      [/ambientlight/i, "Aussenlicht"],
      [/coolant|oil|enginespeed|boost|accelerator|throttle|turbo/i, "Motorsteuerung"],
    ];
    return rules.find(([pattern]) => pattern.test(name))?.[1] ?? "Fahrerassistenz";
  };
  const sensorTemplates = profile.sensorTemplates.map((template) => ({
    hardwareName: template.hardwareName,
    deviceType: "SensorController" as const,
    signalName: template.signalName,
    // The industry template is authoritative. Replacing every ordinary sensor
    // with LIN silently moved fast and safety-relevant devices onto the wrong bus.
    interfaceType: template.interfaceType,
    cycleMs: template.cycleMs,
    unit: template.unit,
    minValue: template.minValue,
    maxValue: template.maxValue,
    factor: template.factor ?? 1,
    functionalOwner: automotiveSensorOwner(template.hardwareName),
    coverageRole: "DomainMeasurement",
  }));
  const controllers = profile.systemVariants.map((name) => {
    const interfaceType = systemInterfaceType(name, domain);
    return {
    hardwareName: name,
    deviceType: controllerDeviceTypeForModel(domain),
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
    const interfaceType = domain === "automotive" ? "LIN" : systemInterfaceType(`${name} ${kind}`, domain);
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
    functionalOwner: name,
    coverageRole: kind,
    };
  }));
  return [
    ...sensorTemplates,
    ...actuators,
    ...controllers,
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
  const lengthBits = generatedArchitectureBitLength({
    signalName: template.signalName,
    hardwareName: template.hardwareName,
    interfaceType: template.interfaceType,
    cycleMs: template.cycleMs,
    minValue: template.minValue,
    maxValue: template.maxValue,
    factor: template.factor ?? 1,
    offset: 0,
    unit: template.unit,
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
    ...(template.functionalOwner || template.coverageRole ? {
      configuration: {
        ...(template.functionalOwner ? { functional_owner: template.functionalOwner } : {}),
        ...(template.coverageRole ? { coverage_role: template.coverageRole } : {}),
        ...(template.deviceType === "ActuatorController" && template.coverageRole ? {
          actuator_command_template: { source: "wizard-generic-actuator-v1", length_bits: lengthBits,
            data_type: dataType, unit: template.unit, factor: template.factor ?? 1,
            min_value: template.minValue, max_value: template.maxValue,
            semantic: { semantic_type: "NUMERIC", meaning: `Generischer Simulations-Sollwert: ${template.coverageRole}` },
            data: { minimum: template.minValue, maximum: template.maxValue, resolution: template.factor ?? 1 } },
        } : {}),
      },
    } : {}),
    domain,
  };
}

const SENSOR_COVERAGE_ROLES = [
  ["PrimaryFeedback", "Rueckmeldung", "%", 0, 100, 0.1],
  ["OperatingState", "Betriebszustand", "code", 0, 15, 1],
  ["HealthFeedback", "Zustandsdiagnose", "%", 0, 100, 1],
  ["DemandInput", "Sollwertvorgabe", "%", 0, 100, 0.1],
  ["SafetyFeedback", "Sicherheitsrueckmeldung", "code", 0, 7, 1],
] as const;

const ACTUATOR_COVERAGE_ROLES = [
  ["PrimaryCommand", "Stellbefehl", "%", 0, 100, 0.1],
  ["EnableCommand", "Freigabebefehl", "code", 0, 1, 1],
  ["SafetyCommand", "Sicherheitsbefehl", "code", 0, 3, 1],
  ["FallbackCommand", "Rueckfallbefehl", "%", 0, 100, 0.1],
  ["DiagnosticCommand", "Diagnosebefehl", "code", 0, 15, 1],
] as const;

function alphabeticOrdinal(value: number) {
  let remaining = value;
  let result = "";
  do {
    result = String.fromCharCode(65 + (remaining % 26)) + result;
    remaining = Math.floor(remaining / 26) - 1;
  } while (remaining >= 0);
  return result;
}

function supplementalEndpointTemplate(
  deviceType: "SensorController" | "ActuatorController",
  controller: ExtractedEngineeringChain,
  ordinal: number,
): ArchitectureTemplate {
  const roles = deviceType === "SensorController" ? SENSOR_COVERAGE_ROLES : ACTUATOR_COVERAGE_ROLES;
  const [role, signalRole, unit, minValue, maxValue, factor] = roles[ordinal % roles.length];
  const generation = Math.floor(ordinal / roles.length);
  const semanticRole = generation ? `${role}${alphabeticOrdinal(generation - 1)}` : role;
  const controllerName = normalizeHardwareName(controller.hardware_name);
  return {
    hardwareName: `${controllerName}${semanticRole}`,
    deviceType,
    signalName: `${identifier(controllerName)}${signalRole}${generation ? alphabeticOrdinal(generation - 1) : ""}`,
    interfaceType: controller.interface_type,
    cycleMs: controller.cycle_ms,
    unit,
    minValue,
    maxValue,
    factor,
    functionalOwner: controller.hardware_name,
    coverageRole: semanticRole,
  };
}

function supplementalInfrastructureTemplate(
  deviceType: EngineeringControllerDeviceType | "Gateway",
  ordinal: number,
  domain: string,
): ArchitectureTemplate {
  const role = ["SafetySupervisor", "ServiceCoordinator", "DiagnosticsCoordinator", "FallbackCoordinator", "ZoneCoordinator"][ordinal % 5];
  const generation = Math.floor(ordinal / 5);
  const qualifier = generation ? alphabeticOrdinal(generation - 1) : "";
  const hardwareName = deviceType === "Gateway" ? `${role}${qualifier}Gateway` : `${role}${qualifier}`;
  return {
    hardwareName,
    deviceType,
    signalName: `${identifier(hardwareName)}Status`,
    interfaceType: systemInterfaceType(role, domain),
    cycleMs: 20,
    unit: "code",
    minValue: 0,
    maxValue: 255,
    factor: 1,
    coverageRole: role,
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
    if (!isEngineeringControllerDevice(chain.device_type)) return [chain];
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
  completenessFirst = false,
  allowExampleTemplates = false,
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
  const chains = targets.explicit && !completenessFirst
    ? canonicalRecognizedChains.filter((chain) => {
      const category = chain.device_type === "SensorController"
        ? "sensors"
        : chain.device_type === "ActuatorController" ? "actuators"
        : chain.device_type === "Gateway"
          ? "gateways"
          : isEngineeringControllerDevice(chain.device_type)
            ? "ecus"
            : null;
      if (!category) return true;
      if (retainedCounts[category] >= targets[category]) return false;
      retainedCounts[category] += 1;
      return true;
    })
    : [...canonicalRecognizedChains];
  const names = new Set(chains.map((chain) => normalized(normalizeHardwareName(chain.hardware_name))));
  // A quantity is not permission to invent device identities, physical
  // technologies or additional owners. Only an explicit example request may
  // expand a catalogue. Keep missing inventory visible to the caller.
  if (!targets.explicit || !allowExampleTemplates) return { chains: allowExampleTemplates ? chains : [...canonicalRecognizedChains], targets };

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
  // Once the finite catalogue is exhausted, create semantically distinct roles.
  // Numeric copies of identical hardware/signals made ownership ambiguous.
  const targetControllerType = controllerDeviceTypeForModel(domain);
  for (const deviceType of [targetControllerType, "Gateway", "SensorController", "ActuatorController"] as const) {
    let current = isEngineeringControllerDevice(deviceType)
      ? chainCounts(chains).ecus : chains.filter((chain) => chain.device_type === deviceType).length;
    let instance = 0;
    while (current < targetFor(deviceType)) {
      const controllers = chains.filter((chain) => isEngineeringControllerDevice(chain.device_type));
      const template = (deviceType === "SensorController" || deviceType === "ActuatorController") && controllers.length
        ? supplementalEndpointTemplate(deviceType, controllers[instance % controllers.length], Math.floor(instance / controllers.length))
        : supplementalInfrastructureTemplate(deviceType as EngineeringControllerDeviceType | "Gateway", instance, domain);
      const hardwareName = template.hardwareName;
      if (names.has(normalized(normalizeHardwareName(hardwareName)))) {
        instance += 1;
        continue;
      }
      const interfaceType = communicationSystems.some((system) => communicationSystemAllowsTemplateInterface(system, template.interfaceType)) || !communicationSystems.length
        ? template.interfaceType : communicationSystems[instance % communicationSystems.length];
      chains.push(chainFromTemplate({ ...template, hardwareName, interfaceType }, chains.length, domain));
      names.add(normalized(normalizeHardwareName(hardwareName)));
      current += 1;
      instance += 1;
    }
  }
  if (domain === "automotive" && completenessFirst) {
    const presentControllers = new Set(chains
      .filter((chain) => isEngineeringControllerDevice(chain.device_type))
      .map((chain) => normalized(normalizeHardwareName(chain.hardware_name))));
    const adasSelected = ["fahrerassistenz", "kameraverarbeitung", "radarverarbeitung", "ultraschallverarbeitung"]
      .some((name) => presentControllers.has(name));
    if (adasSelected) {
      const requiredNames = [
        "Fahrerassistenz", "Kameraverarbeitung", "Radarverarbeitung", "Ultraschallverarbeitung",
        "FrontCameraSensor", "RearCameraSensor", "SurroundLeftCameraSensor", "SurroundRightCameraSensor",
        "FrontRadarDistanceSensor", "RearRadarDistanceSensor",
        "FrontLeftUltrasonicDistanceSensor", "FrontRightUltrasonicDistanceSensor",
        "RearLeftUltrasonicDistanceSensor", "RearRightUltrasonicDistanceSensor",
      ];
      for (const requiredName of requiredNames) {
        const key = normalized(normalizeHardwareName(requiredName));
        if (names.has(key)) continue;
        const template = templates.find((candidate) => normalized(normalizeHardwareName(candidate.hardwareName)) === key);
        if (!template) continue;
        const interfaceType = communicationSystems.some((system) => communicationSystemAllowsTemplateInterface(system, template.interfaceType)) || !communicationSystems.length
          ? template.interfaceType
          : communicationSystems.includes("Ethernet") || communicationSystems.includes("SOME_IP")
            ? "Ethernet"
            : communicationSystems[0];
        chains.push(chainFromTemplate({ ...template, interfaceType }, chains.length, domain));
        names.add(key);
      }
    }
  }
  if (completenessFirst) {
    // Hardware targets are minimums in completeness-first mode. A named ECU
    // may consume the final target slot while catalog endpoints still refer to
    // a later controller. Close those ownership references explicitly instead
    // of leaving otherwise valid sensors or actuators orphaned in clustering.
    const controllerNames = new Set(chains
      .filter((chain) => isEngineeringControllerDevice(chain.device_type))
      .map((chain) => normalized(normalizeHardwareName(chain.hardware_name))));
    const requiredOwners = new Map<string, { name: string; endpoint: ExtractedEngineeringChain }>();
    for (const chain of chains) {
      if (chain.device_type !== "SensorController" && chain.device_type !== "ActuatorController") continue;
      const owner = typeof chain.configuration?.functional_owner === "string"
        ? normalizeHardwareName(chain.configuration.functional_owner)
        : "";
      const key = normalized(owner);
      if (key && !controllerNames.has(key) && !requiredOwners.has(key)) {
        requiredOwners.set(key, { name: owner, endpoint: chain });
      }
    }
    for (const [key, { name: ownerName, endpoint }] of requiredOwners) {
      const catalogTemplate = templates.find((template) =>
        isEngineeringControllerDevice(template.deviceType)
        && normalized(normalizeHardwareName(template.hardwareName)) === key);
      const preferredInterfaceType = catalogTemplate?.interfaceType || systemInterfaceType(ownerName, domain) || endpoint.interface_type;
      const template: ArchitectureTemplate = catalogTemplate ?? {
        hardwareName: ownerName,
        deviceType: targetControllerType,
        signalName: `${identifier(ownerName)}Status`,
        interfaceType: preferredInterfaceType,
        cycleMs: preferredInterfaceType === "LIN" ? 100 : preferredInterfaceType === "Ethernet" ? 20 : 10,
        unit: "code",
        minValue: 0,
        maxValue: 255,
        factor: 1,
      };
      const interfaceType = communicationSystems.some((system) => communicationSystemAllowsTemplateInterface(system, preferredInterfaceType))
        || !communicationSystems.length
        ? preferredInterfaceType
        : communicationSystems[chains.length % communicationSystems.length];
      chains.push(chainFromTemplate({ ...template, hardwareName: ownerName, interfaceType }, chains.length, domain));
      names.add(key);
      controllerNames.add(key);
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
  const genericModifiers = inventoryVocabulary.modifiers.split('|')
    .filter(modifier => !['io link', 'can fd', 'ethernet', 'real time'].includes(modifier))
    .join('|');
  return new RegExp(
    `^(?:genau\\s+)?${COUNT_TOKEN}\\s+(?:(?:${genericModifiers}|funktions|typische|weitere|einziges|einzigen)\\s+){0,3}(?:sensor(?:en|s)?|actuator(?:s)?|aktuator(?:en)?|aktor(?:en)?|ecu(?:s)?|funktionscontroller(?:s)?|controller(?:s)?|plc(?:s)?|sps|steuerger(?:a|ä|ae)t(?:e)?|gateway(?:s)?)$`,
  ).test(key);
}

function hardwareName(label: string) {
  const rawName = cleanLabel(label);
  const exampleName = rawName.replace(/^(?:beispiel|beispielsweise)\s+/i, "").trim();
  const name = exampleName && exampleName !== rawName && /\b[\p{L}\d][\p{L}\d_-]*(?:sensor|actuator|aktuator|aktor|ecu|gateway|plc|controller|steuergeraet|steuergerät)\b/iu.test(exampleName)
    ? exampleName
    : rawName;
  if (/[↔→←]|<->|<-|->/.test(name)) return "";
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

function singularControllerHardwareNames(line: string): Array<{ name: string; declaredType: string }> {
  const match = line.match(/^\s*(?:[-*]\s*)?1\s+([\p{L}][\p{L}\s-]*(?:Controller|Computer))\s*$/iu);
  if (!match) return [];
  const name = cleanLabel(match[1]);
  return [{ name, declaredType: /computer$/i.test(name) ? 'IndustrialPC' : deviceType(name) }];
}

/** Explicit role-first declarations keep identifiers that have no role suffix. */
function declaredHardwareNames(line: string): Array<{ name: string; declaredType: string }> {
  const roles = /\b(gateways?|ecus?|controllers?|sensor(?:en|s)?|aktor(?:en)?|aktuator(?:en)?|actuators?|plcs?|sps|steuerger(?:ä|ae)te?)\b\s*(?::\s*|\s+)(?:namens\s+|named\s+)?/giu;
  const name = /^(?:"([^"\r\n]+)"|„([^“\r\n]+)“|'([^'\r\n]+)'|([\p{L}][\p{L}\d_-]*))/u;
  const prose = /^(?:mit|und|and|oder|or|von|vom|zu|zum|zur|fuer|für|auf|an|aus|im|in|der|die|das|den|dem|des|ein(?:e|er|em|en|es)?|einem|einen|with|for|to|is|are|wird|werden|soll|sollen|ist|sind|als|je|pro|insgesamt|jeweils|plus|ueber|über|anzahl|erfassen|messen|steuern|measure|capture|control|can|can_fd|can-fd|lin|ethernet|sensor(?:en|s)?|aktor(?:en)?|aktuator(?:en)?|actuators?|ecus?|gateways?|plcs?)$/iu;
  const result: Array<{ name: string; declaredType: string }> = [];
  for (const match of line.matchAll(roles)) {
    const prefix = line.slice(0, match.index);
    const remainingName = line.slice(match.index! + match[0].length);
    // A role word in a capability heading ("Gateway Queueing") or a rule
    // ("Gateway muss ...") does not declare a participant. Require a local
    // naming/count/enumeration context instead of consuming its next word.
    const explicitName = /:\s*$|\b(?:namens|named)\s*$/iu.test(match[0]) || /^["„']/.test(remainingName);
    const declarationContext = (/^\s*(?:[-*]\s*)?$/.test(prefix) && /^(PLC|SPS)$/i.test(match[1])) || /\b(?:ein(?:e|en|em|er|es)?|\d+|den|dem)\s*$/iu.test(prefix)
      || /\b(?:mit|aus|with|containing)\s+(?:(?:der|die|das|den|dem|the|an?)\s+)?$/iu.test(prefix);
    if (!explicitName && !declarationContext) continue;
    const role = normalized(match[1]);
    const declaredType = role.startsWith('gateway') ? 'Gateway'
      : role.startsWith('sensor') ? 'SensorController'
      : /^(aktor|aktuator|actuator)/.test(role) ? 'ActuatorController'
      : /^(plc|sps)/.test(role) ? 'PLC' : 'ECU';
    let remaining = remainingName;
    while (remaining) {
      const candidate = remaining.match(name);
      if (!candidate) break;
      const label = (candidate[1] ?? candidate[2] ?? candidate[3] ?? candidate[4]).trim();
      if (!label || prose.test(label) || isCountedHardwareGroup(label)) break;
      result.push({ name: label, declaredType });
      remaining = remaining.slice(candidate[0].length);
      const separator = remaining.match(/^\s*(?:,\s*(?:(?:und|and)\s+)?|(?:und|and|&)\s+)/iu);
      if (!separator) break;
      remaining = remaining.slice(separator[0].length);
    }
  }
  return result;
}

function groupedHardwareNames(lines: string[]): HardwareOccurrence[] {
  const group = /^\s*(?:[-*]\s*)?(?:\d+|ein(?:e|en|em|er|es)?|zwei|drei|vier|fuenf|funf|sechs|sieben|acht|neun|zehn)\s+((?:io[-\s]*link[-\s]*)?sensor(?:en|s)?|aktor(?:en)?|aktuator(?:en)?|actuators?)\s*:\s*$/iu;
  const bullet = /^\s*[-*]\s+(.+?)\s*$/u;
  const result: HardwareOccurrence[] = [];
  for (let index = 0; index < lines.length; index += 1) {
    const heading = lines[index].match(group);
    if (!heading) continue;
    const role = normalized(heading[1]).includes('sensor') ? 'SensorController' : 'ActuatorController';
    const declaredInterface = /io[-\s]*link/iu.test(heading[1]) ? 'IO_LINK' : undefined;
    let generatedValveIndex = 0;
    for (let itemIndex = index + 1; itemIndex < lines.length; itemIndex += 1) {
      const item = lines[itemIndex].match(bullet)?.[1];
      if (!item) break;
      const counted = item.match(/^((?:\d+|ein(?:e|en|em|er|es)?|zwei|drei|vier|fuenf|funf|sechs|sieben|acht|neun|zehn))\s+(.+)$/iu);
      const count = counted ? Math.max(1, countValue(normalized(counted[1]))) : 1;
      const description = (counted?.[2] ?? item).split(/\s+(?:über|ueber|via)\s+|\s*[,;]\s*/iu, 1)[0].trim();
      const valve = role === 'ActuatorController' && /\b(?:pwm[-\s]*)?ventil(?:e|en)?\b/iu.test(description);
      for (let instance = 0; instance < count; instance += 1) {
        const name = valve
          ? `Ventilaktor${++generatedValveIndex}`
          : count > 1 ? `${description}${instance + 1}` : description;
        if (name) result.push({ index: itemIndex, name, declaredType: role, declaredInterface });
      }
    }
  }
  return result;
}

function explicitCommunicationAssignments(text: string, names: string[]): Record<string, string> {
  const assignments: Record<string, string> = {};
  const conflicts = new Set<string>();
  const key = (value: string) => normalized(normalizeHardwareName(value)).replace(/\d+$/, '').replace(/s$/, '');
  for (const line of text.split(/\r?\n/)) {
    const match = line.match(/^\s*[-*]\s+(.+?)\s*:\s*(.+)\s*$/u);
    if (!match) continue;
    const systems = extractCommunicationSystems(match[2]).filter(system => !['DDS', 'SOME_IP', 'MQTT', 'OPCUA'].includes(system));
    if (systems.length !== 1) continue;
    const participants = match[1].split(/\s*(?:\/|↔|<->|→|->)\s*/u).map(key).filter(Boolean);
    for (const name of names) {
      const hardwareKey = key(name);
      const shortControllerName = /\b(?:Computer|Controller)$/iu.test(name) ? hardwareKey.split(' ')[0] : '';
      const uniqueShortName = shortControllerName && names.filter(candidate => key(candidate).split(' ')[0] === shortControllerName).length === 1;
      if (!participants.includes(hardwareKey) && !(uniqueShortName && participants.includes(shortControllerName))) continue;
      const canonicalKey = normalizeHardwareName(name).toLocaleLowerCase('de');
      if (assignments[canonicalKey] && assignments[canonicalKey] !== systems[0]) conflicts.add(canonicalKey);
      assignments[canonicalKey] = systems[0];
    }
  }
  for (const name of conflicts) delete assignments[name];
  return assignments;
}

function explicitFunctionalOwner(name: string, controllers: string[], text: string): string | undefined {
  const escape = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const endpoint = escape(name);
  const owners = controllers.filter(controller => {
    const owner = escape(controller);
    return new RegExp(`\\b${endpoint}\\s+(?:wird|werden)\\s+(?:von(?:\\s+(?:der|dem))?|vom)\\s+${owner}\\s+(?:ausgewertet|überwacht|ueberwacht|gesteuert|geregelt)\\b`, 'iu').test(text)
      || new RegExp(`\\b${owner}\\s+(?:steuert|regelt|überwacht|ueberwacht|wertet)\\s+${endpoint}\\b`, 'iu').test(text);
  });
  return owners.length === 1 ? owners[0] : undefined;
}

function impliedHardwareNames(line: string, confirmedActuators?: number, specification = line) {
  const key = normalized(line);
  const names: string[] = [];
  if (/\b(?:raspberry|rasberry|rasperry|respary)\s*pi\b|\braspi\b/.test(key)) names.push('RaspberryPi');
  if (/^(?:(?:1|ein(?:e|en|em|er|es)?)\s+)?(?:plc|sps)$/.test(key)) names.push('PLC');
  const plcControllerCount = key.match(new RegExp(`^${COUNT_TOKEN}\\s+(?:plc|sps)(?:\\s*[/+-]?\\s*controller)?s?$`));
  if (plcControllerCount) {
    const count = Math.min(1000, countValue(plcControllerCount[1]));
    for (let i = 1; i <= count; i++) names.push(count === 1 ? 'PLC' : `PLC${i}`);
  }
  if (/^(?:(?:1|ein(?:e|en|em|er|es)?)\s+)(?:controller|steuergeraet|ecu)$/.test(key)) names.push('Controller');
  if (/^(?:(?:1|ein(?:e|en|em|er|es)?)\s+)?safety\s+controller$/.test(key)) names.push('SafetyController');
  if (/^(?:(?:1|ein(?:e|en|em|er|es)?)\s+)?sicherheitssteuerung$/.test(key)) names.push('Sicherheitssteuerung');
  if (/^(?:(?:1|ein(?:e|en|em|er|es)?)\s+)?uebergeordnete\s+kommunikationsanbindung$/.test(key)) names.push('SystemGateway');
  if (/^(?:(?:1|ein(?:e|en|em|er|es)?)\s+)?zentrale\s+(?:kopplung|koppelstelle)$/.test(key)) names.push('SystemGateway');
  const numberedHeading = /^\s*#{1,6}\s*\d+[.)]?\s*/.test(line);
  const centralGatewayCount = numberedHeading ? null : key.match(new RegExp(
    `^${COUNT_TOKEN}\\s+(?:zentrale[rsnm]?\\s+)?gateway(?:s)?\\s*[/+-]?\\s*edge\\s+controller$`,
  ));
  if (centralGatewayCount) {
    const count = Math.min(1000, countValue(centralGatewayCount[1]));
    for (let i = 1; i <= count; i++) names.push(i === 1 ? 'SystemGateway' : `SystemGateway${i}`);
  }
  const standaloneGatewayCount = /\bfsoe\b/i.test(specification)
    && /\bsafety\s*cycle\s*:/i.test(specification)
    && /\bsicherheitssensor(?:en|s)?\b/i.test(specification)
    && /\bsafety[-\s]*aktor(?:en)?\b/i.test(specification)
    ? key.match(new RegExp(`^${COUNT_TOKEN}\\s+gateways?$`)) : null;
  if (standaloneGatewayCount) {
    for (let i = 1; i <= Math.min(1000, countValue(standaloneGatewayCount[1])); i++) {
      names.push(i === 1 ? 'SafetySystemGateway' : `SafetySystemGateway${i}`);
    }
  }
  const gatewayCount = key.match(new RegExp(`^${COUNT_TOKEN}\\s+gateways?\\s+(?:mit|with|ueber|via)\\b`));
  if (gatewayCount) {
    for (let i = 1; i <= Math.min(1000, countValue(gatewayCount[1])); i++) {
      names.push(i === 1 ? 'Gateway' : `Gateway${i}`);
    }
  }
  const embeddedControllerCount = key.match(new RegExp(`\\b${COUNT_TOKEN}\\s+embedded\\s+controllers?\\b`));
  if (embeddedControllerCount) {
    for (let i = 1; i <= Math.min(1000, countValue(embeddedControllerCount[1])); i++) {
      names.push(i === 1 ? "EmbeddedController" : `EmbeddedController${i}`);
    }
  }
  if (/\bgemeinsame steuerung\b/.test(key)) names.push('Steuerung');
  // Preserve a counted physical quantity instead of filling the count from unrelated templates.
  const temperatureCount = key.match(new RegExp(`\\b${COUNT_TOKEN}\\s+(?:temperatur(?:mess)?sensor(?:en|s)?|temperature sensors?|sensor(?:en|s)?\\s+(?:(?:fuer|zur messung von)\\s+temperatur(?:en)?|(?:die\\s+)?temperatur(?:en)?\\s+messen|for\\s+temperatures?))\\b`));
  if (temperatureCount) {
    for (let i = 1; i <= Math.min(1000, countValue(temperatureCount[1])); i++) names.push(`Temperatursensor${i}`);
  }
  const positionSensorCount = key.match(new RegExp(`\\b${COUNT_TOKEN}\\s+positionssensor(?:en|s)?\\b`));
  if (positionSensorCount) {
    for (let i = 1; i <= Math.min(1000, countValue(positionSensorCount[1])); i++) names.push(`Positionssensor${i}`);
  }
  const safetySensorCount = key.match(new RegExp(`\\b${COUNT_TOKEN}\\s+(?:(?:digitale?|digital)\\s+)?(?:sicherheitssensor(?:en|s)?|safety[-\\s]*sensors?)\\b`));
  if (safetySensorCount) {
    for (let i = 1; i <= Math.min(1000, countValue(safetySensorCount[1])); i++) names.push(`Sicherheitssensor${i}`);
  }
  const servoDriveCount = key.match(new RegExp(`\\b${COUNT_TOKEN}\\s+servo(?:antrieb|drive)(?:e|en|s)?\\b`));
  if (servoDriveCount) {
    for (let i = 1; i <= Math.min(1000, countValue(servoDriveCount[1])); i++) names.push(`Servoantrieb${i}`);
  }
  const fanActuatorCount = key.match(new RegExp(`\\b${COUNT_TOKEN}\\s+(?:luefter|fans?)(?:[-\\s]*(?:aktor(?:en)?|actuators?))?\\b`));
  if (fanActuatorCount) {
    for (let i = 1; i <= Math.min(1000, countValue(fanActuatorCount[1])); i++) names.push(`Luefteraktor${i}`);
  }
  const safetyActuatorCount = key.match(new RegExp(`\\b${COUNT_TOKEN}\\s+(?:safety[-\\s]*aktor(?:en)?|sicherheitsaktor(?:en)?|sicherheitsrelevante\\s+aktor(?:en)?|safety[-\\s]*actuators?)\\b`));
  if (safetyActuatorCount) {
    for (let i = 1; i <= Math.min(1000, countValue(safetyActuatorCount[1])); i++) names.push(`SafetyAktor${i}`);
  }
  const valveCount = key.match(new RegExp(`\\b${COUNT_TOKEN}\\s+(?:(?:pwm|proportional)[-\\s]*)?(?:ventilaktor(?:en)?|ventil(?:e|en)?|valves?)\\b`));
  if (valveCount) {
    for (let i = 1; i <= Math.min(1000, countValue(valveCount[1])); i++) names.push(`Ventilaktor${i}`);
  } else if (/\b(?:ventile(?:n)?|valves)\b/.test(key) && Number.isSafeInteger(confirmedActuators) && confirmedActuators! >= 0) {
    for (let i = 1; i <= Math.min(1000, confirmedActuators!); i++) names.push(`Ventilaktor${i}`);
  }
  if (/\b(?:sensor|sensoren)\b/.test(key) && /\bmotorstrom\b/.test(key)) {
    names.push("Motorstromsensor");
  }
  return names;
}

function deviceType(name: string) {
  const key = normalized(name);
  if (key === 'raspberrypi') return 'EmbeddedController';
  if (key.includes("gateway")) return "Gateway";
  if (key.includes("sensor") || key.includes("kamera") || key.includes("camera") || key.includes("radar") || key.includes("lidar")) return "SensorController";
  if (/actuator|aktuator|aktor|servoantrieb|servodrive/.test(key)) return "ActuatorController";
  if (key.includes("plc") || /\bsps\b/.test(key)) return "PLC";
  if (/robot.*controller|motion.*controller/.test(key)) return "RobotController";
  if (/flight.*computer|flugrechner/.test(key)) return "FlightComputer";
  if (/energy.*controller|energie.*controller/.test(key)) return "EnergyController";
  if (/building.*controller|gebaeude.*controller/.test(key)) return "BuildingController";
  if (/embedded.*controller/.test(key)) return "EmbeddedController";
  if (/industrial.*pc/.test(key)) return "IndustrialPC";
  if (key.includes("controller")) return "ECU";
  return "ECU";
}

function protocolFrom(text: string, fallback = 'CAN') {
  const key = normalized(text);
  if (/\blin\b/.test(key)) return "LIN";
  if (key.includes("can fd") || key.includes("canfd")) return "CAN_FD";
  if (key.includes("canopen")) return "CAN";
  if (/\bcan\b/.test(key)) return "CAN";
  if (/\bsome ip\b|\bsomeip\b/.test(key)) return "Ethernet";
  if (key.includes("arinc 429") || key.includes("arinc429")) return "ARINC";
  if (key.includes("mil std 1553") || key.includes("milstd1553")) return "MIL_STD_1553";
  if (key.includes("ethercat")) return "EtherCAT";
  if (key.includes("profinet")) return "ProfiNET";
  if (/\bio\s*link\b/.test(key)) return "IO_LINK";
  if (key.includes("automotive ethernet") || key.includes("ethernet")) return "Ethernet";
  if (key.includes("modbus tcp")) return "ModbusTCP";
  if (key.includes("modbus rtu")) return "ModbusRTU";
  if (/\bspi\b/.test(key)) return "SPI";
  if (/\bi2c\b/.test(key)) return "I2C";
  if (/\buart\b/.test(key)) return "UART";
  if (/\b(?:usb|pcie|rs485|rs232)\b/.test(key)) return key.match(/\b(?:usb|pcie|rs485|rs232)\b/)?.[0].toUpperCase() ?? "Other";
  if (key.includes("opc ua")) return "OPCUA";
  if (/\bmqtt\b/.test(key)) return "MQTT";
  if (/\bwifi\b|wi-fi/.test(key)) return "WiFi";
  if (/\bble\b|bluetooth low energy/.test(key)) return "BLE";
  if (/\bdds\b/.test(key)) return "DDS";
  if (/\b(?:adc|dac|gpio|pwm)\b/.test(key)) return key.match(/\b(?:adc|dac|gpio|pwm)\b/)![0].toUpperCase();
  return fallback;
}

function withoutPlanningLimits(text: string) {
  // Listing available settings does not select those protocols for the model.
  return text.replace(/^- Bus-Teilnehmergrenzen:[^\r\n]*(?:\r?\n|$)/gm, "");
}

export function extractCommunicationSystems(text: string) {
  const key = normalized(withoutPlanningLimits(text));
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
  if (/\bio\s*link\b/.test(key)) systems.push("IO_LINK");
  if (/\bmodbus tcp\b/.test(key)) systems.push("ModbusTCP");
  if (/\bmodbus rtu\b|\bmodbusrtu\b/.test(key)) systems.push("ModbusRTU");
  if (/\bspi\b/.test(key)) systems.push("SPI");
  if (/\bi2c\b/.test(key)) systems.push("I2C");
  if (/\buart\b/.test(key)) systems.push("UART");
  if (/\busb\b/.test(key)) systems.push("USB");
  if (/\bpcie\b/.test(key)) systems.push("PCIe");
  if (/\brs\s*485\b/.test(key)) systems.push("RS485");
  if (/\brs232\b/.test(key)) systems.push("RS232");
  if (/\bopc ua\b/.test(key)) systems.push("OPCUA");
  if (/\bmqtt\b/.test(key)) systems.push("MQTT");
  if (/\bwifi\b|wi-fi/.test(key)) systems.push("WiFi");
  if (/\bble\b|bluetooth low energy/.test(key)) systems.push("BLE");
  if (/\bdds\b/.test(key)) systems.push("DDS");
  for (const technology of ['adc', 'dac', 'gpio', 'pwm']) {
    if (new RegExp(`\\b${technology}\\b`).test(key)) systems.push(technology.toUpperCase());
  }
  return [...new Set(systems)];
}

export function canonicalCommunicationSystem(value: string) {
  const key = normalized(value);
  const compact = key.replace(/\s+/g, "");
  if (/^(adc|dac|gpio|pwm)$/.test(compact)) return compact.toUpperCase();
  if (/\blin\b/.test(key) || compact === "lin") return "LIN";
  if (/\bcan fd\b|\bcanfd\b/.test(key) || compact === "canfd") return "CAN_FD";
  if (/\bflexray\b/.test(key)) return "FlexRay";
  if (/\bautomotive ethernet\b|\bethernet\b/.test(key) || compact === "eth") return "Ethernet";
  if (/\bsome ip\b/.test(key) || compact === "someip") return "SOME_IP";
  if (/\barinc 429\b/.test(key) || compact === "arinc429") return "ARINC";
  if (/\bmil std 1553\b/.test(key) || compact === "milstd1553") return "MIL_STD_1553";
  if (/\bethercat\b/.test(key)) return "EtherCAT";
  if (/\bprofinet\b/.test(key)) return "ProfiNET";
  if (/\bio\s*link\b/.test(key) || compact === "iolink") return "IO_LINK";
  if (/\bmodbus tcp\b/.test(key) || compact === "modbustcp") return "ModbusTCP";
  if (/\bmodbus rtu\b/.test(key) || compact === "modbusrtu") return "ModbusRTU";
  if (/\bspi\b/.test(key)) return "SPI";
  if (/\bi2c\b/.test(key)) return "I2C";
  if (/\buart\b/.test(key)) return "UART";
  if (/\busb\b/.test(key)) return "USB";
  if (/\bpcie\b/.test(key)) return "PCIe";
  if (/\brs\s*485\b/.test(key)) return "RS485";
  if (/\brs232\b/.test(key)) return "RS232";
  if (/\bopc ua\b/.test(key) || compact === "opcua") return "OPCUA";
  if (/\bmqtt\b/.test(key)) return "MQTT";
  if (/\bwifi\b|wi-fi/.test(key)) return "WiFi";
  if (/\bble\b|bluetooth low energy/.test(key)) return "BLE";
  if (/\bdds\b/.test(key)) return "DDS";
  if (/\btrdp\b/.test(key)) return "TRDP";
  if (/\betb\b/.test(key)) return "ETB";
  if (/\bwtb\b/.test(key)) return "WTB";
  if (/\bmvb\b/.test(key)) return "MVB";
  if (/\bcan\b/.test(key)) return "CAN";
  return "";
}

const COMMUNICATION_SYSTEM_PATTERN = "(?:automotive\\s+ethernet|ethernet|some\\s*ip|someip|can\\s*fd|canfd|can|lin|arinc\\s*429|arinc429|mil\\s*std\\s*1553|milstd1553|ethercat|profinet|modbus\\s*rtu|modbusrtu|modbus\\s*tcp|io\\s*link|iolink|spi|i2c|uart|usb|pcie|rs485|rs232|opc\\s*ua|adc|dac|gpio|pwm)";

function looksLikeBitrateSuffix(value: string) {
  return /^\s*(?:k?bit|m?bit|kbps|mbps|baud|bd|ms|byte|bytes|b)\b/i.test(value);
}

export function extractCommunicationSystemCounts(text: string): Record<string, number> {
  const counts: Record<string, number> = {};
  const ethernetSegments: Record<string, number> = {};
  const countBeforePattern = new RegExp(`\\b${COUNT_TOKEN}\\s*(?:x\\s*)?${COMMUNICATION_SYSTEM_PATTERN}\\b`, "gi");
  const countAfterPattern = new RegExp(`\\b${COMMUNICATION_SYSTEM_PATTERN}\\b\\s*(?:bus(?:se)?|netz(?:e)?|segmente?|anzahl)?\\s*(?::|=|-)?\\s*${COUNT_TOKEN}\\b`, "gi");
  const qualifiedEthernetSegments = new RegExp(`\\b${COUNT_TOKEN}\\s+(industrial\\s+ethernet|ethernet\\s+backbone)\\s+segmente?\\b`, "gi");

  specificationBody(text).split(/\r?\n/).forEach((line) => {
    const source = normalized(line.replace(/^\s*#{1,6}\s+/, "").replace(/^\s*\d+[.)]\s+/, ""));
    for (const match of source.matchAll(qualifiedEthernetSegments)) {
      const category = match[2].startsWith("industrial") ? "industrial" : "backbone";
      ethernetSegments[category] = Math.max(ethernetSegments[category] ?? 0, countValue(match[1] ?? ""));
    }
    for (const match of source.matchAll(countBeforePattern)) {
      if (/(?:\brs|\barinc|\bstd)\s*$/.test(source.slice(0, match.index ?? 0))) continue;
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

  if (Object.keys(ethernetSegments).length) {
    counts.Ethernet = Math.max(counts.Ethernet ?? 0, Object.values(ethernetSegments).reduce((sum, count) => sum + count, 0));
  }

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
  if (/robotics|robotik|roboter|robot.*controller|\bros\b|manipulator|motion planner/.test(key)) return "robotics_ros";
  if (/industrial|plc|profinet|ethercat|sicherheitssystem|sicherheitssteuerung/.test(key)) return "industrial_automation";
  if (/aerospace|arinc|avionik/.test(key)) return "aerospace";
  if (/\brail\b|bahn|zug|train/.test(key)) return "rail";
  if (/marine|schiff|ship|vessel|maritim/.test(key)) return "marine";
  if (/building automation|gebaeude|gebäude|knx|bacnet|hlk/.test(key)) return "building_automation";
  if (/\benergy\b|energie|microgrid|wechselrichter|schaltanlage|transformator/.test(key)) return "energy";
  if (/generic networking|router|switch|firewall|loadbalancer|vpn/.test(key)) return "generic_networking";
  if (/automotive|fahrzeug|ecu|can fd|kamera|camera|radar|lidar|umfeld/.test(key)) return "automotive";
  if (/\bembedded\b|\bi2c\b|\bspi\b|\buart\b|\bpcie\b|\busb\b/.test(key)) return "embedded_systems";
  return "generic";
}

const DOMAIN_EVIDENCE_RULES: Array<{ domain: string; markers: RegExp[] }> = [
  { domain: "rail", markers: [/\bbogie/i, /drehgestell/i, /\baxle/i, /pantograph/i, /stromabnehmer/i, /wayside/i, /eventrecorder/i, /passengerinformation/i, /couplingcontrol/i, /signalling/i] },
  { domain: "automotive", markers: [/kombiinstrument/i, /headupdisplay/i, /abgasnachbehandlung/i, /batteriemanagement/i, /motorsteuerung/i, /getriebesteuerung/i, /fahrerassistenz/i, /parkassistenz/i, /keylessentry/i, /bordnetzmanagement/i] },
  { domain: "industrial_automation", markers: [/\bplc\b/i, /profinet/i, /ethercat/i, /fertigungs/i, /foerder/i, /servo/i, /sicherheitssystem/i, /sicherheitssteuerung/i, /deterministisch/i] },
  { domain: "aerospace", markers: [/arinc/i, /avionik/i, /flightcontrol/i, /landinggear/i, /autopilot/i] },
  { domain: "energy", markers: [/microgrid/i, /wechselrichter/i, /schaltanlage/i, /transformator/i, /gridcontrol/i] },
  { domain: "marine", markers: [/vessel/i, /schiff/i, /marine/i, /nmea/i] },
  { domain: "building_automation", markers: [/\bknx\b/i, /bacnet/i, /gebaeude/i, /gebäude/i, /buildingautomation/i] },
  { domain: "robotics_ros", markers: [/\bros2?\b/i, /robotik/i, /roboter/i, /robot\s*controller/i, /\bdds\b/i, /manipulator/i, /motionplanner/i] },
];

/** Detect strong domain evidence without allowing a wizard header to decide the result. */
export function engineeringDomainEvidence(text: string): EngineeringDomainEvidence {
  const body = specificationBody(text).replace(/^\s*-?\s*Industrie\s*:[^\r\n]*$/gim, "");
  const scored = DOMAIN_EVIDENCE_RULES
    .map((rule) => ({
      domain: rule.domain,
      markers: rule.markers.flatMap((marker) => body.match(marker)?.[0] ?? []),
    }))
    .map((item) => ({ ...item, score: new Set(item.markers.map((marker) => normalized(marker))).size }))
    .sort((left, right) => right.score - left.score || left.domain.localeCompare(right.domain));
  const best = scored[0];
  const runnerUp = scored[1]?.score ?? 0;
  if (!best || best.score < 2 || best.score === runnerUp) return { domain: "generic", confidence: 0, markers: [] };
  return {
    domain: best.domain,
    confidence: Math.min(1, 0.45 + best.score * 0.08 + Math.max(0, best.score - runnerUp) * 0.04),
    markers: [...new Set(best.markers)].slice(0, 6),
  };
}

function numeric(value: string | undefined) {
  if (!value) return undefined;
  const result = Number(value.replace(",", "."));
  return Number.isFinite(result) ? result : undefined;
}

function rangeFrom(text: string) {
  const match = text
    .replace(/−/g, "-")
    .match(/(-?\d+(?:[,.]\d+)?)\s*(?:°\s*c|a|bar|rpm|u\s*\/\s*min|\/\s*min)?\s*(?:bis|–|—|…|\.\.\.)\s*\+?(-?\d+(?:[,.]\d+)?)/i);
  return { min: numeric(match?.[1]), max: numeric(match?.[2]) };
}

function factorFrom(text: string, unit: string | undefined) {
  const match = text.match(/(?:auflösung|aufloesung|schrittweite)\s*:?\s*(-?\d+(?:[,.]\d+)?)/i);
  const explicit = numeric(match?.[1]);
  if (explicit !== undefined) return explicit;
  // Compact device specifications put resolution after the range, separated
  // by a comma ("0…10 bar, 0,01 bar, 20 ms"). Never read the range as resolution.
  // A decimal comma inside a value is not a specification separator:
  // "Auflösung beispielsweise: 0,1 A" must never become "1 A".
  const compact = text.match(/(?:^|(?<!\d)[,;])\s*(\d+(?:[,.]\d+)?)\s*(?:°\s*c|bar|rpm|a)\s*(?=[,;]|$)/i);
  const resolution = numeric(compact?.[1]);
  if (resolution !== undefined && resolution > 0) return resolution;
  return unit === "degC" || unit === "A" ? 0.1 : 1;
}

function unitFrom(text: string) {
  if (/°\s*c/i.test(text)) return "degC";
  if (/\bbar\b/i.test(text)) return "bar";
  if (/\bl\s*\/\s*min\b/i.test(text)) return "l/min";
  if (/\brpm\b|u\s*\/\s*min|\/\s*min/i.test(text)) return "rpm";
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
  if (key.includes("durchfluss") || key.includes("flow")) return "Durchfluss";
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
  if (key.includes("safetycommand") || key.includes("sicherheitsbefehl") || key.includes("sicherheitszustand")) {
    return { min: 0, max: 1, unit: "code" };
  }
  if (key.includes("temperatur")) return { min: -40, max: 215, unit: "degC" };
  if (key.includes("druck")) return { min: 0, max: 250, unit: "bar" };
  if (key.includes("durchfluss") || key.includes("flow")) return { min: 0, max: 1000, unit: "l/min" };
  if (key.includes("drehzahl")) return { min: 0, max: 8000, unit: "rpm" };
  if (key.includes("drehmoment")) return { min: -10000, max: 10000, unit: "Nm" };
  if (key.includes("strom")) return { min: -200, max: 200, unit: "A" };
  if (key.includes("spannung")) return { min: 0, max: 1000, unit: "V" };
  if (key.includes("winkel")) return { min: -180, max: 180, unit: "deg" };
  if (key.includes("kraft")) return { min: -100000, max: 100000, unit: "N" };
  if (key.includes("federweg")) return { min: -300, max: 300, unit: "mm" };
  if (key.includes("radlast")) return { min: 0, max: 100000, unit: "N" };
  if (key.includes("reifenverschleiß")) return { min: 0, max: 100, unit: "%" };
  if (key.includes("drehrate")) return { min: -1000, max: 1000, unit: "deg/s" };
  if (key.includes("luftfeuchtigkeit")) return { min: 0, max: 100, unit: "%" };
  if (key.includes("co2") || key.includes("kohlendioxid")) return { min: 0, max: 10000, unit: "ppm" };
  if (key.includes("präsenz") || key.includes("praesenz")) return { min: 0, max: 1, unit: "state" };
  if (/\bph wert\b/.test(key)) return { min: 0, max: 14, unit: "pH" };
  if (key.includes("leitfähigkeit") || key.includes("leitfaehigkeit")) return { min: 0, max: 200000, unit: "uS/cm" };
  if (key.includes("füllstand") || key.includes("fuellstand")) return { min: 0, max: 100, unit: "%" };
  if (key.includes("abstand")) return { min: 0, max: 1000, unit: "m" };
  if (key.includes("beschleunigung")) return { min: -200, max: 200, unit: "m/s²" };
  if (key.includes("geschwindigkeit") || key.includes("speed")) {
    return { min: 0, max: 300, unit: "km/h" };
  }
  if (key.includes("position")) return { min: 0, max: 100, unit: "%" };
  return { min: undefined, max: undefined, unit: undefined };
}

export function engineeringGenerationMode(text: string): 'REAL_PROJECT' | 'EXAMPLE_PROJECT' {
  const explicit = text.match(/^- Generierungsmodus:\s*(REAL_PROJECT|EXAMPLE_PROJECT)\s*$/mi)?.[1]?.toUpperCase();
  if (explicit === 'REAL_PROJECT' || explicit === 'EXAMPLE_PROJECT') return explicit;
  const withoutNegatedExamples = text.replace(/\b(?:kein(?:e|en)?|not?\s+(?:an?\s+)?|ohne)\s+(?:Musterprojekt|Beispielprojekt|example project|sample project)\b/gi, '');
  return /\b(?:Musterprojekt|Beispielprojekt|example project|sample project|Skalierungsziel)\b/i.test(withoutNegatedExamples) ? 'EXAMPLE_PROJECT' : 'REAL_PROJECT';
}

function explicitDeviceConnections(text: string): Record<string, string> {
  const raw = text.match(/^- Geräteanschlüsse:\s*(\{[^\r\n]*\})\s*$/m)?.[1];
  if (!raw) return {};
  let values: Record<string, string>;
  try { values = JSON.parse(raw); } catch { return {}; }
  if (!values || Array.isArray(values) || typeof values !== 'object') return {};
  return Object.fromEntries(Object.entries(values).map(([name, technology]) => {
    const canonical = canonicalCommunicationSystem(String(technology));
    if (!canonical) return [normalizeHardwareName(name).toLocaleLowerCase('de'), 'Other'];
    return [normalizeHardwareName(name).toLocaleLowerCase('de'), canonical];
  }));
}

function explicitDeviceOwners(text: string): Record<string, string> {
  const raw = text.match(/^- Gerätezuordnungen:\s*(\{[^\r\n]*\})\s*$/m)?.[1];
  if (!raw) return {};
  let values: Record<string, string>;
  try { values = JSON.parse(raw); } catch { return {}; }
  if (!values || Array.isArray(values) || typeof values !== 'object'
      || Object.values(values).some(value => typeof value !== 'string')) return {};
  return Object.fromEntries(Object.entries(values).map(([name, owner]) => [
    normalizeHardwareName(name).toLocaleLowerCase('de'),
    normalizeHardwareName(owner),
  ]));
}

export function extractEngineeringSpecification(
  text: string,
  overrides: Partial<EngineeringHardwareCounts> = {},
  domainOverride?: string,
  completenessFirst = false,
): ExtractedEngineeringSpecification {
  text = withoutPlanningLimits(text);
  const explicitMode = text.match(/^- Generierungsmodus:\s*(REAL_PROJECT|EXAMPLE_PROJECT)\s*$/mi)?.[1]?.toUpperCase();
  const legacyConfirmed = !explicitMode && /per Wizard-Uebernehmen bestaetigt/.test(text);
  const exampleRequested = engineeringGenerationMode(text) === 'EXAMPLE_PROJECT';
  const measurements = sensorMeasurementSelections(text);
  const lines = specificationBody(text).replace(/^- Sensor-Messgrößen:[^\r\n]*$/gm, '').split(/\r?\n/);
  const confirmedCounts = { ...confirmedHardwareCounts(text), ...overrides };
  const grouped = groupedHardwareNames(lines);
  const groupedLineIndexes = new Set(grouped.map((item) => item.index));
  const occurrences = [...lines.flatMap((line, index): HardwareOccurrence[] => {
    if (groupedLineIndexes.has(index)) return [];
    if (/^\s*[-*]?\s*(?:gemischte|mixed)\s+(?:PLC|SPS)[-–,]/i.test(line)) return [];
    const singularControllers = singularControllerHardwareNames(line);
    const names = singularControllers.length ? [] : [hardwareName(headingLabel(line)), ...inlineHardwareNames(line), ...naturalLanguageHardwareNames(line), ...impliedHardwareNames(line, confirmedCounts.actuators, text)].filter(Boolean);
    const candidates = [...names.map(name => ({ index, name })), ...declaredHardwareNames(line).map(item => ({ index, ...item })), ...singularControllers.map(item => ({ index, ...item }))];
    return [...new Map(candidates.map(item => [normalized(normalizeHardwareName(item.name)), item])).values()];
  }), ...grouped].sort((left, right) => left.index - right.index);
  const contexts = new Map<string, { name: string; lines: string[]; declaredType?: string; declaredInterface?: string }>();
  occurrences.forEach((occurrence, occurrenceIndex) => {
    const nextIndex = occurrences[occurrenceIndex + 1]?.index ?? lines.length;
    const sectionBoundary = lines.findIndex((line, index) => index > occurrence.index && index < nextIndex
      && !lines[index - 1]?.trim()
      && /^\s*(?:#{1,6}\s+)?[^-*].*:\s*$/.test(line));
    const contextEnd = sectionBoundary >= 0 ? sectionBoundary : nextIndex;
    const key = normalized(normalizeHardwareName(occurrence.name));
    const existing = contexts.get(key) ?? { name: occurrence.name, lines: [] };
    if (occurrence.declaredType) existing.declaredType = occurrence.declaredType;
    if (occurrence.declaredInterface) existing.declaredInterface = occurrence.declaredInterface;
    existing.lines.push(...lines.slice(occurrence.index, Math.max(occurrence.index + 1, contextEnd)));
    contexts.set(key, existing);
  });

  // Explicit choices can resolve count-only Sensor1… slots without inventing a function.
  for (const name of Object.keys(measurements)) {
    const key = normalized(normalizeHardwareName(name));
    if (!contexts.has(key) && /^Sensor\d+$/.test(name)) {
      contexts.set(key, { name, lines: [], declaredType: 'SensorController' });
    }
  }

  const inferredDomain = domainOverride || domainFrom(text);
  const modelType = domainOverride || extractProjectModelType(text, inferredDomain);
  const domain = domainOverride || modelType || inferredDomain;
  const communicationSystems = extractCommunicationSystems(text);
  const unconfiguredPi = /\b(?:raspberry|rasberry|rasperry|respary)[\s-]*pi\b|\braspi\b/i.test(text) && !communicationSystems.length;
  const interfaceType = unconfiguredPi ? 'Other' : protocolFrom(text.replace(/^- Geräteanschlüsse:[^\r\n]*$/gm, ''), (exampleRequested || legacyConfirmed) && domain === 'automotive' ? 'CAN' : 'Other');
  const communicationSystemCounts = extractCommunicationSystemCounts(text);
  const networkArchitecture = extractNetworkArchitectureMode(text);
  const deviceConnections = {
    ...explicitCommunicationAssignments(text, [...contexts.values()].map(entry => entry.name)),
    ...explicitDeviceConnections(text),
  };
  const deviceOwners = explicitDeviceOwners(text);
  const safetyProfile = /\bfsoe\b/i.test(text) ? 'FSoE' : undefined;
  const safetyCycleMs = numeric(text.match(/\bSafety\s*Cycle\s*:\s*(\d+(?:[,.]\d+)?)\s*ms\b/i)?.[1]);
  const deviceSpecificationRaw = text.match(/^- Geräte-Spezifikationen:\s*(\{[^\r\n]*\})\s*$/m)?.[1];
  let deviceSpecifications: Record<string, string> = {};
  if (deviceSpecificationRaw) {
    const parsed: unknown = JSON.parse(deviceSpecificationRaw);
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object' || Object.values(parsed).some(value => typeof value !== 'string')) {
      throw new Error('Ungültige Gerätespezifikationen.');
    }
    deviceSpecifications = parsed as Record<string, string>;
  }
  const declaredControllers = [...contexts.values()].filter(entry =>
    isEngineeringControllerDevice(entry.declaredType ?? deviceType(entry.name))).map(entry => normalizeHardwareName(entry.name));
  const recognizedChains = [...contexts.values()].map((entry, index): ExtractedEngineeringChain => {
    const hardwareName = normalizeHardwareName(entry.name);
    const context = [deviceSpecifications[hardwareName], ...entry.lines.map((line) => cleanLabel(line))].filter(Boolean).join("; ");
    const declaredType = entry.declaredType ?? deviceType(entry.name);
    const selectedOwner = deviceOwners[hardwareName.toLocaleLowerCase('de')];
    const confirmedOwner = selectedOwner && declaredControllers.some(owner => normalized(owner) === normalized(selectedOwner))
      ? declaredControllers.find(owner => normalized(owner) === normalized(selectedOwner)) : undefined;
    const functionalOwner = ['SensorController', 'ActuatorController'].includes(declaredType)
      ? confirmedOwner ?? explicitFunctionalOwner(entry.name, declaredControllers, lines.join('\n')) : undefined;
    const countedTemperature = hardwareName.match(/^Temperatursensor(\d+)$/);
    const explicitMeasurementId = Object.entries(measurements)
      .find(([name]) => normalized(normalizeHardwareName(name)) === normalized(hardwareName))?.[1];
    const measurement = declaredType === 'SensorController' ? SENSOR_MEASUREMENTS.find(item =>
      item.id === explicitMeasurementId || (!explicitMeasurementId && item.match.test(`${hardwareName} ${context}`))) : undefined;
    const safetyEndpoint = /safety|sicher/.test(normalized(`${hardwareName} ${context}`));
    const safetyParticipant = safetyEndpoint || Boolean(safetyProfile && safetyCycleMs);
    const derivedSignal = signalName(hardwareName, context);
    const complexMeasurement = measurement && derivedSignal !== 'ObjektErkannt' && 'dataComplexity' in measurement ? measurement : undefined;
    const modeledMeasurement = measurement && (!('dataComplexity' in measurement) || complexMeasurement) ? measurement : undefined;
    const measurementDefinesIdentity = Boolean(modeledMeasurement
      && (explicitMeasurementId || modeledMeasurement.id === 'safety_state' || 'dataComplexity' in modeledMeasurement));
    const signal = measurementDefinesIdentity ? `${modeledMeasurement!.label}_${identifier(hardwareName)}` : countedTemperature ? `Temperatur${countedTemperature[1]}`
      : declaredType === 'ActuatorController' && safetyEndpoint ? 'SafetyCommand'
        : hardwareName === 'RaspberryPi' ? 'RaspberryPiStatus' : derivedSignal;
    const defaults = generatedPhysicalDefaults(modeledMeasurement?.label ?? signal);
    const unit = modeledMeasurement?.unit ?? unitFrom(context) ?? defaults.unit;
    const factor = factorFrom(context, unit);
    const range = rangeFrom(context);
    const cycleMs = numeric(context.match(/(?:^|[,;\s])(\d+(?:[,.]\d+)?)\s*ms\b/i)?.[1])
      ?? (safetyParticipant ? safetyCycleMs : undefined)
      ?? (complexMeasurement && 'defaultCycleMs' in complexMeasurement ? complexMeasurement.defaultCycleMs : undefined) ?? 10;
    const objectDetectionSignal = signal === "ObjektErkannt";
    const minValue = range.min ?? (objectDetectionSignal ? 0 : defaults.min);
    const maxValue = range.max ?? (objectDetectionSignal ? 1 : defaults.max);
    const hardwareId = identifier(hardwareName);
    const explicitConnection = deviceConnections[hardwareName.toLocaleLowerCase('de')];
    const mayUseProjectInterface = isEngineeringControllerDevice(declaredType)
      || declaredType === "Gateway"
      || (safetyParticipant && Boolean(safetyProfile) && communicationSystems.length === 1)
      || exampleRequested
      || (legacyConfirmed && communicationSystems.length === 1);
    const contextualInterfaceType = entry.declaredInterface ?? protocolFrom(context, mayUseProjectInterface ? interfaceType : "Other");
    const chainInterfaceType = explicitConnection || (contextualInterfaceType === "CAN" && /kamera|camera|radar|lidar|umfeld|objekt/i.test(`${hardwareName} ${context}`)
      ? "Ethernet"
      : contextualInterfaceType);
    const dataType = (minValue ?? 0) < 0 ? "signed" : "unsigned";
    const lengthBits = complexMeasurement && 'payloadBytes' in complexMeasurement ? complexMeasurement.payloadBytes * 8 : generatedArchitectureBitLength({
      signalName: signal,
      hardwareName,
      interfaceType: chainInterfaceType,
      cycleMs,
      minValue,
      maxValue,
      factor,
      offset: 0,
      unit,
      dataType,
    });
    const baseArchitectureMetadata = signalArchitectureMetadata({ signalName: signal, hardwareName,
      interfaceType: chainInterfaceType, cycleMs, dataType, lengthBits, startBit: 0,
      byteOrder: 'little_endian', factor, offset: 0, unit, minValue, maxValue });
    const architectureMetadata = complexMeasurement ? {
      ...baseArchitectureMetadata,
      semantic: { ...baseArchitectureMetadata.semantic, semantic_type: complexMeasurement.semanticType,
        unit: 'not_applicable', assumptions: ['Payloadgröße und Zyklus sind bestätigungspflichtige Modellannahmen.'] },
      data: { payload_bytes: complexMeasurement.payloadBytes },
      configuration: { ...baseArchitectureMetadata.configuration, data_complexity: complexMeasurement.dataComplexity,
        encoding_type: 'raw' },
      quality: { ...baseArchitectureMetadata.quality, value_domain_complete: true },
    } : baseArchitectureMetadata;
    return {
      hardware_name: hardwareName,
      hardware_description: context.slice(0, 1000),
      device_type: declaredType,
      ...(complexMeasurement ? { data_complexity: complexMeasurement.dataComplexity,
        payload_element_type: complexMeasurement.elementType } : {}),
      function_name: modeledMeasurement && (explicitMeasurementId || modeledMeasurement.id === 'safety_state')
        ? `${hardwareId}_${modeledMeasurement.label}Erfassung` : functionName(hardwareName, entry.lines, entry.name),
      function_description: `Aus Nutzerspezifikation abgeleitete Funktion. ${context}`.slice(0, 1000),
      interface_name: `${hardwareId}_${chainInterfaceType}`,
      interface_type: chainInterfaceType,
      message_name: `${hardwareId}Data`,
      message_id_hex: `0x${(0x180 + index).toString(16).toUpperCase()}`,
      direction: "tx",
      cycle_ms: cycleMs,
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
      ...architectureMetadata,
      configuration: { ...architectureMetadata.configuration,
        ...(modeledMeasurement ? { sensor_measurement: modeledMeasurement.id,
          measurement_source: explicitMeasurementId ? 'explicit_user_selection' : 'semantic_device_role' } : {}),
        ...(safetyProfile && safetyParticipant ? { safety_profile: safetyProfile,
          safety_cycle_ms: cycleMs, safety_source: 'explicit_user_specification' } : {}),
        ...(declaredType === 'ActuatorController' && safetyEndpoint ? {
          actuator_command_template: { source: 'wizard-safety-actuator-v1', length_bits: 1,
            data_type: 'unsigned', unit: 'code', factor: 1, min_value: 0, max_value: 1,
            semantic: { semantic_type: 'BOOLEAN', meaning: 'Sicherer Stopp angefordert' },
            data: { enum_values: { RUN: 0, SAFE_STOP: 1 }, default_value: 'RUN' } },
        } : {}),
        ...(explicitConnection ? { connection_source: 'explicit_device_connection' } : {}),
        ...(functionalOwner ? { functional_owner: functionalOwner, functional_owner_source: 'explicit_user_statement' } : {}) },
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
    completenessFirst || /System- und Funktionsvollstaendigkeit hat Vorrang vor den Hardware-Sollwerten/i.test(text),
    exampleRequested || legacyConfirmed,
  );

  return {
    chains: packEngineeringChains(
      expanded.chains.map((chain) => ({ ...chain, hardware_name: normalizeHardwareName(chain.hardware_name) })),
    ),
    domain,
    modelType,
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

export function hardwareTargetsAreMinimums(text: string) {
  return /Vollstaendigkeitsprinzip:\s*System- und Funktionsvollstaendigkeit hat Vorrang vor den Hardware-Sollwerten;\s*diese sind Mindestumfang, keine Obergrenze/i.test(text);
}

type ConfirmedClusterGraph = Array<{
  network_id?: string;
  network_label?: string;
  bus_name?: string;
  controllers?: Array<{ ecu?: string; device_type?: 'Gateway'; sensors?: string[]; actuators?: string[] }>;
}>;

/** The reviewed graph owns device identities; catalog expansion must not replace them. */
export function reconcileConfirmedGraphDevices(spec: ExtractedEngineeringSpecification, prompt: string) {
  const raw = prompt.match(/^- Systemcluster-Graph:\s*(\[[^\r\n]*\])\s*$/m)?.[1];
  if (!raw) return spec.chains;
  const graph = JSON.parse(raw) as ConfirmedClusterGraph;
  if (!Array.isArray(graph)) throw new Error("Der bestätigte Systemcluster-Graph ist kein Array.");
  const keyOf = (name: string) => normalizeHardwareName(name).toLocaleLowerCase("de");
  const confirmedConnections = explicitDeviceConnections(prompt);
  const desired = new Map<string, { name: string; role: ArchitectureTemplate["deviceType"]; owner?: string }>();
  const add = (name: string | undefined, role: ArchitectureTemplate["deviceType"], owner?: string) => {
    if (typeof name !== "string" || !name.trim()) throw new Error("Ein bestätigter Graph-Teilnehmer hat keinen Namen.");
    const key = keyOf(name);
    const previous = desired.get(key);
    if (previous && (previous.name !== name.trim() || previous.role !== role || previous.owner !== owner)) {
      throw new Error(`Mehrdeutige Geräteidentität im bestätigten Graph: ${name}`);
    }
    desired.set(key, { name: name.trim(), role, owner });
  };
  for (const cluster of graph) {
    for (const controller of cluster.controllers ?? []) {
      if (controller.device_type && controller.device_type !== 'Gateway') throw new Error('Unbekannte explizite Controllerrolle im bestätigten Graph.');
      const existingController = spec.chains.find((chain) =>
        keyOf(chain.hardware_name) === keyOf(controller.ecu ?? '') && isEngineeringControllerDevice(chain.device_type));
      add(controller.ecu, controller.device_type === 'Gateway' ? 'Gateway'
        : (existingController?.device_type as ArchitectureTemplate["deviceType"] | undefined) ?? controllerDeviceTypeForModel(spec.modelType));
      for (const name of controller.sensors ?? []) add(name, "SensorController", controller.ecu);
      for (const name of controller.actuators ?? []) add(name, "ActuatorController", controller.ecu);
    }
  }
  const catalog = architectureTemplates(spec.domain);
  const confirmedCoverageTemplate = (device: { name: string; role: ArchitectureTemplate["deviceType"]; owner?: string }) => {
    if (!device.owner || (device.role !== "SensorController" && device.role !== "ActuatorController")) return undefined;
    const ownerKey = keyOf(device.owner);
    const ownerRole = desired.get(ownerKey)?.role;
    const knownOwner = spec.chains.find((chain) => keyOf(chain.hardware_name) === ownerKey && chain.device_type === ownerRole);
    const ownerTemplate = catalog.find((item) => keyOf(item.hardwareName) === ownerKey && item.deviceType === ownerRole);
    const owner = knownOwner ?? (ownerTemplate ? chainFromTemplate(ownerTemplate, 0, spec.domain) : undefined);
    if (!owner) return undefined;
    const roles = device.role === "SensorController" ? SENSOR_COVERAGE_ROLES : ACTUATOR_COVERAGE_ROLES;
    for (const [index, [role]] of roles.entries()) {
      const prefix = `${normalizeHardwareName(device.owner)}${role}`;
      if (!keyOf(device.name).startsWith(keyOf(prefix))) continue;
      const suffix = normalizeHardwareName(device.name).slice(prefix.length).toUpperCase();
      if (!/^[A-Z]{0,3}$/.test(suffix)) continue;
      // Restore the same reviewed coverage definition even when a new count-based
      // catalogue expansion distributed the supplemental endpoints differently.
      const generation = [...suffix].reduce((value, char) => value * 26 + char.charCodeAt(0) - 64, 0);
      return supplementalEndpointTemplate(device.role, owner, generation * roles.length + index);
    }
    return undefined;
  };
  const used = new Set<string>();
  const result: ExtractedEngineeringChain[] = [];
  for (const [key, device] of desired) {
    const matches = spec.chains.filter((chain) => keyOf(chain.hardware_name) === key && chain.device_type === device.role);
    const explicitConnection = confirmedConnections[key];
    if (matches.length) {
      result.push(...matches.map((chain) => ({ ...chain, hardware_name: device.name,
        ...(explicitConnection ? {
          interface_type: explicitConnection,
          interface_name: `${normalizeHardwareName(device.name)}_${explicitConnection}`,
        } : {}),
        configuration: { ...chain.configuration,
          ...(device.owner ? { functional_owner: device.owner } : {}),
          ...(explicitConnection ? { connection_source: 'explicit_device_connection' } : {}) } })));
    } else {
      const template = catalog.find((item) => keyOf(item.hardwareName) === key && item.deviceType === device.role)
        ?? confirmedCoverageTemplate(device);
      const chain = chainFromTemplate({ ...(template ?? {
        deviceType: device.role, signalName: `${identifier(device.name)}Value`,
        interfaceType: spec.interfaceType, cycleMs: 100, minValue: 0, maxValue: 255, factor: 1,
      }), hardwareName: device.name, functionalOwner: device.owner }, result.length, spec.domain);
      result.push({ ...chain,
        ...(explicitConnection ? {
          interface_type: explicitConnection,
          interface_name: `${normalizeHardwareName(device.name)}_${explicitConnection}`,
        } : {}),
        hardware_description: template
        ? `Bestätigter Graph-Teilnehmer; Parameter aus dem ${spec.domain}-Katalog.`
        : "Bestätigter Graph-Teilnehmer; generisches, vor Übernahme zu prüfendes Parametermodell (keine physikalische Zusicherung).",
        configuration: { ...chain.configuration, specification_source: "CONFIRMED_CLUSTER_GRAPH",
          ...(explicitConnection ? { connection_source: 'explicit_device_connection' } : {}),
          parameter_quality: template ? "DOMAIN_TEMPLATE" : "GENERIC_ESTIMATE" } });
    }
    used.add(key);
  }
  const roleKey = (role: string) => role === "SensorController" ? "sensors" : role === "ActuatorController"
    ? "actuators" : role === "Gateway" ? "gateways" : "ecus";
  const counts = { sensors: 0, actuators: 0, ecus: 0, gateways: 0 };
  for (const device of desired.values()) counts[roleKey(device.role)] += 1;
  const confirmed = confirmedHardwareCounts(prompt);
  const minimumTargets = hardwareTargetsAreMinimums(prompt);
  for (const key of ["sensors", "actuators", "ecus", "gateways"] as const) {
    if (!minimumTargets && confirmed[key] !== undefined && counts[key] > confirmed[key]) {
      throw new Error(`Bestätigter Graph überschreitet Hardware-Sollwert ${key}: ${counts[key]} > ${confirmed[key]}`);
    }
  }
  // A graph can cover selected clusters only. Retain other devices up to the
  // confirmed counts; replace inferred surplus of the same role, never gateways.
  const retained = new Set<string>();
  for (const chain of spec.chains) {
    const key = keyOf(chain.hardware_name);
    if (used.has(key)) continue;
    const role = roleKey(chain.device_type);
    if (!retained.has(key)) {
      if (counts[role] >= (confirmed[role] ?? spec.targetCounts[role])) continue;
      retained.add(key); counts[role] += 1;
    }
    result.push(chain);
  }
  return result;
}

function confirmedBusTechnology(network: string) {
  return canonicalCommunicationSystem(network);
}

export function applyConfirmedClusterGraph(chains: ExtractedEngineeringChain[], prompt: string) {
  const raw = prompt.match(/^- Systemcluster-Graph:\s*(\[[^\r\n]*\])\s*$/m)?.[1];
  if (!raw) return chains;
  let graph: ConfirmedClusterGraph;
  try {
    graph = JSON.parse(raw) as ConfirmedClusterGraph;
  } catch {
    throw new Error("Der bestätigte Systemcluster-Graph ist kein gültiges JSON-Array.");
  }
  if (!Array.isArray(graph)) throw new Error("Der bestätigte Systemcluster-Graph ist kein Array.");
  const assignedBus = new Map<string, { technology: string; networkRef: string }>();
  const localEndpointNetwork = new Map<string, { controller: string; networkRef: string }>();
  for (const cluster of graph) {
    const technology = confirmedBusTechnology(`${cluster.network_id ?? ""} ${cluster.network_label ?? ""}`);
    if (!technology) continue;
    const networkRef = cluster.bus_name || cluster.network_label || cluster.network_id || `${technology}_network`;
    for (const controller of cluster.controllers ?? []) {
      if (controller.ecu) {
        assignedBus.set(normalizeHardwareName(controller.ecu).toLocaleLowerCase("de"), { technology, networkRef });
      }
      const controllerSlug = normalizeHardwareName(controller.ecu || "controller")
        .toLocaleLowerCase("de")
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/(^-|-$)/g, "");
      for (const name of [...(controller.sensors ?? []), ...(controller.actuators ?? [])]) {
        const key = normalizeHardwareName(name).toLocaleLowerCase("de");
        localEndpointNetwork.set(key, { controller: controller.ecu || "Controller", networkRef: `${networkRef}-IO-${controllerSlug}` });
      }
    }
  }
  return chains.map((chain) => {
    const key = normalizeHardwareName(chain.hardware_name).toLocaleLowerCase("de");
    const assignment = assignedBus.get(key);
    const local = localEndpointNetwork.get(key);
    if (local) {
      // The selected cluster bus is the ECU/Gateway backbone.  Low-level
      // sensors and actuators retain their own confirmed/template technology
      // and are connected to the owning controller on a local I/O network.
      return {
        ...chain,
        transport_network_ref: `${local.networkRef}-${chain.interface_type.toLocaleLowerCase("de").replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "local"}`,
      };
    }
    if (!assignment) return chain;
    const hasExplicitConnection = chain.configuration?.connection_source === 'explicit_device_connection';
    const technology = hasExplicitConnection ? chain.interface_type : assignment.technology;
    const assignmentTechnology = canonicalCommunicationSystem(assignment.technology);
    const explicitTechnology = canonicalCommunicationSystem(chain.interface_type);
    const technologySuffix = explicitTechnology
      .toLocaleLowerCase("de")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "");
    // A V4 cluster may contain controllers on different confirmed field buses.
    // Keep the reviewed cluster identity, but split its physical network per
    // technology instead of assigning contradictory technologies to one ID.
    const networkRef = hasExplicitConnection && explicitTechnology && explicitTechnology !== assignmentTechnology
      ? `${assignment.networkRef}-${technologySuffix}`
      : assignment.networkRef;
    return {
      ...chain,
      interface_type: technology,
      interface_name: `${normalizeHardwareName(chain.hardware_name)}_${technology}`,
      transport_network_ref: networkRef,
    };
  });
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
