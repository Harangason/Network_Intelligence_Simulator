export const SIGNAL_SEMANTIC_TYPES = [
  "NUMERIC",
  "ENUM",
  "BOOLEAN",
  "STATE",
  "BITFIELD",
  "COUNTER",
  "FLAG",
  "RAW",
  "STRING",
  "BYTE_ARRAY",
  "DERIVED",
  "CUSTOM",
  "UNKNOWN",
] as const;

export type SignalSemanticType = typeof SIGNAL_SEMANTIC_TYPES[number];
export type SignalBitLengthStatus = "VALID" | "OVERDIMENSIONED" | "UNDERDIMENSIONED" | "UNKNOWN";
export type ReservePolicy = "NONE" | "MINIMUM_1_STATE" | "PERCENTAGE" | "EXPLICIT" | "POWER_OF_TWO";

export type SignalValueDomain = {
  minimum: number | null;
  maximum: number | null;
  resolution: number | null;
  allowedValues: unknown[];
  enumValues: Record<string, unknown>;
  invalidValues: unknown[];
  reservedValues: unknown[];
  defaultValue: unknown;
};

export type SignalEncodingDefinition = {
  rawDatatype: string;
  bitLength: number | null;
  signed: boolean | null;
  factor: number | null;
  offset: number | null;
  endianness: string;
  startBit: number | null;
  encodingType: string;
  codingRule: string;
  invalidRawValues: unknown[];
  reservedRawValues: unknown[];
};

export type CanonicalSignalDefinition = {
  id: string;
  name: string;
  displayName: string;
  description: string;
  semantic: {
    semanticType: SignalSemanticType;
    quantity: string;
    category: string;
    meaning: string;
    unit: string;
  };
  valueDomain: SignalValueDomain;
  encoding: SignalEncodingDefinition;
  communication: Record<string, unknown>;
  quality: Record<string, unknown>;
  governance: Record<string, unknown>;
};

export type SignalBitRequirement = {
  semanticType: SignalSemanticType;
  requiredBits: number | null;
  configuredBits: number | null;
  status: SignalBitLengthStatus;
  reason: string;
  valueCount: number | null;
  reserveCount: number;
};

export type SignalOptimizationProposal = {
  signalId: string;
  status: SignalBitLengthStatus;
  configuredBits: number | null;
  requiredBits: number | null;
  potentialSavingBits: number;
  reason: string;
};

type SignalRecord = { id?: unknown; name?: unknown; [key: string]: unknown };

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function array(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function number(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  return null;
}

function normalizeSemanticType(value: unknown): SignalSemanticType {
  const normalized = text(value).toUpperCase().replace(/[-\s]+/g, "_");
  return (SIGNAL_SEMANTIC_TYPES as readonly string[]).includes(normalized) ? normalized as SignalSemanticType : "UNKNOWN";
}

function entriesCount(value: Record<string, unknown>) {
  return Object.keys(value).filter(Boolean).length;
}

function signalLabel(signal: SignalRecord): string {
  return text(signal.display_name) || text(signal.name);
}

function looksLikeStateSignal(value: string): boolean {
  return /(?:status|state|mode|zustand|diagnose|fehler|error|warning|warnung)$/i.test(value)
    || /(?:^|[-_\s])(?:status|state|mode|zustand)(?:[-_\s]|$)/i.test(value);
}

function defaultStateEnumValues(label: string): Record<string, number> {
  const key = label.toLowerCase();
  if (key.includes("gateway")) {
    return {
      OFF: 0,
      INIT: 1,
      CONFIGURING: 2,
      READY: 3,
      ACTIVE: 4,
      STANDBY: 5,
      SHUTTING_DOWN: 6,
      ERROR: 7,
    };
  }
  if (/(kommunikation|connect|bus|link)/i.test(label)) {
    return {
      OFFLINE: 0,
      INITIALIZING: 1,
      CONNECTED: 2,
      PARTIAL: 3,
      BUS_OFF: 4,
      LINK_LOSS: 5,
      ERROR: 6,
    };
  }
  return {
    OFF: 0,
    INIT: 1,
    SELF_TEST: 2,
    READY: 3,
    RUNNING: 4,
    DEGRADED: 5,
    ERROR: 6,
    SHUTDOWN: 7,
  };
}

function isLegacyGenericStateDomain(values: Record<string, unknown>) {
  const keys = Object.keys(values).map((key) => key.toUpperCase()).sort();
  if (keys.length === 0) return false;
  const legacyKeys = new Set(["DEGRADED", "ERROR", "NOT_AVAILABLE", "OK", "ROUTING_LIMITED", "WARNING"]);
  return keys.every((key) => legacyKeys.has(key)) && keys.some((key) => key === "OK" || key === "NOT_AVAILABLE");
}

function ceilLog2(count: number): number | null {
  if (!Number.isFinite(count) || count <= 0) return null;
  return Math.max(1, Math.ceil(Math.log2(count)));
}

function compareBits(requiredBits: number | null, configuredBits: number | null): SignalBitLengthStatus {
  if (requiredBits === null || configuredBits === null) return "UNKNOWN";
  if (requiredBits > configuredBits) return "UNDERDIMENSIONED";
  if (requiredBits < configuredBits) return "OVERDIMENSIONED";
  return "VALID";
}

function reserveCount(domain: SignalValueDomain, policy: ReservePolicy): number {
  if (policy === "MINIMUM_1_STATE") return Math.max(1, domain.reservedValues.length);
  if (policy === "EXPLICIT") return domain.reservedValues.length;
  return domain.reservedValues.length;
}

function semanticTypeFrom(signal: SignalRecord): SignalSemanticType {
  const semantic = record(signal.semantic);
  const data = record(signal.data);
  const configuration = record(signal.configuration);
  const explicit = normalizeSemanticType(semantic.semantic_type ?? semantic.semanticType ?? data.semantic_type ?? configuration.semantic_type);
  if (explicit !== "UNKNOWN") return explicit;
  const datatype = text(signal.data_type).toLowerCase();
  if (/^(bool|boolean)$/.test(datatype)) return "BOOLEAN";
  if (/^(string|text)$/.test(datatype)) return "STRING";
  if (/^(bytes|byte_array|bytearray)$/.test(datatype)) return "BYTE_ARRAY";
  if (array(data.bit_members ?? configuration.bit_members).length > 0) return "BITFIELD";
  if (entriesCount(record(data.enum_values ?? configuration.enum_values)) > 0 || array(data.allowed_values ?? configuration.allowed_values).length > 0) {
    return /state|status|mode|zustand/i.test(text(signal.display_name) || text(signal.name)) ? "STATE" : "ENUM";
  }
  if (looksLikeStateSignal(signalLabel(signal))) return "STATE";
  return "UNKNOWN";
}

export function buildCanonicalSignalDefinition(signal: SignalRecord): CanonicalSignalDefinition {
  const semantic = record(signal.semantic);
  const data = record(signal.data);
  const configuration = record(signal.configuration);
  const communication = record(signal.communication);
  const quality = record(signal.quality);
  const provenance = record(signal.provenance);
  const semanticType = semanticTypeFrom(signal);
  const unit = text(signal.unit ?? semantic.unit);
  const rawDatatype = text(signal.data_type ?? configuration.raw_datatype ?? configuration.rawDatatype);
  const factor = number(signal.factor ?? configuration.factor);
  const offset = number(signal.offset_value ?? configuration.offset);
  const enumValues = record(data.enum_values ?? configuration.enum_values);
  const allowedValues = array(data.allowed_values ?? configuration.allowed_values);
  const useDefaultStateDomain = semanticType === "STATE" && looksLikeStateSignal(signalLabel(signal)) && entriesCount(enumValues) === 0 && allowedValues.length === 0;
  const useExpandedStateDomain = useDefaultStateDomain || (semanticType === "STATE" && looksLikeStateSignal(signalLabel(signal)) && isLegacyGenericStateDomain(enumValues));
  const expandedStateEnumValues = defaultStateEnumValues(signalLabel(signal));
  const expandedReservedValues = Array.from({ length: 16 }, (_, index) => index)
    .filter((value) => !Object.values(expandedStateEnumValues).includes(value));

  return {
    id: text(signal.id),
    name: text(signal.name),
    displayName: text(signal.display_name ?? signal.name),
    description: text(signal.description),
    semantic: {
      semanticType,
      quantity: text(semantic.quantity),
      category: text(semantic.category ?? signal.category),
      meaning: text(semantic.meaning ?? signal.description),
      unit,
    },
    valueDomain: {
      minimum: number(signal.min_value ?? signal.minimum ?? data.minimum),
      maximum: number(signal.max_value ?? signal.maximum ?? data.maximum),
      resolution: number(data.resolution ?? signal.resolution ?? factor),
      allowedValues: useExpandedStateDomain ? Object.keys(expandedStateEnumValues) : allowedValues,
      enumValues: useExpandedStateDomain ? expandedStateEnumValues : enumValues,
      invalidValues: array(data.invalid_values ?? configuration.invalid_values ?? (data.invalid_value == null ? [] : [data.invalid_value])),
      reservedValues: useExpandedStateDomain ? expandedReservedValues : array(data.reserved_values ?? configuration.reserved_values),
      defaultValue: useExpandedStateDomain ? Object.keys(expandedStateEnumValues)[0] : data.default_value ?? signal.default_value ?? null,
    },
    encoding: {
      rawDatatype,
      bitLength: number(signal.length_bits ?? configuration.bit_length),
      signed: typeof configuration.signed === "boolean" ? configuration.signed : /^(signed|int|int8|int16|int32|int64|sint8|sint16|sint32|sint64)$/.test(rawDatatype),
      factor,
      offset,
      endianness: text(signal.byte_order ?? configuration.endianness),
      startBit: number(signal.start_bit ?? configuration.start_bit),
      encodingType: text(configuration.encoding_type),
      codingRule: text(configuration.coding_rule),
      invalidRawValues: array(configuration.invalid_raw_values),
      reservedRawValues: array(configuration.reserved_raw_values),
    },
    communication,
    quality,
    governance: {
      source: text(signal.source),
      provenance,
      review_state: text(signal.review_state),
      approval_state: text(signal.approval_state),
    },
  };
}

export function calculateSignalBitRequirement(
  signal: CanonicalSignalDefinition,
  reservePolicy: ReservePolicy = "EXPLICIT",
): SignalBitRequirement {
  const domain = signal.valueDomain;
  const encoding = signal.encoding;
  const semanticType = signal.semantic.semanticType;
  const configuredBits = encoding.bitLength;
  const reserve = reserveCount(domain, reservePolicy);
  let requiredBits: number | null = null;
  let valueCount: number | null = null;
  let reason = "";

  if (semanticType === "NUMERIC") {
    if (domain.minimum === null || domain.maximum === null || domain.resolution === null || domain.resolution <= 0) {
      reason = "NUMERIC benötigt Minimum, Maximum und Resolution im Value-Domain-Modell.";
    } else if (domain.minimum > domain.maximum) {
      reason = "Minimum ist größer als Maximum.";
    } else {
      valueCount = Math.floor((domain.maximum - domain.minimum) / domain.resolution) + 1 + reserve;
      requiredBits = ceilLog2(valueCount);
      reason = `${valueCount} gültige Werte aus Range und Resolution.`;
    }
  } else if (semanticType === "ENUM" || semanticType === "STATE") {
    valueCount = Math.max(entriesCount(domain.enumValues), domain.allowedValues.length) + reserve;
    if (valueCount > 0) {
      requiredBits = ceilLog2(valueCount);
      reason = `${valueCount} definierte Zustände inklusive Reserve.`;
    } else {
      reason = `${semanticType} benötigt allowed_values oder enum_values.`;
    }
  } else if (semanticType === "BOOLEAN" || semanticType === "FLAG") {
    valueCount = 2;
    requiredBits = 1;
    reason = `${semanticType} benötigt genau 1 Bit.`;
  } else if (semanticType === "COUNTER") {
    const modulus = number(record(signal.quality).modulus ?? record(signal.communication).modulus ?? record(signal.encoding).modulus);
    if (modulus !== null && modulus > 1) {
      valueCount = modulus;
    } else if (domain.minimum !== null && domain.maximum !== null && domain.minimum <= domain.maximum) {
      valueCount = Math.floor(domain.maximum - domain.minimum) + 1;
    }
    requiredBits = valueCount === null ? null : ceilLog2(valueCount);
    reason = valueCount === null ? "COUNTER benötigt Modulus oder Minimum/Maximum." : `${valueCount} Zählerwerte.`;
  } else if (semanticType === "BITFIELD") {
    const members = array(record(signal.quality).bit_members ?? record(signal.communication).bit_members ?? record(signal.valueDomain).bit_members ?? []);
    const bits = members.map((member, index) => {
      const item = record(member);
      return number(item.bit ?? item.bit_position ?? item.start_bit) ?? index;
    });
    requiredBits = bits.length ? Math.max(...bits) + 1 : null;
    valueCount = bits.length;
    reason = bits.length ? `${bits.length} Bitfield-Mitglieder.` : "BITFIELD benötigt bit_members.";
  } else if (semanticType === "RAW" || semanticType === "STRING" || semanticType === "BYTE_ARRAY") {
    requiredBits = configuredBits;
    reason = `${semanticType} verwendet eine explizite Transportlänge.`;
  } else {
    reason = "Semantik fehlt; Legacy-Signal benötigt Klassifizierung vor Bitoptimierung.";
  }

  return {
    semanticType,
    requiredBits,
    configuredBits,
    status: compareBits(requiredBits, configuredBits),
    reason,
    valueCount,
    reserveCount: reserve,
  };
}

export function buildSignalOptimizationProposal(signal: CanonicalSignalDefinition): SignalOptimizationProposal {
  const requirement = calculateSignalBitRequirement(signal);
  return {
    signalId: signal.id,
    status: requirement.status,
    configuredBits: requirement.configuredBits,
    requiredBits: requirement.requiredBits,
    potentialSavingBits: requirement.status === "OVERDIMENSIONED" && requirement.configuredBits !== null && requirement.requiredBits !== null
      ? requirement.configuredBits - requirement.requiredBits
      : 0,
    reason: requirement.reason,
  };
}
