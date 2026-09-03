"use client";

import { FormEvent, Fragment, useEffect, useMemo, useRef, useState } from "react";
import {
  createEngineeringObject,
  createEngineeringRelation,
  approveAllValidEngineeringProposals,
  approveEngineeringProposal,
  deleteEngineeringObject,
  deleteEngineeringRelation,
  getEngineeringSchema,
  listAllEngineeringObjects,
  listEngineeringProposals,
  listEngineeringRelations,
  rejectEngineeringProposal,
  RESOURCE_LABELS,
  RESOURCE_TO_OBJECT_TYPE,
  updateEngineeringObject,
  updateEngineeringProposal,
  validateEngineeringProposal,
} from "@/lib/engineering-api";
import { ENGINEERING_MODEL_CHANGED_EVENT } from "@/lib/engineering-events";
import {
  engineeringDeviceTypeLabel,
  engineeringObjectTypeClass,
  engineeringObjectTypeLabel,
  engineeringResourceType,
  isMergedHardwareAlias,
} from "@/lib/engineering-object-style";
import type {
  EngineeringObject,
  EngineeringProposal,
  EngineeringRelation,
  EngineeringResource,
  EngineeringSchema,
  EngSignal,
} from "@/lib/types";
import { getWorkflow, setWorkflowContext } from "@/lib/workflow-api";
import {
  ENGINEERING_AGENT_WIZARD_OPEN_EVENT,
  takePendingEngineeringAgentWizard,
} from "@/lib/agent-task-events";
import { readActiveProjectId } from "@/lib/user-settings";
import { buildCanonicalSignalDefinition } from "@/lib/signal-architecture";
import { EngineeringAgentWizard } from "@/components/agent-chat-core";
import { StructureTreeWorkbench } from "@/components/structure-tree-workbench";

const RESOURCES: EngineeringResource[] = [
  "hardware-nodes",
  "hardware-interfaces",
  "functions",
  "interfaces",
  "messages",
  "signals",
];
const OBJECT_TYPE_RESOURCE: Partial<Record<string, EngineeringResource>> = Object.fromEntries(
  RESOURCES.map((item) => [RESOURCE_TO_OBJECT_TYPE[item], item]),
) as Partial<Record<string, EngineeringResource>>;
const ENGINEERING_PAGE_SIZE = 50;

const HARDWARE_PRESETS = [
  { label: "ECU", deviceType: "ECU" },
  { label: "Gateway", deviceType: "Gateway" },
  { label: "Sensor", deviceType: "SensorController" },
  { label: "Aktor", deviceType: "ActuatorController" },
] as const;

const DEFAULT_TYPING_BY_DEVICE_TYPE: Record<string, { deviceClass: number; typing: string; complexity: string }> = {
  ECU: { deviceClass: 4, typing: "Intelligent Subsystem", complexity: "SERVICE_DATA" },
  Gateway: { deviceClass: 4, typing: "Intelligent Subsystem", complexity: "SERVICE_DATA" },
  SensorController: { deviceClass: 1, typing: "Basic Sensor", complexity: "PHYSICAL_SCALAR" },
  ActuatorController: { deviceClass: 1, typing: "Basic Actuator", complexity: "CONTROL_COMMAND" },
};

const REQUIREMENT_FIELDS = [
  { key: "cycle_time_ms", label: "Zyklus", unit: "ms" },
  { key: "deadline_ms", label: "Deadline", unit: "ms" },
  { key: "timeout_ms", label: "Timeout", unit: "ms" },
  { key: "maximum_latency_ms", label: "Max. Latenz", unit: "ms" },
  { key: "maximum_jitter_ms", label: "Max. Jitter", unit: "ms" },
  { key: "data_freshness_limit", label: "Freshness", unit: "ms" },
  { key: "event_rate", label: "Event Rate", unit: "Hz" },
  { key: "burst_rate", label: "Burst Rate", unit: "Hz" },
] as const;

function requirementPayload(form: FormData, prefix: string) {
  const values: Record<string, unknown> = {};
  for (const field of REQUIREMENT_FIELDS) {
    const raw = form.get(`${prefix}${field.key}`);
    values[field.key] = raw === null || raw === "" ? null : Number(raw);
  }
  values.priority = form.get(`${prefix}priority`) || null;
  values.reliability_requirement = form.get(`${prefix}reliability_requirement`) || null;
  return values;
}

const RESOURCE_HIERARCHY: Partial<
  Record<
    EngineeringResource,
    {
      parentResource: EngineeringResource;
      parentLabel: string;
      relationType: string;
    }
  >
> = {
  functions: {
    parentResource: "hardware-nodes",
    parentLabel: "Hardware-Knoten",
    relationType: "HAS_FUNCTION",
  },
  "hardware-interfaces": {
    parentResource: "hardware-nodes",
    parentLabel: "Hardware-Knoten",
    relationType: "HAS_HARDWARE_INTERFACE",
  },
  interfaces: {
    parentResource: "functions",
    parentLabel: "Funktion",
    relationType: "HAS_INTERFACE",
  },
  messages: {
    parentResource: "interfaces",
    parentLabel: "Interface",
    relationType: "HAS_MESSAGE",
  },
  signals: {
    parentResource: "messages",
    parentLabel: "Nachricht",
    relationType: "CONTAINS_SIGNAL",
  },
};

const RESOURCE_REFERENCES: Record<EngineeringResource, EngineeringResource[]> = {
  "hardware-nodes": [],
  "hardware-interfaces": ["hardware-nodes", "messages", "functions", "interfaces"],
  functions: ["hardware-nodes"],
  interfaces: ["functions", "hardware-nodes", "messages"],
  messages: ["interfaces", "hardware-interfaces"],
  signals: ["messages", "interfaces", "functions"],
};

const RESOURCE_TABLE_HEADERS: Record<EngineeringResource, string[]> = {
  "hardware-nodes": ["Name", "Gerätetyp", "Class", "Typisierung", "Domäne"],
  "hardware-interfaces": ["Hardware", "Name", "Technologie", "Kanal", "Netzwerk", "Messages", "Last", "Status"],
  functions: ["Name", "Hardware-Knoten", "Domäne", "Beschreibung"],
  interfaces: ["Name", "Funktion", "Interface-Typ", "Hardware"],
  messages: ["Name", "Interface", "Hardware Interface", "Message-ID", "Richtung", "Zyklus", "DLC"],
  signals: ["Funktion", "Name", "Nachricht", "Start-Bit", "Länge", "Byte-Reihenfolge", "Datentyp", "Einheit"],
};

function referenceName(names: Record<string, string>, id: string | null) {
  return id ? names[id] ?? "Unbekannt" : "—";
}

type TableSort = {
  column: number;
  direction: "asc" | "desc";
} | null;

function compareEngineeringTableValues(left: string, right: string) {
  const leftNumber = parseSortableNumber(left);
  const rightNumber = parseSortableNumber(right);
  if (leftNumber !== null && rightNumber !== null && leftNumber !== rightNumber) {
    return leftNumber - rightNumber;
  }
  return left.localeCompare(right, "de-DE", { numeric: true, sensitivity: "base" });
}

function parseSortableNumber(value: string) {
  const match = value.replace(",", ".").match(/-?\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : null;
}

const BUS_TECH_NAME_PATTERN = /(?:^|_)(?:can_fd|can|lin|flexray|ethernet|ethercat|profinet|modbustcp|modbusrtu|rs232|rs485|spi|i2c|usb|pcie|mqtt|opcua)(?=_|$)/gi;
const MESSAGE_NAME_SUFFIX_PATTERN = /(?:_)?(?:data|message|nachricht|aktor|actor|sensor|status|command|steuerung)$/i;
const SIGNAL_INITIAL_ALIASES: Record<string, string> = {
  gateway: "gw",
  system_gateway: "sgw",
  systemgateway: "sgw",
};

function asciiName(value: string) {
  return value
    .replace(/ß/g, "ss")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function splitNameTokens(value: string) {
  return asciiName(value)
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .replace(/[^A-Za-z0-9]+/g, "_")
    .split("_")
    .map((token) => token.trim())
    .filter(Boolean);
}

function toSnakeCase(value: unknown) {
  return splitNameTokens(String(value ?? "")).join("_").toLowerCase();
}

function toPascalCase(value: unknown) {
  return splitNameTokens(String(value ?? ""))
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
    .join("");
}

function normalizeMessageName(value: unknown) {
  const withoutBus = toSnakeCase(value).replace(BUS_TECH_NAME_PATTERN, "_").replace(/_+/g, "_").replace(/^_|_$/g, "");
  const base = withoutBus.replace(MESSAGE_NAME_SUFFIX_PATTERN, "") || withoutBus;
  return toPascalCase(base || value);
}

function normalizeInterfaceName(value: unknown) {
  const raw = String(value ?? "");
  const cleaned = toSnakeCase(raw)
    .replace(BUS_TECH_NAME_PATTERN, "_")
    .replace(/_+/g, "_")
    .replace(/^_|_$/g, "");
  return cleaned ? cleaned.split("_").map((token) => /^\d+$/.test(token) ? token : token.charAt(0).toUpperCase() + token.slice(1)).join("_") : raw;
}

function normalizedInterfaceGroupName(value: unknown) {
  return toSnakeCase(value)
    .replace(BUS_TECH_NAME_PATTERN, "_")
    .replace(/_\d+$/g, "")
    .replace(/_+/g, "_")
    .replace(/^_|_$/g, "");
}

function signalInitials(value: unknown) {
  const cleaned = toSnakeCase(String(value ?? "")).replace(MESSAGE_NAME_SUFFIX_PATTERN, "");
  if (SIGNAL_INITIAL_ALIASES[cleaned]) return SIGNAL_INITIAL_ALIASES[cleaned];
  const tokens = cleaned.split("_").filter(Boolean);
  if (tokens.length > 1) return tokens.map((token) => token.charAt(0)).join("");
  const token = tokens[0] ?? "";
  if (!token) return "sig";
  const consonants = token.replace(/[aeiou]/g, "");
  return (consonants.length >= 2 ? consonants.slice(0, 2) : token.slice(0, 2)).toLowerCase();
}

function normalizeSignalName(value: unknown, messageName?: unknown) {
  const raw = toSnakeCase(value);
  const base = raw.replace(/^sig_/, "").replace(/_signal$/, "") || "signal";
  if (!String(messageName ?? "").trim()) return base;
  const prefix = signalInitials(messageName);
  return base.startsWith(`${prefix}_`) && base.endsWith(`_${prefix}`) ? base : `${prefix}_${base}_${prefix}`;
}

function parseTypedSignalValue(value: string) {
  const text = value.trim();
  if (!text) return "";
  if (/^-?\d+(?:\.\d+)?$/.test(text)) return Number(text);
  if (/^(true|false)$/i.test(text)) return /^true$/i.test(text);
  return text;
}

function parseSignalValueList(value: FormDataEntryValue | null) {
  return String(value ?? "")
    .split(/[,\n]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map(parseTypedSignalValue);
}

function formatSignalValueList(values: unknown[]) {
  return values.map(signalValueText).join(", ");
}

function parseSignalEnumValues(value: FormDataEntryValue | null) {
  const entries: Record<string, unknown> = {};
  for (const line of String(value ?? "").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const separator = trimmed.includes("=") ? "=" : trimmed.includes(":") ? ":" : "";
    if (!separator) continue;
    const [rawKey, ...rawValueParts] = trimmed.split(separator);
    const key = rawKey.trim().toUpperCase().replace(/[^A-Z0-9]+/g, "_").replace(/^_|_$/g, "");
    const rawValue = rawValueParts.join(separator).trim();
    if (key) entries[key] = parseTypedSignalValue(rawValue);
  }
  return entries;
}

function parseSignalEnumValueRows(form: FormData) {
  const states = form.getAll("edit_enum_state");
  const codes = form.getAll("edit_enum_code");
  const kinds = form.getAll("edit_enum_kind");
  const entries: Record<string, unknown> = {};
  const reservedValues: unknown[] = [];
  states.forEach((stateValue, index) => {
    const state = String(stateValue ?? "").trim().toUpperCase().replace(/[^A-Z0-9]+/g, "_").replace(/^_|_$/g, "");
    const code = String(codes[index] ?? "").trim();
    const kind = String(kinds[index] ?? "defined");
    if (!code) return;
    const parsedCode = parseTypedSignalValue(code);
    if (kind === "reserved") {
      reservedValues.push(parsedCode);
      return;
    }
    if (state) entries[state] = parsedCode;
  });
  return { enumValues: entries, reservedValues };
}

function formatSignalEnumValues(values: Record<string, unknown>) {
  return Object.entries(values).map(([state, code]) => `${state}=${signalValueText(code)}`).join("\n");
}

function signalFunctionName(
  item: EngineeringObject,
  names: Record<string, string>,
  objectsById: Map<string, EngineeringObject>,
) {
  if (!("message_id" in item) || !item.message_id) return "—";
  const message = objectsById.get(item.message_id);
  const interfaceId = message && "interface_id" in message && typeof message.interface_id === "string"
    ? message.interface_id
    : null;
  const interfaceObject = interfaceId ? objectsById.get(interfaceId) : null;
  const functionId = interfaceObject && "function_id" in interfaceObject && typeof interfaceObject.function_id === "string"
    ? interfaceObject.function_id
    : null;
  return referenceName(names, functionId);
}

function hardwareClassValue(item: EngineeringObject) {
  return "device_class" in item && item.device_class !== null && item.device_class !== undefined
    ? String(item.device_class)
    : "—";
}

function hardwareTypingValue(item: EngineeringObject) {
  return "device_typing" in item ? item.device_typing || "—" : "—";
}

function hardwareGeneratorPolicy(item: EngineeringObject) {
  if (!("hardware_information" in item)) return {};
  const policy = item.hardware_information.generator_policy;
  return policy && typeof policy === "object" && !Array.isArray(policy) ? policy as Record<string, unknown> : {};
}

function hardwareCapabilities(item: EngineeringObject) {
  if (!("hardware_information" in item)) return {};
  const profile = item.hardware_information.device_capability_profile;
  return profile && typeof profile === "object" && !Array.isArray(profile) ? profile as Record<string, unknown> : {};
}

function resourceTableValues(
  resource: EngineeringResource,
  item: EngineeringObject,
  names: Record<string, string>,
  objectsById: Map<string, EngineeringObject>,
): string[] {
  switch (resource) {
    case "hardware-nodes":
      return [
        item.name,
        "device_type" in item ? engineeringDeviceTypeLabel(item.device_type) : "—",
        hardwareClassValue(item),
        hardwareTypingValue(item),
        item.domain ?? "—",
      ];
    case "hardware-interfaces": {
      const messageCount = "message_refs" in item && Array.isArray(item.message_refs)
        ? item.message_refs.length
        : Array.from(objectsById.values()).filter((candidate) => (
            "hardware_interface_id" in candidate && candidate.hardware_interface_id === item.id
          )).length;
      const load = "static_load" in item && item.static_load !== null
        ? `${item.static_load} %`
        : "runtime_load" in item && item.runtime_load !== null
          ? `${item.runtime_load} %`
          : "—";
      return [
        "hardware_node_id" in item ? referenceName(names, item.hardware_node_id) : "—",
        item.name,
        "technology" in item ? item.technology : "—",
        "channel_index" in item && item.channel_index !== null ? String(item.channel_index) : "—",
        "network_ref" in item ? item.network_ref ?? "—" : "—",
        String(messageCount),
        load,
        "status" in item ? item.status : "—",
      ];
    }
    case "functions":
      return [
        item.name,
        "hardware_node_id" in item ? referenceName(names, item.hardware_node_id) : "—",
        item.domain ?? "—",
        item.description ?? "—",
      ];
    case "interfaces":
      return [
        item.name,
        "function_id" in item ? referenceName(names, item.function_id) : "—",
        "interface_type" in item ? item.interface_type : "—",
        "hardware_node_id" in item ? referenceName(names, item.hardware_node_id) : "—",
      ];
    case "messages":
      return [
        item.name,
        "interface_id" in item ? referenceName(names, item.interface_id) : "—",
        "hardware_interface_id" in item ? referenceName(names, item.hardware_interface_id) : "—",
        "message_id_hex" in item ? item.message_id_hex ?? "—" : "—",
        "direction" in item ? item.direction ?? "—" : "—",
        "cycle_ms" in item && item.cycle_ms !== null ? `${item.cycle_ms} ms` : "—",
        "dlc" in item && item.dlc !== null ? String(item.dlc) : "—",
      ];
    case "signals":
      return [
        signalFunctionName(item, names, objectsById),
        item.name,
        "message_id" in item ? referenceName(names, item.message_id) : "—",
        "start_bit" in item && item.start_bit !== null ? String(item.start_bit) : "—",
        "length_bits" in item && item.length_bits !== null ? `${item.length_bits} Bit` : "—",
        "byte_order" in item ? item.byte_order ?? "—" : "—",
        "data_type" in item ? item.data_type ?? "—" : "—",
        "unit" in item ? item.unit ?? "—" : "—",
      ];
  }
}

const RELATION_TYPES = [
  "HAS_FUNCTION",
  "HAS_CAPABILITY",
  "HAS_PORT",
  "HAS_INTERFACE",
  "CONNECTED_TO",
  "COMMUNICATES_WITH",
  "PROVIDES",
  "CONSUMES",
  "SENDS",
  "RECEIVES",
  "HAS_MESSAGE",
  "CONTAINS_SIGNAL",
  "RUNS_ON",
  "MAPPED_TO",
  "USES_PROTOCOL",
  "CONNECTED_VIA",
  "DERIVED_FROM",
  "DEFINED_BY",
  "IMPORTED_FROM",
  "SUPPORTED_BY",
  "VALIDATED_BY",
  "CONFLICTS_WITH",
  "DEPENDS_ON",
  "RELATED_TO",
  "SIMULATED_IN",
  "FAILED_IN",
  "OBSERVED_IN",
  "REPLACES",
  "VERSION_OF",
];

const OBJECT_TYPE_TO_RESOURCE: Record<string, EngineeringResource> = {
  HardwareNode: "hardware-nodes",
  HardwareNetworkInterface: "hardware-interfaces",
  Function: "functions",
  Interface: "interfaces",
  Message: "messages",
  Signal: "signals",
};

const WIZARD_STEPS = ["Identität", "Zuordnung", "Details", "Prüfen"] as const;

const REQUIRED_PROPOSAL_FIELDS: Record<string, string[]> = {
  HardwareNode: ["name"],
  HardwareNetworkInterface: ["name", "hardware_node_id", "technology"],
  Function: ["name", "hardware_node_id"],
  Interface: ["name", "function_id", "interface_type"],
  Message: ["name", "interface_id"],
  Signal: ["name", "message_id"],
  Relation: ["relation_type", "source_type", "source_id", "target_type", "target_id"],
};

const FIELD_LABELS: Record<string, string> = {
  name: "Name",
  domain: "Domäne",
  description: "Beschreibung",
  device_type: "Gerätetyp",
  device_class: "Class",
  device_typing: "Typisierung",
  data_complexity: "Data Complexity",
  classification_status: "Klassifikationsstatus",
  capability_profile_ref: "Capability-Profil",
  hardware_node_id: "Hardware-Knoten",
  hardware_interface_id: "Hardware Interface",
  function_id: "Funktion",
  interface_id: "Interface",
  message_id: "Message",
  interface_type: "Interface-Typ",
  technology: "Technologie",
  controller_ref: "Controller",
  physical_port_ref: "Physischer Port",
  channel_index: "Kanal",
  network_ref: "Netzwerk",
  bitrate: "Bitrate",
  data_bitrate: "Data Bitrate",
  status: "Status",
  static_load: "Statische Last",
  runtime_load: "Runtime Last",
  target_load_limit: "Ziel-Last",
  warning_load_limit: "Warn-Last",
  hard_load_limit: "Harte Last",
  message_id_hex: "Message-ID",
  direction: "Richtung",
  cycle_ms: "Zyklus",
  dlc: "DLC",
  display_name: "Anzeigename",
  start_bit: "Start-Bit",
  length_bits: "Länge",
  byte_order: "Byte Order",
  data_type: "Datentyp",
  factor: "Faktor",
  offset_value: "Offset",
  unit: "Einheit",
  min_value: "Min",
  max_value: "Max",
  relation_type: "Relation",
  source_type: "Quelle-Typ",
  source_id: "Quelle",
  target_type: "Ziel-Typ",
  target_id: "Ziel",
};

const SIGNAL_BYTE_ORDERS = ["little_endian", "big_endian"];

function proposalObjectType(proposal: EngineeringProposal, item: Record<string, unknown>) {
  const direct = String(item.object_type ?? "");
  if (direct in OBJECT_TYPE_TO_RESOURCE || direct === "Relation") return direct;
  const resource = String(item.resource ?? "");
  if (resource in RESOURCE_TO_OBJECT_TYPE) return RESOURCE_TO_OBJECT_TYPE[resource as EngineeringResource];
  const target = (proposal as EngineeringProposal & { target_object?: Record<string, unknown> }).target_object;
  const targetResource = String(target?.resource ?? "");
  if (targetResource in RESOURCE_TO_OBJECT_TYPE) return RESOURCE_TO_OBJECT_TYPE[targetResource as EngineeringResource];
  if (proposal.proposal_type === "RELATION") return "Relation";
  return proposal.proposal_type || "Object";
}

function proposalAction(item: Record<string, unknown>) {
  const action = String(item.proposal_action ?? item.action ?? "CREATE").toUpperCase();
  return ["CREATE", "UPDATE", "DELETE", "DEPRECATE"].includes(action) ? action : "CREATE";
}

function proposalActionLabel(action: string) {
  if (action === "UPDATE") return "Korrigieren";
  if (action === "DELETE") return "Loeschen";
  if (action === "DEPRECATE") return "Ausmustern";
  return "Ergaenzen";
}

function proposalApplyLabel(action: string) {
  if (action === "UPDATE") return "Korrektur uebernehmen";
  if (action === "DELETE") return "Loeschen freigeben";
  if (action === "DEPRECATE") return "Ausmustern freigeben";
  return "Freigeben";
}

function proposalItemApplied(item: Record<string, unknown>) {
  return String(item.proposal_state ?? "").toUpperCase() === "APPROVED" || Boolean(item.applied_action);
}

function fieldValue(value: unknown) {
  return value === null || value === undefined ? "" : String(value);
}

function optionalNumberValue(value: string) {
  return value.trim() === "" ? null : Number(value);
}

function words(value: unknown) {
  return fieldValue(value).toLowerCase().split(/[^a-z0-9]+/).filter((word) => word.length > 2);
}

function shortId(id: string) {
  return id ? id.slice(0, 8) : "";
}

function objectById(references: Partial<Record<EngineeringResource, EngineeringObject[]>>, id: unknown) {
  const stringId = fieldValue(id);
  if (!stringId) return undefined;
  return Object.values(references).flatMap((items) => items ?? []).find((item) => item.id === stringId);
}

function interfaceTechnology(item: EngineeringObject | undefined) {
  if (!item || !("interface_type" in item)) return "";
  const raw = String(item.configuration?.bus ?? item.interface_type ?? "").toLowerCase();
  if (raw.includes("can_fd") || raw.includes("can fd")) return "CAN FD";
  if (raw.includes("ethernet")) return "Ethernet";
  if (raw.includes("lin")) return "LIN";
  if (raw.includes("flexray")) return "FlexRay";
  return String(item.interface_type ?? "");
}

function missingProposalFields(type: string, item: Record<string, unknown>) {
  return (REQUIRED_PROPOSAL_FIELDS[type] ?? ["name"]).filter((field) => {
    const value = item[field];
    return value === null || value === undefined || String(value).trim() === "";
  });
}

function optionLabel(item: EngineeringObject, references: Partial<Record<EngineeringResource, EngineeringObject[]>> = {}) {
  const domain = item.domain ? ` · ${item.domain}` : "";
  if ("interface_type" in item) {
    const fn = objectById(references, item.function_id);
    const hw = objectById(references, item.hardware_node_id);
    return `${item.name} · ${item.interface_type}${fn ? ` · ${fn.name}` : ""}${hw ? ` · ${hw.name}` : ""} · ${shortId(item.id)}`;
  }
  if ("interface_id" in item) {
    const iface = objectById(references, item.interface_id);
    return `${item.name}${iface ? ` · ${iface.name}` : ""}${domain} · ${shortId(item.id)}`;
  }
  if ("message_id" in item) {
    const message = objectById(references, item.message_id);
    return `${item.display_name || item.name}${message ? ` · ${message.name}` : ""}${domain} · ${shortId(item.id)}`;
  }
  if ("hardware_node_id" in item) {
    const hw = objectById(references, item.hardware_node_id);
    return `${item.name}${hw ? ` · ${hw.name}` : ""}${domain} · ${shortId(item.id)}`;
  }
  return `${item.name}${domain} · ${shortId(item.id)}`;
}

function referenceDisplay(references: Partial<Record<EngineeringResource, EngineeringObject[]>>, field: string, value: unknown) {
  const id = fieldValue(value);
  if (!id) return "Noch nicht gesetzt";
  const allReferences = Object.values(references).flatMap((items) => items ?? []);
  const item = allReferences.find((candidate) => candidate.id === id);
  return item ? optionLabel(item, references) : id;
}

type WizardSuggestion = {
  id: string;
  label: string;
  confidence: number;
  reason: string;
};

function proposalContextText(proposal: EngineeringProposal, draft: Record<string, unknown>) {
  return [proposal.prompt, draft.name, draft.description, draft.domain].map(fieldValue).join(" ");
}

function scoreReferenceOption(
  proposal: EngineeringProposal,
  draft: Record<string, unknown>,
  item: EngineeringObject,
  references: Partial<Record<EngineeringResource, EngineeringObject[]>>,
) {
  const context = new Set(words(proposalContextText(proposal, draft)));
  const candidateWords = [
    ...words(item.name),
    ...words(item.domain),
    ...words("display_name" in item ? item.display_name : ""),
    ...words("interface_type" in item ? item.interface_type : ""),
  ];
  let score = 34;
  for (const word of candidateWords) {
    if (context.has(word)) score += 16;
  }
  if (draft.domain && item.domain === draft.domain) score += 12;
  if ("interface_id" in item) {
    const iface = objectById(references, item.interface_id);
    if (iface && "interface_type" in iface && fieldValue(iface.interface_type).toLowerCase().includes("can")) score += 6;
  }
  if ("interface_type" in item && fieldValue(item.interface_type).toLowerCase().includes("can")) score += 6;
  return Math.max(12, Math.min(96, score));
}

function referenceSuggestions(
  proposal: EngineeringProposal,
  draft: Record<string, unknown>,
  options: EngineeringObject[],
  references: Partial<Record<EngineeringResource, EngineeringObject[]>>,
) {
  return options
    .map((item) => ({
      id: item.id,
      label: optionLabel(item, references),
      confidence: scoreReferenceOption(proposal, draft, item, references),
      reason: "Namensnähe, Domäne und Bus-Kontext",
    }))
    .sort((left, right) => right.confidence - left.confidence)
    .slice(0, 3);
}

function busDefaultsFor(technology: string, objectType: string) {
  const tech = technology.toLowerCase();
  if (objectType === "Message") {
    if (tech.includes("ethernet")) return { direction: "tx", cycle_ms: 10, dlc: 64 };
    if (tech.includes("lin")) return { direction: "tx", cycle_ms: 20, dlc: 8 };
    if (tech.includes("flex")) return { direction: "tx", cycle_ms: 5, dlc: 32 };
    return { direction: "tx", cycle_ms: 10, dlc: 64 };
  }
  if (objectType === "Signal") {
    if (tech.includes("ethernet")) return { start_bit: 0, length_bits: 32, byte_order: "big_endian", data_type: "float", factor: 1, offset_value: 0 };
    return { start_bit: 0, length_bits: 16, byte_order: "little_endian", data_type: "unsigned", factor: 1, offset_value: 0 };
  }
  return {};
}

export function EngineeringWorkbench() {
  const [resource, setResource] = useState<EngineeringResource>("hardware-nodes");
  const [schema, setSchema] = useState<EngineeringSchema | null>(null);
  const [items, setItems] = useState<EngineeringObject[]>([]);
  const [referenceObjects, setReferenceObjects] = useState<EngineeringObject[]>([]);
  const [referenceNames, setReferenceNames] = useState<Record<string, string>>({});
  const [relations, setRelations] = useState<EngineeringRelation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [hardwarePreset, setHardwarePreset] = useState<string | null>(null);
  const [showAgentWizard, setShowAgentWizard] = useState(false);
  const [showStructureTree, setShowStructureTree] = useState(false);
  const [activeInterfaceIds, setActiveInterfaceIds] = useState<Set<string> | null>(null);
  const [showUnusedInterfaces, setShowUnusedInterfaces] = useState(false);
  const [columnFilters, setColumnFilters] = useState<string[]>([]);
  const [tableSort, setTableSort] = useState<TableSort>(null);
  const [page, setPage] = useState(1);
  const [refreshKey, setRefreshKey] = useState(0);
  const [deepLinkTarget, setDeepLinkTarget] = useState<{ id: string; edit: boolean } | null>(null);

  useEffect(() => {
    const openRequestedWizard = () => {
      if (takePendingEngineeringAgentWizard(readActiveProjectId())) setShowAgentWizard(true);
    };
    openRequestedWizard();
    window.addEventListener(ENGINEERING_AGENT_WIZARD_OPEN_EVENT, openRequestedWizard);
    return () => window.removeEventListener(ENGINEERING_AGENT_WIZARD_OPEN_EVENT, openRequestedWizard);
  }, []);

  useEffect(() => {
    getEngineeringSchema()
      .then(setSchema)
      .catch((err) => setError(err instanceof Error ? err.message : "Schema konnte nicht geladen werden."));
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requestedResource = params.get("resource");
    const requestedType = params.get("type");
    const nextResource = requestedResource && RESOURCES.includes(requestedResource as EngineeringResource)
      ? requestedResource as EngineeringResource
      : requestedType
        ? OBJECT_TYPE_RESOURCE[requestedType]
        : undefined;
    if (nextResource) setResource(nextResource);
    const objectId = params.get("object");
    if (objectId) setDeepLinkTarget({ id: objectId, edit: params.get("edit") === "1" });
  }, []);

  useEffect(() => {
    setLoading(true);
    setError("");
    Promise.all([
      listAllEngineeringObjects(resource),
      Promise.all(RESOURCE_REFERENCES[resource].map((reference) => listAllEngineeringObjects(reference))),
    ])
      .then(([nextItems, referenceGroups]) => {
        const nextReferences = referenceGroups.flat();
        setItems(nextItems);
        setReferenceObjects(nextReferences);
        setReferenceNames(
          Object.fromEntries(nextReferences.map((reference) => [reference.id, reference.name])),
        );
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Backend nicht erreichbar."))
      .finally(() => setLoading(false));
  }, [resource, refreshKey]);

  useEffect(() => {
    setSelectedId(null);
    setColumnFilters([]);
    setTableSort(null);
    setPage(1);
  }, [resource]);

  useEffect(() => {
    if (resource !== "interfaces") {
      setActiveInterfaceIds(null);
      return;
    }
    let cancelled = false;
    getWorkflow()
      .then((state) => {
        if (cancelled) return;
        const ids = new Set<string>();
        for (const node of state.topology.nodes ?? []) {
          for (const port of node.ports ?? []) {
            if (port.engineeringId) ids.add(port.engineeringId);
          }
        }
        setActiveInterfaceIds(ids);
      })
      .catch(() => {
        if (!cancelled) setActiveInterfaceIds(null);
      });
    return () => {
      cancelled = true;
    };
  }, [resource, refreshKey]);

  useEffect(() => {
    if (!showAgentWizard) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setShowAgentWizard(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [showAgentWizard]);

  useEffect(() => {
    const handleModelChanged = (event: Event) => {
      const detail = (event as CustomEvent<{ resource?: string; id?: string }>).detail;
      setRefreshKey((key) => key + 1);
      if (detail?.resource === resource && detail.id) setSelectedId(detail.id);
    };
    window.addEventListener(ENGINEERING_MODEL_CHANGED_EVENT, handleModelChanged);
    return () => window.removeEventListener(ENGINEERING_MODEL_CHANGED_EVENT, handleModelChanged);
  }, [resource]);

  const unusedNetworkInterfaces = useMemo(
    () => resource === "interfaces" && activeInterfaceIds
      ? items.filter((item) => (
          item.provenance.origin === "network-editor"
          && !activeInterfaceIds.has(item.id)
        ))
      : [],
    [activeInterfaceIds, items, resource],
  );
  const baseVisibleItems = useMemo(() => {
    const activeItems = resource === "hardware-nodes"
      ? items.filter((item) => !isMergedHardwareAlias(item))
      : items;
    return resource === "interfaces" && !showUnusedInterfaces && unusedNetworkInterfaces.length
      ? activeItems.filter((item) => !unusedNetworkInterfaces.some((unused) => unused.id === item.id))
      : activeItems;
  }, [items, resource, showUnusedInterfaces, unusedNetworkInterfaces]);
  const tableHeaders = RESOURCE_TABLE_HEADERS[resource];
  const engineeringObjectsById = useMemo(
    () => new Map([...items, ...referenceObjects].map((item) => [item.id, item])),
    [items, referenceObjects],
  );
  const visibleItems = useMemo(
    () => {
      const filtered = baseVisibleItems.filter((item) => {
        const values = resourceTableValues(resource, item, referenceNames, engineeringObjectsById);
        return columnFilters.every((filter, index) => {
          const query = (filter ?? "").trim().toLocaleLowerCase("de-DE");
          return !query || (values[index] ?? "").toLocaleLowerCase("de-DE").includes(query);
        });
      });
      if (!tableSort) return filtered;
      return [...filtered].sort((left, right) => {
        const leftValues = resourceTableValues(resource, left, referenceNames, engineeringObjectsById);
        const rightValues = resourceTableValues(resource, right, referenceNames, engineeringObjectsById);
        const order = compareEngineeringTableValues(leftValues[tableSort.column] ?? "", rightValues[tableSort.column] ?? "");
        return tableSort.direction === "asc" ? order : -order;
      });
    },
    [baseVisibleItems, columnFilters, engineeringObjectsById, referenceNames, resource, tableSort],
  );
  const totalPages = Math.max(1, Math.ceil(visibleItems.length / ENGINEERING_PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const paginatedItems = useMemo(
    () => visibleItems.slice(
      (currentPage - 1) * ENGINEERING_PAGE_SIZE,
      currentPage * ENGINEERING_PAGE_SIZE,
    ),
    [currentPage, visibleItems],
  );
  const selected = useMemo(
    () => paginatedItems.find((item) => item.id === selectedId) ?? null,
    [paginatedItems, selectedId],
  );

  useEffect(() => {
    if (!deepLinkTarget) return;
    const index = visibleItems.findIndex((item) => item.id === deepLinkTarget.id);
    if (index < 0) return;
    setPage(Math.floor(index / ENGINEERING_PAGE_SIZE) + 1);
    setSelectedId(deepLinkTarget.id);
  }, [deepLinkTarget, visibleItems]);

  useEffect(() => {
    setPage((current) => Math.min(current, totalPages));
  }, [totalPages]);

  useEffect(() => {
    void setWorkflowContext({
      selected_object: selected ? { id: selected.id, type: RESOURCE_TO_OBJECT_TYPE[resource], name: selected.name } : null,
      selected_signal: resource === "signals" && selected ? selected.id : null,
    }).catch(() => undefined);
  }, [resource, selected]);

  useEffect(() => {
    if (!selected) {
      setRelations([]);
      return;
    }
    listEngineeringRelations({ object_type: RESOURCE_TO_OBJECT_TYPE[resource], object_id: selected.id })
      .then(setRelations)
      .catch(() => setRelations([]));
  }, [selected, resource]);

  function refresh() {
    setRefreshKey((key) => key + 1);
  }

  if (error) {
    return (
      <>
        <div className="panel error-card">
          <p className="eyebrow">Engineering-API nicht erreichbar</p>
          <h2>{error}</h2>
          <p className="muted">Prüfe Backend und Datenbankverbindung oder versuche es erneut.</p>
          <div className="form-actions error-card-actions">
            <button className="button secondary" onClick={refresh} type="button">
              Erneut prüfen
            </button>
            <button className="button primary" onClick={() => setShowAgentWizard(true)} type="button">
              Projekt-Wizard öffnen
            </button>
          </div>
        </div>
        {showAgentWizard && <EngineeringAgentWizardDialog onClose={() => setShowAgentWizard(false)} />}
      </>
    );
  }

  return (
    <>
    <div className="workspace-grid engineering-workspace">
      <div className="panel config-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Kanonisches Modell</p>
            <h2 className={showStructureTree ? undefined : `eng-object-label ${engineeringObjectTypeClass(engineeringResourceType(resource))}`}>{showStructureTree ? "Structure Tree" : RESOURCE_LABELS[resource]}</h2>
          </div>
          <div className="panel-heading-actions">
            <button className="button secondary" onClick={() => setShowAgentWizard(true)} type="button">
              Agent-Auftrag
            </button>
          </div>
        </div>

        <div className="eng-resource-tabs eng-resource-flow" role="tablist" aria-label="Objekthierarchie">
          {RESOURCES.map((res, index) => (
            <Fragment key={res}>
              <button
                aria-selected={!showStructureTree && resource === res}
                className={`eng-object-accent ${engineeringObjectTypeClass(engineeringResourceType(res))} ${!showStructureTree && resource === res ? "active" : ""}`}
                onClick={() => {
                  setShowStructureTree(false);
                  setResource(res);
                  setShowCreate(false);
                  setHardwarePreset(null);
                }}
                role="tab"
                type="button"
              >
                {RESOURCE_LABELS[res]}
              </button>
              {index < RESOURCES.length - 1 && (
                <span aria-hidden="true" className="eng-resource-arrow">→</span>
              )}
            </Fragment>
          ))}
          <span aria-hidden="true" className="eng-resource-tree-divider" />
          <button
            aria-selected={showStructureTree}
            className={`eng-structure-tree-tab ${showStructureTree ? "active" : ""}`}
            onClick={() => {
              setShowStructureTree(true);
              setShowCreate(false);
              setHardwarePreset(null);
              setSelectedId(null);
            }}
            role="tab"
            type="button"
          >
            Structure Tree
          </button>
        </div>

        {showStructureTree ? (
          <StructureTreeWorkbench onChanged={refresh} />
        ) : <>
        <div className={`eng-resource-wizard-bar eng-object-surface ${engineeringObjectTypeClass(engineeringResourceType(resource))}`}>
          <div>
            <p className="eyebrow">Objekt-Wizard</p>
            <strong>{RESOURCE_LABELS[resource]} geführt anlegen</strong>
            <span>Identität → Zuordnung → technische Details → Prüfung</span>
          </div>
          <button
            className="button primary"
            onClick={() => {
              setHardwarePreset(null);
              setShowCreate(true);
            }}
            type="button"
          >
            Wizard starten
          </button>
        </div>

        {resource === "interfaces" && unusedNetworkInterfaces.length > 0 && (
          <label className="eng-unused-interface-toggle">
            <input
              checked={showUnusedInterfaces}
              onChange={(event) => {
                setShowUnusedInterfaces(event.target.checked);
                setSelectedId(null);
                setPage(1);
              }}
              type="checkbox"
            />
            <span>Verwaiste Netzwerk-Interfaces anzeigen</span>
            <small>{unusedNetworkInterfaces.length} nicht mehr in der Topologie verwendet</small>
          </label>
        )}

        {resource === "hardware-nodes" && (
          <div
            aria-label="Hardware-Typ auswählen"
            className="net-palette eng-hardware-quick-add"
            role="group"
          >
            {HARDWARE_PRESETS.map((preset) => (
              <button
                className={`net-add ${hardwarePreset === preset.deviceType && showCreate ? "active" : ""}`}
                key={preset.deviceType}
                onClick={() => {
                  setHardwarePreset(preset.deviceType);
                  setShowCreate(true);
                }}
                type="button"
              >
                + {preset.label}
              </button>
            ))}
          </div>
        )}

        {showCreate && (
          <CreateForm
            hardwarePreset={hardwarePreset}
            key={`${resource}:${hardwarePreset ?? "custom"}`}
            onClose={() => {
              setShowCreate(false);
              setHardwarePreset(null);
            }}
            resource={resource}
            schema={schema}
            onCreated={() => {
              setShowCreate(false);
              setHardwarePreset(null);
              refresh();
            }}
          />
        )}

        {loading ? (
          <div className="loading-panel">Lädt …</div>
        ) : baseVisibleItems.length === 0 ? (
          <div className="empty-result">
            <span className="empty-icon">◇</span>
            <strong>Keine Objekte vorhanden</strong>
            <p>Lege das erste {RESOURCE_LABELS[resource]}-Objekt an.</p>
          </div>
        ) : (
          <div className="eng-table-scroll">
            <table className={`eng-table ${resource}`}>
              <thead>
                <tr>
                  {tableHeaders.map((header, index) => {
                    const isActiveSort = tableSort?.column === index;
                    return (
                      <th key={header}>
                        <button
                          aria-label={`${header} sortieren`}
                          aria-sort={isActiveSort ? (tableSort.direction === "asc" ? "ascending" : "descending") : "none"}
                          className={`eng-table-sort ${isActiveSort ? "active" : ""}`}
                          onClick={() => {
                            setTableSort((current) => (
                              current?.column === index
                                ? { column: index, direction: current.direction === "asc" ? "desc" : "asc" }
                                : { column: index, direction: "asc" }
                            ));
                            setSelectedId(null);
                            setPage(1);
                          }}
                          type="button"
                        >
                          <span>{header}</span>
                          <span aria-hidden="true" className="eng-table-sort-indicator">
                            {isActiveSort ? (tableSort.direction === "asc" ? "↑" : "↓") : "↕"}
                          </span>
                        </button>
                      </th>
                    );
                  })}
                </tr>
                <tr className="eng-table-filter-row">
                  {tableHeaders.map((header, index) => (
                    <th key={`${header}:filter`}>
                      <input
                        aria-label={`${header} filtern`}
                        onChange={(event) => {
                          const value = event.target.value;
                          setColumnFilters((current) => {
                            const next = [...current];
                            next[index] = value;
                            return next;
                          });
                          setSelectedId(null);
                          setPage(1);
                        }}
                        placeholder="Filtern"
                        type="search"
                        value={columnFilters[index] ?? ""}
                      />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visibleItems.length === 0 && (
                  <tr className="eng-table-filter-empty">
                    <td colSpan={tableHeaders.length}>
                      Keine Einträge entsprechen den Spaltenfiltern.
                    </td>
                  </tr>
                )}
                {paginatedItems.map((item) => (
                  <Fragment key={item.id}>
                    <tr
                      className={`eng-object-surface ${engineeringObjectTypeClass(item.object_type)} ${item.id === selectedId ? "selected" : ""}`}
                      onClick={() => setSelectedId(item.id)}
                    >
                      {resourceTableValues(resource, item, referenceNames, engineeringObjectsById).map((value, index) => (
                        <td className={index === 0 ? undefined : "muted"} key={`${item.id}:${index}`}>
                          {value}
                        </td>
                      ))}
                    </tr>
                    {item.id === selectedId && (
                      <tr className="eng-detail-row">
                        <td colSpan={tableHeaders.length}>
                          <DetailPanel
                            item={item}
                            peerItems={items}
                            referenceObjects={referenceObjects}
                            referenceNames={referenceNames}
                            resource={resource}
                            relations={relations}
                            schema={schema}
                            initialEdit={deepLinkTarget?.id === item.id && deepLinkTarget.edit}
                            onChanged={refresh}
                            onDeleted={() => {
                              setSelectedId(null);
                              refresh();
                            }}
                          />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
            {visibleItems.length > 0 && (
              <footer className="eng-table-pagination">
                <span>
                  {(currentPage - 1) * ENGINEERING_PAGE_SIZE + 1}-{Math.min(currentPage * ENGINEERING_PAGE_SIZE, visibleItems.length)} von {visibleItems.length} Einträgen · {ENGINEERING_PAGE_SIZE} pro Seite
                </span>
                <div>
                  <button
                    className="button secondary tiny"
                    disabled={currentPage === 1}
                    onClick={() => setPage((current) => Math.max(1, current - 1))}
                    type="button"
                  >
                    Zurück
                  </button>
                  <span>Seite {currentPage} von {totalPages}</span>
                  <button
                    className="button secondary tiny"
                    disabled={currentPage === totalPages}
                    onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                    type="button"
                  >
                    Weiter
                  </button>
                </div>
              </footer>
            )}
          </div>
        )}
        </>}
      </div>
    </div>
    {showAgentWizard && <EngineeringAgentWizardDialog onClose={() => setShowAgentWizard(false)} />}
    </>
  );
}

function EngineeringAgentWizardDialog({ onClose }: { onClose: () => void }) {
  return (
    <div
      className="engineering-agent-wizard-backdrop"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
      role="presentation"
    >
      <section aria-labelledby="engineering-agent-wizard-title" aria-modal="true" className="engineering-agent-wizard-dialog" role="dialog">
        <header className="engineering-agent-wizard-header">
          <div>
            <p className="eyebrow">Geführte Anlage</p>
            <h2 id="engineering-agent-wizard-title">Engineering-Auftrag erstellen</h2>
            <span>Technische Vorgaben festlegen und anschließend vom Agenten ausführen lassen.</span>
          </div>
          <button aria-label="Wizard schließen" className="eng-dialog-close" onClick={onClose} type="button">×</button>
        </header>
        <EngineeringAgentWizard
          busy={false}
          mode="full"
          onFinish={onClose}
          title="Technische Vorgaben"
        />
      </section>
    </div>
  );
}

function ProposalReviewPanel({
  item,
  resource,
  onChanged,
}: {
  item: EngineeringObject;
  resource: EngineeringResource;
  onChanged: () => void;
}) {
  const [proposals, setProposals] = useState<EngineeringProposal[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [wizard, setWizard] = useState<{ proposalId: string; index: number } | null>(null);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");

  async function refresh() {
    try {
      setProposals(await listEngineeringProposals());
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Vorschläge konnten nicht geladen werden.");
    }
  }

  useEffect(() => {
    void refresh();
  }, [item.id]);

  async function act(key: string, action: () => Promise<unknown>, message: string) {
    setBusy(key);
    setNotice("");
    try {
      await action();
      setNotice(message);
      await refresh();
      onChanged();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Aktion fehlgeschlagen.");
    } finally {
      setBusy("");
    }
  }

  async function save(event: FormEvent<HTMLFormElement>, proposal: EngineeringProposal) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const updated = proposal.proposed_objects.map((item, index) => ({
      ...item,
      name: form.get(`name-${index}`) || item.name,
      description: form.get(`description-${index}`) || null,
      domain: form.get(`domain-${index}`) || null,
    }));
    await act(`save:${proposal.proposal_id}`, () => updateEngineeringProposal(proposal.proposal_id, updated), "Vorschlag gespeichert. Erneute Validierung erforderlich.");
    setEditingId(null);
  }

  async function saveWizard(proposal: EngineeringProposal, index: number, nextItem: Record<string, unknown>) {
    const updated = proposal.proposed_objects.map((item, itemIndex) => (itemIndex === index ? nextItem : item));
    await act(
      `wizard:${proposal.proposal_id}:${index}`,
      async () => {
        await updateEngineeringProposal(proposal.proposal_id, updated);
        await validateEngineeringProposal(proposal.proposal_id);
      },
      "Wizard gespeichert und Vorschlag neu validiert.",
    );
    setWizard(null);
  }

  const relevant = proposals.filter((proposal) => {
    const target = (proposal as EngineeringProposal & { target_object?: Record<string, unknown> }).target_object;
    const targetResource = String(target?.resource ?? "");
    return proposal.proposed_objects.some((candidate) => {
      const canonicalId = String(candidate.canonical_id ?? "");
      const sameObject = canonicalId === item.id
        || (targetResource === resource && String(candidate.name ?? "") === item.name);
      const relatedObject = proposal.proposal_type === "RELATION"
        && (String(candidate.source_id ?? "") === item.id || String(candidate.target_id ?? "") === item.id);
      return sameObject || relatedObject;
    });
  });
  const open = relevant.filter((proposal) => !["APPROVED", "REJECTED", "SUPERSEDED"].includes(proposal.status));
  const wizardProposal = wizard ? relevant.find((proposal) => proposal.proposal_id === wizard.proposalId) : undefined;

  return (
    <details className="eng-detail-section eng-proposal-review embedded">
      <summary>
        <span>KI-Audit</span>
        <strong>{relevant.length} {relevant.length === 1 ? "Vorgang" : "Vorgänge"}</strong>
      </summary>
      <div className="eng-detail-section-body">
      <div className="panel-heading">
        <div><p className="eyebrow">KI-Audit</p><h2>Vorschläge und Werkzeuge</h2></div>
        <div className="panel-heading-actions">
          <span className="status-badge">{open.length} offen</span>
          <button className="button secondary tiny" disabled={!open.length || Boolean(busy)} onClick={() => void act("approve-all", approveAllValidEngineeringProposals, "Alle validen Vorschlaege freigegeben.")} type="button">Alle validen freigeben</button>
        </div>
      </div>
      {notice && <div className="notice">{notice}</div>}
      {!relevant.length ? (
        <div className="eng-proposal-empty">Für dieses Objekt liegt noch keine KI-Auditspur vor.</div>
      ) : (
        <div className="eng-proposal-list">
          {relevant.map((proposal) => {
            const editing = editingId === proposal.proposal_id;
            return (
              <form className="eng-proposal-row" key={proposal.proposal_id} onSubmit={(event) => void save(event, proposal)}>
                <header>
                  <div><span>{proposal.proposal_type}</span><strong>{proposal.prompt}</strong></div>
                  <span className={`status-badge ${proposal.status.toLowerCase()}`}>{proposal.status}</span>
                </header>
                <div className="eng-proposal-objects">
                  {proposal.proposed_objects.map((item, index) => {
                    const validation = proposal.validation_results.find((candidate) => candidate.index === index);
                    const action = proposalAction(item);
                    const applied = proposalItemApplied(item);
                    return (
                      <div className={`eng-proposal-object eng-object-surface ${engineeringObjectTypeClass(proposalObjectType(proposal, item))}`} key={`${proposal.proposal_id}:${index}`}>
                        {editing ? (
                          <div className="eng-proposal-fields">
                            <label>Name<input defaultValue={String(item.name ?? "")} name={`name-${index}`} /></label>
                            <label>Domäne<input defaultValue={String(item.domain ?? "")} name={`domain-${index}`} /></label>
                            <label>Beschreibung<input defaultValue={String(item.description ?? "")} name={`description-${index}`} /></label>
                          </div>
                        ) : (
                          <div>
                            <strong>{String(item.name ?? item.relation_type ?? `Objekt ${index + 1}`)}</strong>
                            <span className={`eng-object-badge ${engineeringObjectTypeClass(proposalObjectType(proposal, item))}`}>{engineeringObjectTypeLabel(proposalObjectType(proposal, item))}</span>
                            <span className={`eng-proposal-action ${action.toLowerCase()}`}>{proposalActionLabel(action)}</span>
                            <span>{String(item.domain ?? "generic")}</span>
                          </div>
                        )}
                        <div className="eng-proposal-object-actions">
                          {validation && <span className={`status-badge ${validation.valid ? "completed" : "outdated"}`}>{validation.valid ? "VALID" : "INVALID"}</span>}
                          <button className="button secondary tiny" disabled={proposal.status === "APPROVED" || Boolean(busy)} onClick={() => setWizard({ proposalId: proposal.proposal_id, index })} type="button">Wizard</button>
                          {applied ? <span className="status-badge approved">Uebernommen</span> : <button className="button primary tiny" disabled={!validation?.valid || Boolean(busy)} onClick={() => void act(`approve:${proposal.proposal_id}:${index}`, () => approveEngineeringProposal(proposal.proposal_id, [index]), "Vorschlag ins kanonische Modell uebernommen.")} type="button">{proposalApplyLabel(action)}</button>}
                        </div>
                        {validation?.errors.map((error) => <small className="routing-issue error" key={error}>{error}</small>)}
                      </div>
                    );
                  })}
                </div>
                <footer>
                  <span>Evidence {proposal.evidence.length} · {proposal.model ?? "Modell nicht angegeben"}</span>
                  <div>
                    {editing ? <><button className="button secondary tiny" onClick={() => setEditingId(null)} type="button">Abbrechen</button><button className="button primary tiny" disabled={Boolean(busy)} type="submit">Speichern</button></> : <button className="button secondary tiny" disabled={proposal.status === "APPROVED" || Boolean(busy)} onClick={() => setEditingId(proposal.proposal_id)} type="button">Bearbeiten</button>}
                    <button className="button secondary tiny" disabled={proposal.status === "APPROVED" || Boolean(busy)} onClick={() => void act(`validate:${proposal.proposal_id}`, () => validateEngineeringProposal(proposal.proposal_id), "Vorschlag validiert.")} type="button">Validieren</button>
                    <button className="button danger tiny" disabled={proposal.status === "APPROVED" || Boolean(busy)} onClick={() => void act(`reject:${proposal.proposal_id}`, () => rejectEngineeringProposal(proposal.proposal_id), "Vorschlag abgelehnt.")} type="button">Ablehnen</button>
                  </div>
                </footer>
              </form>
            );
          })}
        </div>
      )}
      {wizard && wizardProposal && (
        <ProposalObjectWizard
          busy={Boolean(busy)}
          index={wizard.index}
          onClose={() => setWizard(null)}
          onSave={(nextItem) => void saveWizard(wizardProposal, wizard.index, nextItem)}
          proposal={wizardProposal}
        />
      )}
      </div>
    </details>
  );
}

function ProposalObjectWizard({
  busy,
  index,
  onClose,
  onSave,
  proposal,
}: {
  busy: boolean;
  index: number;
  onClose: () => void;
  onSave: (nextItem: Record<string, unknown>) => void;
  proposal: EngineeringProposal;
}) {
  const initialItem = proposal.proposed_objects[index] ?? {};
  const objectType = proposalObjectType(proposal, initialItem);
  const validation = proposal.validation_results.find((candidate) => candidate.index === index);
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<Record<string, unknown>>(initialItem);
  const [schema, setSchema] = useState<EngineeringSchema | null>(null);
  const [references, setReferences] = useState<Partial<Record<EngineeringResource, EngineeringObject[]>>>({});
  const [loadError, setLoadError] = useState("");
  const missing = missingProposalFields(objectType, draft);
  const isLastStep = step === WIZARD_STEPS.length - 1;

  useEffect(() => {
    setDraft(initialItem);
    setStep(0);
  }, [initialItem, proposal.proposal_id, index]);

  useEffect(() => {
    let cancelled = false;
    setLoadError("");
    Promise.all([
      getEngineeringSchema(),
      listAllEngineeringObjects("hardware-nodes"),
      listAllEngineeringObjects("functions"),
      listAllEngineeringObjects("interfaces"),
      listAllEngineeringObjects("messages"),
      listAllEngineeringObjects("signals"),
    ])
      .then(([nextSchema, hardwareNodes, functions, interfaces, messages, signals]) => {
        if (cancelled) return;
        setSchema(nextSchema);
        setReferences({
          "hardware-nodes": hardwareNodes.filter((item) => !isMergedHardwareAlias(item)),
          functions,
          interfaces,
          messages,
          signals,
        });
        setDraft((current) => ({
          ...current,
          ...(objectType === "HardwareNode" && !current.device_type ? { device_type: nextSchema.device_types[0] ?? "ECU" } : {}),
          ...(objectType === "HardwareNode" && !current.device_class ? { device_class: DEFAULT_TYPING_BY_DEVICE_TYPE[String(current.device_type ?? "ECU")]?.deviceClass ?? 1 } : {}),
          ...(objectType === "HardwareNode" && !current.device_typing ? { device_typing: DEFAULT_TYPING_BY_DEVICE_TYPE[String(current.device_type ?? "ECU")]?.typing ?? "Basic Communication Device" } : {}),
          ...(objectType === "HardwareNode" && !current.data_complexity ? { data_complexity: DEFAULT_TYPING_BY_DEVICE_TYPE[String(current.device_type ?? "ECU")]?.complexity ?? "SERVICE_DATA" } : {}),
          ...(objectType === "Interface" && !current.interface_type ? { interface_type: nextSchema.interface_types[0] ?? "CAN" } : {}),
        }));
      })
      .catch((error) => {
        if (!cancelled) setLoadError(error instanceof Error ? error.message : "Referenzen konnten nicht geladen werden.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function updateField(field: string, value: unknown) {
    setDraft((current) => ({ ...current, [field]: value }));
  }

  function updateFunction(value: string) {
    const selectedFunction = references.functions?.find((item) => item.id === value);
    setDraft((current) => ({
      ...current,
      function_id: value || null,
      hardware_node_id: selectedFunction && "hardware_node_id" in selectedFunction ? selectedFunction.hardware_node_id : current.hardware_node_id ?? null,
    }));
  }

  function fillDefaultsFrom(technology: string, type = objectType) {
    const defaults = busDefaultsFor(technology, type);
    setDraft((current) => {
      const next = { ...current };
      for (const [key, value] of Object.entries(defaults)) {
        if (fieldValue(next[key]).trim() === "") next[key] = value;
      }
      return next;
    });
  }

  function updateInterface(value: string) {
    const selectedInterface = references.interfaces?.find((item) => item.id === value);
    setDraft((current) => {
      const next: Record<string, unknown> = { ...current, interface_id: value || null };
      if (selectedInterface) {
        for (const [key, defaultValue] of Object.entries(busDefaultsFor(interfaceTechnology(selectedInterface), "Message"))) {
          if (fieldValue(next[key]).trim() === "") next[key] = defaultValue;
        }
      }
      return next;
    });
  }

  function updateMessage(value: string) {
    const selectedMessage = references.messages?.find((item) => item.id === value);
    const selectedInterface = selectedMessage && "interface_id" in selectedMessage ? objectById(references, selectedMessage.interface_id) : undefined;
    setDraft((current) => {
      const next: Record<string, unknown> = { ...current, message_id: value || null };
      if (selectedInterface) {
        for (const [key, defaultValue] of Object.entries(busDefaultsFor(interfaceTechnology(selectedInterface), "Signal"))) {
          if (fieldValue(next[key]).trim() === "") next[key] = defaultValue;
        }
      }
      return next;
    });
  }

  function objectOptions(type: string) {
    const resource = OBJECT_TYPE_TO_RESOURCE[type];
    return resource ? references[resource] ?? [] : [];
  }

  function normalizedDraft() {
    const next: Record<string, unknown> = { ...draft, object_type: objectType };
    for (const field of ["cycle_ms", "dlc", "start_bit", "length_bits", "factor", "offset_value", "min_value", "max_value"]) {
      if (field in next) next[field] = optionalNumberValue(fieldValue(next[field]));
    }
    for (const field of ["description", "domain", "hardware_node_id", "function_id", "interface_id", "message_id", "message_id_hex", "direction", "display_name", "byte_order", "data_type", "unit", "source_id", "target_id"]) {
      if (field in next && fieldValue(next[field]).trim() === "") next[field] = null;
    }
    if (objectType === "HardwareNode" && !next.device_type) next.device_type = schema?.device_types[0] ?? "ECU";
    if (objectType === "HardwareNode") {
      const defaults = DEFAULT_TYPING_BY_DEVICE_TYPE[String(next.device_type ?? "ECU")] ?? DEFAULT_TYPING_BY_DEVICE_TYPE.ECU;
      next.device_class = optionalNumberValue(fieldValue(next.device_class || defaults.deviceClass));
      if (!next.device_typing) next.device_typing = defaults.typing;
      if (!next.data_complexity) next.data_complexity = defaults.complexity;
      next.classification_status = next.classification_status || "CONFIRMED";
    }
    if (objectType === "Interface" && !next.interface_type) next.interface_type = schema?.interface_types[0] ?? "CAN";
    return next;
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSave(normalizedDraft());
  }

  return (
    <div className="proposal-wizard-backdrop" role="presentation">
      <form aria-modal="true" className="proposal-wizard" onSubmit={submit} role="dialog">
        <header>
          <div>
            <p className="eyebrow">Proposal Wizard</p>
            <h3>{String(draft.name ?? draft.relation_type ?? `Objekt ${index + 1}`)}</h3>
            <span>{objectType} · {proposal.prompt}</span>
          </div>
          <button className="button secondary tiny" onClick={onClose} type="button">Abbrechen</button>
        </header>

        <div className="proposal-wizard-steps">
          {WIZARD_STEPS.map((label, stepIndex) => (
            <button
              className={stepIndex === step ? "active" : ""}
              key={label}
              onClick={() => setStep(stepIndex)}
              type="button"
            >
              <span>{String(stepIndex + 1).padStart(2, "0")}</span>
              {label}
            </button>
          ))}
        </div>

        {loadError && <div className="notice error">{loadError}</div>}

        {step === 0 && (
          <div className="proposal-wizard-grid">
            {objectType !== "Relation" && (
              <>
                <WizardField label="Name" required value={fieldValue(draft.name)} onChange={(value) => updateField("name", value)} />
                <WizardField label="Domäne" value={fieldValue(draft.domain)} onChange={(value) => updateField("domain", value)} placeholder="z. B. automotive" />
                <label className="field full-width">
                  <span>Beschreibung</span>
                  <textarea onChange={(event) => updateField("description", event.target.value)} rows={3} value={fieldValue(draft.description)} />
                </label>
              </>
            )}
            {objectType === "Relation" && (
              <>
                <label className="field">
                  <span>Relation</span>
                  <select required onChange={(event) => updateField("relation_type", event.target.value)} value={fieldValue(draft.relation_type)}>
                    <option value="">Auswählen</option>
                    {RELATION_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
                  </select>
                </label>
                <label className="field">
                  <span>Quelle-Typ</span>
                  <select required onChange={(event) => updateField("source_type", event.target.value)} value={fieldValue(draft.source_type)}>
                    <option value="">Auswählen</option>
                    {Object.keys(OBJECT_TYPE_TO_RESOURCE).map((type) => <option key={type} value={type}>{type}</option>)}
                  </select>
                </label>
                <label className="field">
                  <span>Ziel-Typ</span>
                  <select required onChange={(event) => updateField("target_type", event.target.value)} value={fieldValue(draft.target_type)}>
                    <option value="">Auswählen</option>
                    {Object.keys(OBJECT_TYPE_TO_RESOURCE).map((type) => <option key={type} value={type}>{type}</option>)}
                  </select>
                </label>
              </>
            )}
          </div>
        )}

        {step === 1 && (
          <div className="proposal-wizard-grid">
            {objectType === "HardwareNode" && (
              <>
                <label className="field">
                  <span>Gerätetyp</span>
                  <select required onChange={(event) => {
                    const defaults = DEFAULT_TYPING_BY_DEVICE_TYPE[event.target.value];
                    updateField("device_type", event.target.value);
                    if (defaults) {
                      updateField("device_class", defaults.deviceClass);
                      updateField("device_typing", defaults.typing);
                      updateField("data_complexity", defaults.complexity);
                    }
                  }} value={fieldValue(draft.device_type || schema?.device_types[0] || "ECU")}>
                    {(schema?.device_types ?? ["ECU"]).map((type) => <option key={type} value={type}>{engineeringDeviceTypeLabel(type)}</option>)}
                  </select>
                </label>
                <label className="field">
                  <span>Class</span>
                  <select required onChange={(event) => updateField("device_class", Number(event.target.value))} value={fieldValue(draft.device_class || 1)}>
                    {(schema?.device_classes ?? [{ value: 1, label: "Basic" }]).map((item) => <option key={item.value} value={item.value}>{item.value} · {item.label}</option>)}
                  </select>
                </label>
                <label className="field">
                  <span>Typisierung</span>
                  <select required onChange={(event) => updateField("device_typing", event.target.value)} value={fieldValue(draft.device_typing || "Basic Communication Device")}>
                    {(schema?.device_typings ?? ["Basic Communication Device"]).map((type) => <option key={type} value={type}>{type}</option>)}
                  </select>
                </label>
                <label className="field">
                  <span>Data Complexity</span>
                  <select required onChange={(event) => updateField("data_complexity", event.target.value)} value={fieldValue(draft.data_complexity || "SERVICE_DATA")}>
                    {(schema?.data_complexities ?? ["SERVICE_DATA"]).map((type) => <option key={type} value={type}>{type}</option>)}
                  </select>
                </label>
              </>
            )}
            {objectType === "Function" && (
              <ReferenceSelect label="Hardware-Knoten" options={references["hardware-nodes"] ?? []} proposal={proposal} references={references} required value={fieldValue(draft.hardware_node_id)} onChange={(value) => updateField("hardware_node_id", value || null)} draft={draft} />
            )}
            {objectType === "Interface" && (
              <>
                <ReferenceSelect label="Funktion" options={references.functions ?? []} proposal={proposal} references={references} required value={fieldValue(draft.function_id)} onChange={updateFunction} draft={draft} />
                <label className="field">
                  <span>Interface-Typ</span>
                  <select required onChange={(event) => updateField("interface_type", event.target.value)} value={fieldValue(draft.interface_type || schema?.interface_types[0] || "CAN")}>
                    {(schema?.interface_types ?? ["CAN"]).map((type) => <option key={type} value={type}>{type}</option>)}
                  </select>
                </label>
              </>
            )}
            {objectType === "Message" && (
              <>
                <ReferenceSelect label="Interface" options={references.interfaces ?? []} proposal={proposal} references={references} required value={fieldValue(draft.interface_id)} onChange={updateInterface} draft={draft} />
                {draft.interface_id && <button className="button secondary" onClick={() => fillDefaultsFrom(interfaceTechnology(objectById(references, draft.interface_id)), "Message")} type="button">Leere Felder per Bus füllen</button>}
              </>
            )}
            {objectType === "Signal" && (
              <>
                <ReferenceSelect label="Message" options={references.messages ?? []} proposal={proposal} references={references} required value={fieldValue(draft.message_id)} onChange={updateMessage} draft={draft} />
                {draft.message_id && <button className="button secondary" onClick={() => {
                  const message = objectById(references, draft.message_id);
                  const iface = message && "interface_id" in message ? objectById(references, message.interface_id) : undefined;
                  fillDefaultsFrom(interfaceTechnology(iface), "Signal");
                }} type="button">Leere Felder per Bus füllen</button>}
              </>
            )}
            {objectType === "Relation" && (
              <>
                <ReferenceSelect label="Quelle" options={objectOptions(fieldValue(draft.source_type))} proposal={proposal} references={references} required value={fieldValue(draft.source_id)} onChange={(value) => updateField("source_id", value || null)} draft={draft} />
                <ReferenceSelect label="Ziel" options={objectOptions(fieldValue(draft.target_type))} proposal={proposal} references={references} required value={fieldValue(draft.target_id)} onChange={(value) => updateField("target_id", value || null)} draft={draft} />
              </>
            )}
          </div>
        )}

        {step === 2 && (
          <div className="proposal-wizard-grid three">
            {objectType === "Message" && (
              <>
                <WizardField label="Message-ID" value={fieldValue(draft.message_id_hex)} onChange={(value) => updateField("message_id_hex", value)} placeholder="0x1A0" />
                <label className="field">
                  <span>Richtung</span>
                  <select onChange={(event) => updateField("direction", event.target.value || null)} value={fieldValue(draft.direction)}>
                    <option value="">Offen</option>
                    {(schema?.message_directions ?? ["tx", "rx", "bidirectional"]).map((dir) => <option key={dir} value={dir}>{dir}</option>)}
                  </select>
                </label>
                <WizardField inputMode="decimal" label="Zyklus (ms)" type="number" value={fieldValue(draft.cycle_ms)} onChange={(value) => updateField("cycle_ms", value)} />
                <WizardField inputMode="numeric" label="DLC" type="number" value={fieldValue(draft.dlc)} onChange={(value) => updateField("dlc", value)} />
              </>
            )}
            {objectType === "Signal" && (
              <>
                <WizardField label="Anzeigename" value={fieldValue(draft.display_name)} onChange={(value) => updateField("display_name", value)} />
                <WizardField inputMode="numeric" label="Start-Bit" type="number" value={fieldValue(draft.start_bit)} onChange={(value) => updateField("start_bit", value)} />
                <WizardField inputMode="numeric" label="Länge (Bit)" type="number" value={fieldValue(draft.length_bits)} onChange={(value) => updateField("length_bits", value)} />
                <label className="field">
                  <span>Byte Order</span>
                  <select onChange={(event) => updateField("byte_order", event.target.value || null)} value={fieldValue(draft.byte_order)}>
                    <option value="">Offen</option>
                    {SIGNAL_BYTE_ORDERS.map((order) => <option key={order} value={order}>{order}</option>)}
                  </select>
                </label>
                <WizardField label="Datentyp" value={fieldValue(draft.data_type)} onChange={(value) => updateField("data_type", value)} placeholder="unsigned" />
                <WizardField label="Einheit" value={fieldValue(draft.unit)} onChange={(value) => updateField("unit", value)} />
                <WizardField inputMode="decimal" label="Faktor" type="number" value={fieldValue(draft.factor)} onChange={(value) => updateField("factor", value)} />
                <WizardField inputMode="decimal" label="Offset" type="number" value={fieldValue(draft.offset_value)} onChange={(value) => updateField("offset_value", value)} />
                <WizardField inputMode="decimal" label="Min" type="number" value={fieldValue(draft.min_value)} onChange={(value) => updateField("min_value", value)} />
                <WizardField inputMode="decimal" label="Max" type="number" value={fieldValue(draft.max_value)} onChange={(value) => updateField("max_value", value)} />
              </>
            )}
            {!["Message", "Signal"].includes(objectType) && (
              <div className="proposal-wizard-help">
                <strong>Keine weiteren Pflichtdetails</strong>
                <span>Für diesen Objekttyp reichen Identität und Zuordnung aus, damit die Backend-Validierung entscheiden kann.</span>
              </div>
            )}
          </div>
        )}

        {step === 3 && (
          <div className="proposal-wizard-review">
            <div className={missing.length ? "proposal-wizard-verdict invalid" : "proposal-wizard-verdict valid"}>
              <strong>{missing.length ? "Noch nicht valide" : "Bereit zur Validierung"}</strong>
              <span>{missing.length ? `${missing.length} Pflichtfeld(er) fehlen.` : "Alle bekannten Pflichtfelder sind gefüllt."}</span>
            </div>
            {missing.length > 0 && (
              <div className="proposal-wizard-checks">
                {missing.map((field) => <span key={field}>{FIELD_LABELS[field] ?? field}</span>)}
              </div>
            )}
            {validation?.errors.length ? (
              <div className="proposal-wizard-errors">
                <strong>Aktuelle Backend-Findings</strong>
                {validation.errors.map((error) => <small className="routing-issue error" key={error}>{error}</small>)}
              </div>
            ) : null}
            <ProposalWizardSummary objectType={objectType} references={references} values={normalizedDraft()} />
          </div>
        )}

        <footer>
          <button className="button secondary" disabled={step === 0} onClick={() => setStep((current) => Math.max(0, current - 1))} type="button">Zurück</button>
          {!isLastStep ? (
            <button className="button primary" onClick={() => setStep((current) => Math.min(WIZARD_STEPS.length - 1, current + 1))} type="button">Weiter</button>
          ) : (
            <button className="button primary" disabled={busy || missing.length > 0} type="submit">{busy ? "Speichert ..." : "Speichern & validieren"}</button>
          )}
        </footer>
      </form>
    </div>
  );
}

function ProposalWizardSummary({
  objectType,
  references,
  values,
}: {
  objectType: string;
  references: Partial<Record<EngineeringResource, EngineeringObject[]>>;
  values: Record<string, unknown>;
}) {
  const identityFields = ["name", "domain", "description"].filter((field) => field in values);
  const relationFields = objectType === "Relation"
    ? ["relation_type", "source_type", "source_id", "target_type", "target_id"]
    : [];
  const assignmentFields = {
    HardwareNode: ["device_type", "device_class", "device_typing", "data_complexity", "classification_status"],
    HardwareNetworkInterface: ["hardware_node_id", "technology", "network_ref"],
    Function: ["hardware_node_id"],
    Interface: ["function_id", "hardware_node_id", "interface_type"],
    Message: ["interface_id"],
    Signal: ["message_id"],
  }[objectType] ?? [];
  const detailFields = {
    HardwareNetworkInterface: ["controller_ref", "physical_port_ref", "channel_index", "bitrate", "data_bitrate", "static_load", "runtime_load", "target_load_limit", "warning_load_limit", "hard_load_limit", "status"],
    Message: ["message_id_hex", "direction", "cycle_ms", "dlc"],
    Signal: ["display_name", "start_bit", "length_bits", "byte_order", "data_type", "factor", "offset_value", "unit", "min_value", "max_value"],
  }[objectType] ?? [];

  const sections = [
    { title: "Identität", fields: identityFields },
    { title: objectType === "Relation" ? "Relation" : "Zuordnung", fields: relationFields.length ? relationFields : assignmentFields },
    { title: "Technische Details", fields: detailFields },
  ].filter((section) => section.fields.length > 0);

  return (
    <div className="proposal-wizard-summary">
      {sections.map((section) => (
        <section key={section.title}>
          <h4>{section.title}</h4>
          <dl>
            {section.fields.map((field) => (
              <Fragment key={field}>
                <dt>{FIELD_LABELS[field] ?? field}</dt>
                <dd>{field.endsWith("_id") ? referenceDisplay(references, field, values[field]) : fieldValue(values[field]) || "Nicht gesetzt"}</dd>
              </Fragment>
            ))}
          </dl>
        </section>
      ))}
    </div>
  );
}

function WizardField({
  inputMode,
  label,
  onChange,
  placeholder,
  required,
  type = "text",
  value,
}: {
  inputMode?: "decimal" | "numeric";
  label: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
  type?: string;
  value: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input inputMode={inputMode} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} required={required} type={type} value={value} />
    </label>
  );
}

function ReferenceSelect({
  draft,
  label,
  onChange,
  options,
  proposal,
  references,
  required,
  value,
}: {
  draft: Record<string, unknown>;
  label: string;
  onChange: (value: string) => void;
  options: EngineeringObject[];
  proposal: EngineeringProposal;
  references: Partial<Record<EngineeringResource, EngineeringObject[]>>;
  required?: boolean;
  value: string;
}) {
  const suggestions = referenceSuggestions(proposal, draft, options, references);
  return (
    <div className="proposal-reference-picker">
      <label className="field">
        <span>{label}</span>
        <select disabled={options.length === 0} onChange={(event) => onChange(event.target.value)} required={required} value={value}>
          <option value="">{options.length ? "Auswählen" : "Keine Referenz vorhanden"}</option>
          {options.map((item) => <option key={item.id} value={item.id}>{optionLabel(item, references)}</option>)}
        </select>
      </label>
      {options.length === 0 && (
        <p className="proposal-reference-empty">
          {referenceEmptyHint(label)}
        </p>
      )}
      {suggestions.length > 0 && (
        <div className="proposal-ai-suggestions">
          <span>KI-Vorschläge</span>
          {suggestions.map((suggestion) => (
            <button className={suggestion.id === value ? "active" : ""} key={suggestion.id} onClick={() => onChange(suggestion.id)} type="button">
              <strong>{suggestion.confidence}%</strong>
              <span>{suggestion.label}</span>
              <small>{suggestion.reason}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function referenceEmptyHint(label: string) {
  const subject = label.toLowerCase();
  if (subject.includes("message")) return "Es gibt noch keine Messages im Modell. Lege zuerst eine Message auf einem Interface an.";
  if (subject.includes("interface")) return "Es gibt noch keine Interfaces im Modell. Lege zuerst eine Function und ein Interface an.";
  if (subject.includes("funktion")) return "Es gibt noch keine Functions im Modell. Lege zuerst eine Function auf einem Hardware-Knoten an.";
  if (subject.includes("hardware")) return "Es gibt noch keine Hardware-Knoten im Modell. Lege zuerst Hardware an.";
  return "Das benötigte Elternobjekt ist noch nicht im Modell angelegt.";
}

function CreateForm({
  hardwarePreset,
  onClose,
  resource,
  schema,
  onCreated,
}: {
  hardwarePreset: string | null;
  onClose: () => void;
  resource: EngineeringResource;
  schema: EngineeringSchema | null;
  onCreated: () => void;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const [step, setStep] = useState(0);
  const [reviewValues, setReviewValues] = useState<Record<string, unknown>>({});
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [deviceType, setDeviceType] = useState(
    hardwarePreset ?? schema?.device_types[0] ?? "ECU",
  );
  const initialHardwareDefaults = DEFAULT_TYPING_BY_DEVICE_TYPE[hardwarePreset ?? "ECU"] ?? DEFAULT_TYPING_BY_DEVICE_TYPE.ECU;
  const [deviceClass, setDeviceClass] = useState(initialHardwareDefaults.deviceClass);
  const [deviceTyping, setDeviceTyping] = useState(initialHardwareDefaults.typing);
  const [dataComplexity, setDataComplexity] = useState(initialHardwareDefaults.complexity);
  const [parents, setParents] = useState<EngineeringObject[]>([]);
  const [hardwareInterfaces, setHardwareInterfaces] = useState<EngineeringObject[]>([]);
  const [parentId, setParentId] = useState("");
  const [loadingParents, setLoadingParents] = useState(false);
  const hierarchy = RESOURCE_HIERARCHY[resource];
  const objectType = RESOURCE_TO_OBJECT_TYPE[resource];
  const references = useMemo<Partial<Record<EngineeringResource, EngineeringObject[]>>>(() => (
    hierarchy ? { [hierarchy.parentResource]: parents } : {}
  ), [hierarchy, parents]);
  const missing = missingProposalFields(objectType, reviewValues);

  useEffect(() => {
    if (!hierarchy) {
      setParents([]);
      setParentId("");
      return;
    }
    let cancelled = false;
    setLoadingParents(true);
    listAllEngineeringObjects(hierarchy.parentResource)
      .then((items) => {
        if (cancelled) return;
        const availableItems = hierarchy.parentResource === "hardware-nodes"
          ? items.filter((item) => !isMergedHardwareAlias(item))
          : items;
        setParents(availableItems);
        setParentId(availableItems[0]?.id ?? "");
      })
      .catch((err) => {
        if (!cancelled) {
          setFormError(err instanceof Error ? err.message : "Übergeordnete Objekte konnten nicht geladen werden.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingParents(false);
      });
    return () => {
      cancelled = true;
    };
  }, [hierarchy]);

  useEffect(() => {
    if (resource !== "messages") {
      setHardwareInterfaces([]);
      return;
    }
    let cancelled = false;
    listAllEngineeringObjects("hardware-interfaces")
      .then((items) => {
        if (!cancelled) setHardwareInterfaces(items);
      })
      .catch(() => {
        if (!cancelled) setHardwareInterfaces([]);
      });
    return () => {
      cancelled = true;
    };
  }, [resource]);

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !submitting) onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose, submitting]);

  function optionalFormNumber(form: FormData, name: string) {
    const value = form.get(name);
    return value === null || value === "" ? null : Number(value);
  }

  function payloadFrom(form: FormData) {
    const parent = parents.find((item) => item.id === parentId);
    let normalizedName: unknown = form.get("name");
    if (resource === "interfaces") normalizedName = normalizeInterfaceName(normalizedName);
    if (resource === "messages") normalizedName = normalizeMessageName(normalizedName);
    if (resource === "signals") normalizedName = normalizeSignalName(normalizedName, parent?.name);
    const payload: Record<string, unknown> = {
      name: normalizedName,
      description: form.get("description") || null,
      domain: form.get("domain") || null,
    };
    if (resource === "hardware-nodes") {
      payload.device_type = form.get("device_type");
      payload.device_class = optionalFormNumber(form, "device_class");
      payload.device_typing = form.get("device_typing") || null;
      payload.data_complexity = form.get("data_complexity") || null;
      payload.classification_status = "CONFIRMED";
    }
    if (resource === "hardware-interfaces") {
      payload.hardware_node_id = parentId;
      payload.technology = form.get("technology") || "CAN_FD";
      payload.controller_ref = form.get("controller_ref") || null;
      payload.physical_port_ref = form.get("physical_port_ref") || null;
      payload.channel_index = optionalFormNumber(form, "channel_index");
      payload.network_ref = form.get("network_ref") || null;
      payload.bitrate = optionalFormNumber(form, "bitrate");
      payload.data_bitrate = optionalFormNumber(form, "data_bitrate");
      payload.status = form.get("status") || "UNMAPPED";
      payload.message_refs = [];
      payload.capabilities = {
        reuse_existing_capacity_first: true,
        multiple_messages_allowed: true,
        multiple_functions_allowed: true,
      };
      payload.static_load = optionalFormNumber(form, "static_load");
      payload.runtime_load = optionalFormNumber(form, "runtime_load");
      payload.target_load_limit = optionalFormNumber(form, "target_load_limit");
      payload.warning_load_limit = optionalFormNumber(form, "warning_load_limit");
      payload.hard_load_limit = optionalFormNumber(form, "hard_load_limit");
    }
    if (resource === "functions") payload.hardware_node_id = parentId;
    if (resource === "interfaces") payload.interface_type = form.get("interface_type");
    if (resource === "interfaces" && parent) {
      payload.function_id = parentId;
      if ("hardware_node_id" in parent) payload.hardware_node_id = parent.hardware_node_id;
    }
    if (resource === "messages") {
      payload.interface_id = parentId;
      payload.hardware_interface_id = form.get("hardware_interface_id") || null;
      payload.message_id_hex = form.get("message_id_hex") || null;
      payload.direction = form.get("direction") || null;
      payload.cycle_ms = optionalFormNumber(form, "cycle_ms");
      payload.dlc = optionalFormNumber(form, "dlc");
      payload.configuration = requirementPayload(form, "requirement_");
    }
    if (resource === "signals") {
      payload.message_id = parentId;
      payload.display_name = form.get("display_name") || null;
      payload.start_bit = optionalFormNumber(form, "start_bit");
      payload.length_bits = optionalFormNumber(form, "length_bits");
      payload.byte_order = form.get("byte_order") || null;
      payload.data_type = form.get("data_type") || null;
      payload.factor = optionalFormNumber(form, "factor");
      payload.offset_value = optionalFormNumber(form, "offset_value");
      payload.unit = form.get("unit") || null;
      payload.min_value = optionalFormNumber(form, "min_value");
      payload.max_value = optionalFormNumber(form, "max_value");
      payload.communication = requirementPayload(form, "requirement_");
    }
    return payload;
  }

  function openStep(nextStep: number) {
    if (nextStep === WIZARD_STEPS.length - 1 && formRef.current) {
      setReviewValues(payloadFrom(new FormData(formRef.current)));
    }
    setStep(nextStep);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setFormError("");
    const form = new FormData(event.currentTarget);
    const payload = payloadFrom(form);
    const parent = parents.find((item) => item.id === parentId);
    if (hierarchy && !parent) {
      setFormError(`Wähle zuerst eine übergeordnete ${hierarchy.parentLabel}.`);
      setSubmitting(false);
      return;
    }
    try {
      await createEngineeringObject(resource, payload);
      onCreated();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Anlegen fehlgeschlagen.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="proposal-wizard-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !submitting && onClose()} role="presentation">
    <form aria-modal="true" className="proposal-wizard eng-object-wizard" onMouseDown={(event) => event.stopPropagation()} onSubmit={submit} ref={formRef} role="dialog">
      <header>
        <div>
          <p className="eyebrow">Objekt-Wizard</p>
          <h3>{RESOURCE_LABELS[resource]} anlegen</h3>
          <span>Das Objekt wird nach der Prüfung im kanonischen Engineering-Modell gespeichert.</span>
        </div>
        <button className="button secondary tiny" disabled={submitting} onClick={onClose} type="button">Abbrechen</button>
      </header>

      <div className="proposal-wizard-steps">
        {WIZARD_STEPS.map((label, index) => (
          <button className={index === step ? "active" : ""} key={label} onClick={() => openStep(index)} type="button"><span>{String(index + 1).padStart(2, "0")}</span>{label}</button>
        ))}
      </div>

      <div className="proposal-wizard-grid" hidden={step !== 0}>
        <div className="field">
          <label htmlFor="name">Name</label>
          <input autoFocus id="name" name="name" placeholder={hardwarePreset ? `${HARDWARE_PRESETS.find((item) => item.deviceType === hardwarePreset)?.label} Name` : undefined} required type="text" />
        </div>
        <div className="field">
          <label htmlFor="domain">Domäne</label>
          <input id="domain" name="domain" placeholder="z. B. automotive" type="text" />
        </div>
        <div className="field full-width">
          <label htmlFor="description">Beschreibung</label>
          <textarea id="description" name="description" rows={3} />
        </div>
      </div>

      <div className="proposal-wizard-grid" hidden={step !== 1}>
      {hierarchy && (
        <div className="field eng-parent-field">
          <label htmlFor="parent_id">Enthalten in: {hierarchy.parentLabel}</label>
          <select
            disabled={loadingParents || parents.length === 0}
            id="parent_id"
            onChange={(event) => setParentId(event.target.value)}
            required
            value={parentId}
          >
            {loadingParents && <option value="">Wird geladen …</option>}
            {!loadingParents && parents.length === 0 && <option value="">Kein übergeordnetes Objekt vorhanden</option>}
            {parents.map((parent) => (
              <option key={parent.id} value={parent.id}>
                {parent.name}{parent.domain ? ` · ${parent.domain}` : ""}
              </option>
            ))}
          </select>
          {!loadingParents && parents.length === 0 && (
            <p className="field-hint">Lege zuerst eine {hierarchy.parentLabel} an.</p>
          )}
        </div>
      )}
      {resource === "hardware-nodes" && (
        <div className="field">
          <label htmlFor="device_type">Gerätetyp</label>
          <select
            id="device_type"
            name="device_type"
            onChange={(event) => {
              const next = event.target.value;
              const defaults = DEFAULT_TYPING_BY_DEVICE_TYPE[next];
              setDeviceType(next);
              if (defaults) {
                setDeviceClass(defaults.deviceClass);
                setDeviceTyping(defaults.typing);
                setDataComplexity(defaults.complexity);
              }
            }}
            required
            value={deviceType}
          >
            {(schema?.device_types ?? ["ECU"]).map((type) => (
              <option key={type} value={type}>
                {engineeringDeviceTypeLabel(type)}
              </option>
            ))}
          </select>
        </div>
      )}
      {resource === "hardware-nodes" && (
        <>
          <div className="field">
            <label htmlFor="device_class">Class</label>
            <select id="device_class" name="device_class" onChange={(event) => setDeviceClass(Number(event.target.value))} required value={deviceClass}>
              {(schema?.device_classes ?? [{ value: 1, label: "Basic" }]).map((item) => (
                <option key={item.value} value={item.value}>{item.value} · {item.label}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="device_typing">Typisierung</label>
            <select id="device_typing" name="device_typing" onChange={(event) => setDeviceTyping(event.target.value)} required value={deviceTyping}>
              {(schema?.device_typings ?? ["Basic Communication Device"]).map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="data_complexity">Data Complexity</label>
            <select id="data_complexity" name="data_complexity" onChange={(event) => setDataComplexity(event.target.value)} required value={dataComplexity}>
              {(schema?.data_complexities ?? ["SERVICE_DATA"]).map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
          </div>
        </>
      )}

      {resource === "interfaces" && (
        <div className="field">
          <label htmlFor="interface_type">Interface-Typ</label>
          <select id="interface_type" name="interface_type" required>
            {(schema?.interface_types ?? ["CAN"]).map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </div>
      )}
      {resource === "hardware-interfaces" && (
        <div className="field">
          <label htmlFor="technology">Technologie</label>
          <select id="technology" name="technology" required>
            {(schema?.interface_types ?? ["CAN_FD"]).map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </div>
      )}
      </div>

      <div className="proposal-wizard-grid three" hidden={step !== 2}>
      {!(["hardware-interfaces", "messages", "signals"] as EngineeringResource[]).includes(resource) && (
        <div className="proposal-wizard-help">
          <strong>Keine weiteren technischen Pflichtfelder</strong>
          <span>Identität und Zuordnung reichen für diesen Objekttyp aus. Zusätzliche Beziehungen können anschließend am Objekt gepflegt werden.</span>
        </div>
      )}

      {resource === "hardware-interfaces" && (
        <>
        <div className="form-grid three">
          <div className="field"><label htmlFor="controller_ref">Controller</label><input id="controller_ref" name="controller_ref" placeholder="CAN0" type="text" /></div>
          <div className="field"><label htmlFor="physical_port_ref">Physischer Port</label><input id="physical_port_ref" name="physical_port_ref" placeholder="Port 1" type="text" /></div>
          <div className="field"><label htmlFor="channel_index">Kanal</label><input defaultValue="1" id="channel_index" min="1" name="channel_index" type="number" /></div>
          <div className="field"><label htmlFor="network_ref">Netzwerk / Bussegment</label><input id="network_ref" name="network_ref" placeholder="CAN_FD_A" type="text" /></div>
          <div className="field"><label htmlFor="bitrate">Bitrate</label><input defaultValue="500000" id="bitrate" min="1" name="bitrate" step="1" type="number" /></div>
          <div className="field"><label htmlFor="data_bitrate">Data Bitrate</label><input defaultValue="2000000" id="data_bitrate" min="1" name="data_bitrate" step="1" type="number" /></div>
          <div className="field"><label htmlFor="target_load_limit">Ziel-Last (%)</label><input defaultValue="60" id="target_load_limit" min="0" name="target_load_limit" step="any" type="number" /></div>
          <div className="field"><label htmlFor="warning_load_limit">Warn-Last (%)</label><input defaultValue="75" id="warning_load_limit" min="0" name="warning_load_limit" step="any" type="number" /></div>
          <div className="field"><label htmlFor="hard_load_limit">Harte Last (%)</label><input defaultValue="90" id="hard_load_limit" min="0" name="hard_load_limit" step="any" type="number" /></div>
          <div className="field"><label htmlFor="static_load">Statische Last (%)</label><input id="static_load" min="0" name="static_load" step="any" type="number" /></div>
          <div className="field"><label htmlFor="runtime_load">Runtime Last (%)</label><input id="runtime_load" min="0" name="runtime_load" step="any" type="number" /></div>
          <div className="field"><label htmlFor="status">Status</label><select defaultValue="UNMAPPED" id="status" name="status">{["CONFIGURED", "UNMAPPED", "ACTIVE", "OUTDATED", "OVERLOADED", "ERROR"].map((value) => <option key={value}>{value}</option>)}</select></div>
        </div>
        </>
      )}

      {resource === "messages" && (
        <>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="hardware_interface_id">Hardware Interface</label>
            <select id="hardware_interface_id" name="hardware_interface_id">
              <option value="">Noch nicht zugewiesen</option>
              {hardwareInterfaces.map((hardwareInterface) => (
                <option key={hardwareInterface.id} value={hardwareInterface.id}>
                  {hardwareInterface.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="message_id_hex">Message-ID (hex)</label>
            <input id="message_id_hex" name="message_id_hex" type="text" placeholder="0x1A0" />
          </div>
          <div className="field">
            <label htmlFor="direction">Richtung</label>
            <select id="direction" name="direction">
              {(schema?.message_directions ?? ["tx", "rx", "bidirectional"]).map((dir) => (
                <option key={dir} value={dir}>
                  {dir}
                </option>
              ))}
            </select>
          </div>
          <div className="field"><label htmlFor="cycle_ms">Zyklus (ms)</label><input id="cycle_ms" min="0.001" name="cycle_ms" step="0.001" type="number" /></div>
          <div className="field"><label htmlFor="dlc">DLC</label><input id="dlc" min="0" name="dlc" type="number" /></div>
        </div>
        <RequirementFields prefix="requirement_" />
        </>
      )}

      {resource === "signals" && (
        <>
        <div className="form-grid three">
          <div className="field">
            <label htmlFor="display_name">Anzeigename</label>
            <input id="display_name" name="display_name" type="text" />
          </div>
          <div className="field">
            <label htmlFor="start_bit">Start-Bit</label>
            <input id="start_bit" min="0" name="start_bit" type="number" />
          </div>
          <div className="field">
            <label htmlFor="length_bits">Länge (Bit)</label>
            <input id="length_bits" min="1" name="length_bits" type="number" />
          </div>
          <div className="field"><label htmlFor="byte_order">Byte-Reihenfolge</label><select id="byte_order" name="byte_order"><option value="">—</option>{SIGNAL_BYTE_ORDERS.map((order) => <option key={order} value={order}>{order}</option>)}</select></div>
          <div className="field"><label htmlFor="data_type">Datentyp</label><input id="data_type" list="create-signal-data-types" name="data_type" placeholder="unsigned" type="text" /><datalist id="create-signal-data-types"><option value="unsigned" /><option value="signed" /><option value="float" /><option value="boolean" /><option value="string" /><option value="bytes" /></datalist></div>
          <div className="field"><label htmlFor="factor">Faktor</label><input id="factor" name="factor" step="any" type="number" /></div>
          <div className="field"><label htmlFor="offset_value">Offset</label><input id="offset_value" name="offset_value" step="any" type="number" /></div>
          <div className="field"><label htmlFor="unit">Einheit</label><input id="unit" name="unit" type="text" /></div>
          <div className="field"><label htmlFor="min_value">Minimum</label><input id="min_value" name="min_value" step="any" type="number" /></div>
          <div className="field"><label htmlFor="max_value">Maximum</label><input id="max_value" name="max_value" step="any" type="number" /></div>
        </div>
        <RequirementFields prefix="requirement_" />
        </>
      )}
      </div>

      <div className="proposal-wizard-review" hidden={step !== 3}>
        <div className={missing.length ? "proposal-wizard-verdict invalid" : "proposal-wizard-verdict valid"}>
          <strong>{missing.length ? "Noch nicht vollständig" : "Bereit zum Anlegen"}</strong>
          <span>{missing.length ? `${missing.length} Pflichtfeld(er) fehlen.` : "Alle bekannten Pflichtfelder sind gefüllt."}</span>
        </div>
        {missing.length > 0 && <div className="proposal-wizard-checks">{missing.map((field) => <span key={field}>{FIELD_LABELS[field] ?? field}</span>)}</div>}
        <ProposalWizardSummary objectType={objectType} references={references} values={reviewValues} />
      </div>

      {formError && <div className="notice error">{formError}</div>}

      <footer>
        <button className="button secondary" disabled={step === 0 || submitting} onClick={() => openStep(Math.max(0, step - 1))} type="button">Zurück</button>
        {step < WIZARD_STEPS.length - 1 ? (
          <button className="button primary" disabled={loadingParents} onClick={() => openStep(Math.min(WIZARD_STEPS.length - 1, step + 1))} type="button">Weiter</button>
        ) : (
          <button className="button primary" disabled={submitting || missing.length > 0 || Boolean(hierarchy && !parentId)} type="submit">{submitting ? "Wird angelegt …" : "Objekt anlegen"}</button>
        )}
      </footer>
    </form>
    </div>
  );
}

function DetailPanel({
  item,
  initialEdit = false,
  peerItems,
  referenceObjects,
  referenceNames,
  resource,
  relations,
  schema,
  onChanged,
  onDeleted,
}: {
  item: EngineeringObject;
  initialEdit?: boolean;
  peerItems: EngineeringObject[];
  referenceObjects: EngineeringObject[];
  referenceNames: Record<string, string>;
  resource: EngineeringResource;
  relations: EngineeringRelation[];
  schema: EngineeringSchema | null;
  onChanged: () => void;
  onDeleted: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [showRelationForm, setShowRelationForm] = useState(false);
  const [showEdit, setShowEdit] = useState(false);

  useEffect(() => {
    setShowEdit(initialEdit);
    setNotice("");
  }, [initialEdit, item.id]);

  async function setLifecycle(next: string) {
    setBusy(true);
    setNotice("");
    try {
      await updateEngineeringObject(resource, item.id, { lifecycle_state: next });
      onChanged();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Aktualisierung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  async function setReview(next: string) {
    setBusy(true);
    setNotice("");
    try {
      await updateEngineeringObject(resource, item.id, { review_state: next });
      onChanged();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Aktualisierung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    setNotice("");
    try {
      await deleteEngineeringObject(resource, item.id);
      onDeleted();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Löschen fehlgeschlagen (nur 'draft' löschbar).");
    } finally {
      setBusy(false);
    }
  }

  async function removeRelation(relationId: string) {
    setBusy(true);
    try {
      await deleteEngineeringRelation(relationId);
      onChanged();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Relation konnte nicht gelöscht werden.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="eng-detail-dropdown">
      <details className="eng-detail-section" open>
        <summary>
          <span className={`eng-object-badge ${engineeringObjectTypeClass(engineeringResourceType(resource))}`}>{engineeringObjectTypeLabel(engineeringResourceType(resource))}</span>
          <strong>{item.name}</strong>
        </summary>
        <div className="eng-detail-section-body">
          <div className="panel-heading">
            <div>
              <p className={`eyebrow eng-object-label ${engineeringObjectTypeClass(engineeringResourceType(resource))}`}>{engineeringObjectTypeLabel(engineeringResourceType(resource))}</p>
              <h2>{item.name}</h2>
            </div>
            <button className="button secondary tiny" onClick={() => setShowEdit((value) => !value)} type="button">
              {showEdit ? "Abbrechen" : "Bearbeiten"}
            </button>
          </div>
          {showEdit && (
            <EditObjectForm
              item={item}
              referenceObjects={referenceObjects}
              referenceNames={referenceNames}
              resource={resource}
              schema={schema}
              onSaved={() => {
                setShowEdit(false);
                onChanged();
              }}
            />
          )}
          <dl className="overview-list">
            <div>
              <dt>Domäne</dt>
              <dd>{item.domain ?? "—"}</dd>
            </div>
            <div>
              <dt>Version</dt>
              <dd>v{item.version}</dd>
            </div>
            <div>
              <dt>Quelle</dt>
              <dd>{item.source}</dd>
            </div>
            <div>
              <dt>Approval</dt>
              <dd>{item.approval_state}</dd>
            </div>
          </dl>
          {resource === "interfaces" && "interface_type" in item && (
            <InterfaceMessageList interfaceItem={item} interfaces={peerItems} messages={referenceObjects} />
          )}
          {resource === "hardware-interfaces" && "technology" in item && (
            <HardwareInterfaceOverview hardwareInterface={item} referenceObjects={referenceObjects} referenceNames={referenceNames} />
          )}
          {resource === "hardware-nodes" && "device_type" in item && (
            <HardwareClassificationOverview item={item} />
          )}
          {resource === "signals" && "start_bit" in item && (
            <SignalParameterOverview item={item} referenceNames={referenceNames} />
          )}
          {item.description && <p className="muted" style={{ marginTop: 14, fontSize: 12 }}>{item.description}</p>}

          <div className="eng-governance-row">
            <div>
              <div className="section-title">
                <span>Lifecycle</span>
              </div>
              <div className="eng-pill-row">
                {["draft", "active", "deprecated", "superseded"].map((state) => (
                  <button
                    className={`button secondary tiny ${item.lifecycle_state === state ? "active" : ""}`}
                    disabled={busy}
                    key={state}
                    onClick={() => setLifecycle(state)}
                    type="button"
                  >
                    {state}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <div className="section-title">
                <span>Review</span>
              </div>
              <div className="eng-pill-row">
                {["unreviewed", "in_review", "reviewed", "rejected"].map((state) => (
                  <button
                    className={`button secondary tiny ${item.review_state === state ? "active" : ""}`}
                    disabled={busy}
                    key={state}
                    onClick={() => setReview(state)}
                    type="button"
                  >
                    {state}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {notice && <div className="notice error">{notice}</div>}

          <div className="form-actions">
            <button className="button secondary" disabled={busy || item.lifecycle_state !== "draft"} onClick={remove} type="button">
              Löschen
            </button>
          </div>
        </div>
      </details>

      <details className="eng-detail-section">
        <summary>
          <span>Relations</span>
          <strong>Knowledge-Graph-Kanten</strong>
        </summary>
        <div className="eng-detail-section-body">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Relations</p>
              <h2 style={{ fontSize: 16 }}>Knowledge-Graph-Kanten</h2>
            </div>
            <button className="button secondary" onClick={() => setShowRelationForm((v) => !v)} type="button">
              {showRelationForm ? "Abbrechen" : "+ Relation"}
            </button>
          </div>

          {showRelationForm && (
            <RelationForm
              sourceType={RESOURCE_TO_OBJECT_TYPE[resource]}
              sourceId={item.id}
              onCreated={() => {
                setShowRelationForm(false);
                onChanged();
              }}
            />
          )}

          {relations.length === 0 ? (
            <p className="muted" style={{ fontSize: 12, marginTop: 14 }}>
              Noch keine Relations für dieses Objekt.
            </p>
          ) : (
            <ul className="eng-relation-list">
              {relations.map((relation) => {
                const relationName = typeof relation.attributes?.name === "string" ? relation.attributes.name : "";
                const relationDescription = typeof relation.attributes?.description === "string" ? relation.attributes.description : "";
                return <li key={relation.id}>
                  <span className="tag">{relation.relation_type}</span>
                  <span className="eng-relation-content"><strong>{relationName || relation.relation_type}</strong><small>{relation.source_type}:{relation.source_id.slice(0, 8)} → {relation.target_type}:{relation.target_id.slice(0, 8)}</small>{relationDescription && <small>{relationDescription}</small>}</span>
                  <button
                    aria-label="Relation löschen"
                    className="eng-relation-remove"
                    disabled={busy}
                    onClick={() => removeRelation(relation.id)}
                    type="button"
                  >
                    ×
                  </button>
                </li>
              })}
            </ul>
          )}
        </div>
      </details>

      <ProposalReviewPanel item={item} onChanged={onChanged} resource={resource} />
    </div>
  );
}

function signalParameterValue(value: unknown, unit?: string | null) {
  if (value === null || value === undefined || value === "") return "—";
  const suffix = unit ? ` ${unit}` : "";
  return `${String(value)}${suffix}`;
}

function signalRangeValue(minimum: unknown, maximum: unknown, unit?: string | null) {
  if ((minimum === null || minimum === undefined || minimum === "") && (maximum === null || maximum === undefined || maximum === "")) {
    return "—";
  }
  return `${signalParameterValue(minimum, unit)} bis ${signalParameterValue(maximum, unit)}`;
}

function signalValueText(value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  return typeof value === "number" && Number.isFinite(value) ? String(value) : String(value);
}

function signalTimeline(data: Record<string, unknown>) {
  return Array.isArray(data.state_timeline)
    ? data.state_timeline.filter((item): item is Record<string, unknown> => item !== null && typeof item === "object" && !Array.isArray(item))
    : [];
}

function isEngMessage(item: EngineeringObject): item is Extract<EngineeringObject, { interface_id: string | null }> {
  return "interface_id" in item && "message_id_hex" in item;
}

function isEngInterface(item: EngineeringObject): item is Extract<EngineeringObject, { interface_type: string }> {
  return "interface_type" in item;
}

function isHardwareNetworkInterface(item: EngineeringObject): item is Extract<EngineeringObject, { technology: string }> {
  return "technology" in item && "network_ref" in item;
}

function HardwareClassificationOverview({ item }: { item: Extract<EngineeringObject, { device_type: string }> }) {
  const profile = hardwareCapabilities(item);
  const policy = hardwareGeneratorPolicy(item);
  const capabilityLabels = [
    "measurement_capabilities",
    "actuation_capabilities",
    "processing_capabilities",
    "diagnostic_capabilities",
    "communication_capabilities",
    "output_types",
  ];
  const visibleCapabilities = capabilityLabels
    .map((key) => ({ key, values: Array.isArray(profile[key]) ? profile[key] as unknown[] : [] }))
    .filter((entry) => entry.values.length > 0);
  return (
    <>
      <div className="section-title signal-parameter-heading">
        <span>Geräteklasse &amp; Generator-Policy</span>
      </div>
      <dl className="overview-list eng-signal-parameter-list">
        <div><dt>Gerätetyp</dt><dd>{engineeringDeviceTypeLabel(item.device_type)}</dd></div>
        <div><dt>Class</dt><dd>{hardwareClassValue(item)}</dd></div>
        <div><dt>Typisierung</dt><dd>{hardwareTypingValue(item)}</dd></div>
        <div><dt>Data Complexity</dt><dd>{"data_complexity" in item ? item.data_complexity : "—"}</dd></div>
        <div><dt>Klassifikation</dt><dd>{"classification_status" in item ? item.classification_status : "—"}</dd></div>
        <div><dt>Profil</dt><dd>{"capability_profile_ref" in item ? item.capability_profile_ref ?? "—" : "—"}</dd></div>
      </dl>
      {visibleCapabilities.length > 0 && (
        <div className="hardware-capability-list" aria-label="Device Capabilities">
          {visibleCapabilities.map((entry) => (
            <span key={entry.key}>
              <b>{FIELD_LABELS[entry.key] ?? entry.key.replace(/_/g, " ")}</b>
              <i>{entry.values.map(signalValueText).join(", ")}</i>
            </span>
          ))}
        </div>
      )}
      {Object.keys(policy).length > 0 && (
        <div className="hardware-generator-policy" aria-label="Generator Policy">
          {Object.entries(policy).map(([key, value]) => (
            <span key={key}><b>{key.replace(/_/g, " ")}</b><i>{signalValueText(value)}</i></span>
          ))}
        </div>
      )}
    </>
  );
}

function HardwareInterfaceOverview({
  hardwareInterface,
  referenceObjects,
  referenceNames,
}: {
  hardwareInterface: Extract<EngineeringObject, { technology: string }>;
  referenceObjects: EngineeringObject[];
  referenceNames: Record<string, string>;
}) {
  const messages = referenceObjects
    .filter(isEngMessage)
    .filter((message) => message.hardware_interface_id === hardwareInterface.id)
    .sort((left, right) => compareEngineeringTableValues(left.name, right.name));
  const functions = [...new Set(messages
    .map((message) => {
      if (!message.interface_id) return "";
      const logicalInterface = referenceObjects.find((item) => item.id === message.interface_id);
      return logicalInterface && "function_id" in logicalInterface && logicalInterface.function_id
        ? referenceNames[logicalInterface.function_id] ?? logicalInterface.function_id
        : "";
    })
    .filter(Boolean))];

  return (
    <>
      <div className="section-title signal-parameter-heading">
        <span>Physische Schnittstelle</span>
      </div>
      <dl className="overview-list eng-signal-parameter-list">
        <div><dt>Hardware Node</dt><dd>{"hardware_node_id" in hardwareInterface ? referenceName(referenceNames, hardwareInterface.hardware_node_id) : "—"}</dd></div>
        <div><dt>Technologie</dt><dd>{signalParameterValue(hardwareInterface.technology)}</dd></div>
        <div><dt>Controller / Channel</dt><dd>{signalParameterValue("controller_ref" in hardwareInterface ? hardwareInterface.controller_ref : null)} / {signalParameterValue("channel_index" in hardwareInterface ? hardwareInterface.channel_index : null)}</dd></div>
        <div><dt>Physical Port</dt><dd>{signalParameterValue("physical_port_ref" in hardwareInterface ? hardwareInterface.physical_port_ref : null)}</dd></div>
        <div><dt>Network</dt><dd>{signalParameterValue("network_ref" in hardwareInterface ? hardwareInterface.network_ref : null)}</dd></div>
        <div><dt>Bitrate</dt><dd>{signalParameterValue("bitrate" in hardwareInterface ? hardwareInterface.bitrate : null, "bit/s")}</dd></div>
        <div><dt>Data Bitrate</dt><dd>{signalParameterValue("data_bitrate" in hardwareInterface ? hardwareInterface.data_bitrate : null, "bit/s")}</dd></div>
        <div><dt>Messages</dt><dd>{messages.length}</dd></div>
        <div><dt>Funktionen</dt><dd>{functions.length ? functions.join(", ") : "—"}</dd></div>
        <div><dt>Statische Last</dt><dd>{signalParameterValue("static_load" in hardwareInterface ? hardwareInterface.static_load : null, "%")}</dd></div>
        <div><dt>Runtime Last</dt><dd>{signalParameterValue("runtime_load" in hardwareInterface ? hardwareInterface.runtime_load : null, "%")}</dd></div>
        <div><dt>Reserve</dt><dd>{hardwareInterface.target_load_limit !== null && hardwareInterface.static_load !== null ? `${Math.max(0, hardwareInterface.target_load_limit - hardwareInterface.static_load).toFixed(1)} %` : "—"}</dd></div>
        <div><dt>Status</dt><dd>{"status" in hardwareInterface ? hardwareInterface.status : "—"}</dd></div>
      </dl>

      <div className="section-title signal-parameter-heading">
        <span>Nachrichten auf diesem Hardware Interface</span>
      </div>
      {messages.length === 0 ? (
        <p className="eng-inline-empty">Noch keine Message ist physisch auf dieses Hardware Interface gelegt.</p>
      ) : (
        <div className="interface-message-list" aria-label="Messages auf Hardware Interface">
          {messages.map((message) => (
            <div key={message.id}>
              <strong>{message.name}<small>{message.interface_id ? referenceName(referenceNames, message.interface_id) : "ohne logisches Interface"}</small></strong>
              <span>{message.message_id_hex ?? "keine ID"}</span>
              <span>{message.direction ?? "—"}</span>
              <span>{signalParameterValue(message.cycle_ms, "ms")}</span>
              <span>DLC {signalParameterValue(message.dlc)}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function InterfaceMessageList({
  interfaceItem,
  interfaces,
  messages,
}: {
  interfaceItem: Extract<EngineeringObject, { interface_type: string }>;
  interfaces: EngineeringObject[];
  messages: EngineeringObject[];
}) {
  const allMessages = messages.filter(isEngMessage);
  const interfaceMessages = allMessages
    .filter((message) => message.interface_id === interfaceItem.id)
    .sort((left, right) => compareEngineeringTableValues(left.name, right.name));
  const currentFunctionId = "function_id" in interfaceItem && typeof interfaceItem.function_id === "string" ? interfaceItem.function_id : null;
  const currentGroupName = normalizedInterfaceGroupName(interfaceItem.name);
  const interfaceNameById = new Map(
    interfaces
      .filter(isEngInterface)
      .map((item) => [item.id, item.name]),
  );
  const relatedInterfaceIds = new Set(
    interfaces
      .filter(isEngInterface)
      .filter((item) => item.id !== interfaceItem.id)
      .filter((item) => {
        const sameFunction = currentFunctionId && "function_id" in item && item.function_id === currentFunctionId;
        const sameGroup = currentGroupName && normalizedInterfaceGroupName(item.name) === currentGroupName;
        return sameFunction || sameGroup;
      })
      .map((item) => item.id),
  );
  const relatedMessages = interfaceMessages.length > 0
    ? []
    : allMessages
      .filter((message) => message.interface_id !== null && relatedInterfaceIds.has(message.interface_id))
      .sort((left, right) => compareEngineeringTableValues(left.name, right.name));
  const visibleMessages = interfaceMessages.length > 0 ? interfaceMessages : relatedMessages;
  const showingRelatedMessages = interfaceMessages.length === 0 && relatedMessages.length > 0;

  return (
    <>
      <div className="section-title signal-parameter-heading">
        <span>Nachrichten</span>
      </div>
      {showingRelatedMessages && (
        <p className="eng-inline-hint">
          Keine direkte Nachricht auf diesem Interface. Angezeigt werden Nachrichten auf verwandten Interfaces derselben Funktion.
        </p>
      )}
      {visibleMessages.length === 0 ? (
        <p className="eng-inline-empty">
          Keine Nachrichten direkt auf diesem Interface. Das passiert, wenn Import oder Generator Messages noch nicht mit diesem Interface verknuepft haben.
        </p>
      ) : (
        <div className="interface-message-list" aria-label={showingRelatedMessages ? "Nachrichten verwandter Interfaces" : "Nachrichten dieses Interfaces"}>
          {visibleMessages.map((message) => (
            <div key={message.id}>
              <strong>
                {message.name}
                {showingRelatedMessages && <small>{message.interface_id ? interfaceNameById.get(message.interface_id) ?? "verwandtes Interface" : "ohne Interface"}</small>}
              </strong>
              <span>{message.message_id_hex ?? "keine ID"}</span>
              <span>{message.direction ?? "—"}</span>
              <span>{signalParameterValue(message.cycle_ms, "ms")}</span>
              <span>DLC {signalParameterValue(message.dlc)}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function SignalParameterOverview({
  item,
  referenceNames,
}: {
  item: EngSignal;
  referenceNames: Record<string, string>;
}) {
  const communication = item.communication ?? {};
  const canonical = buildCanonicalSignalDefinition(item);
  const enumEntries = Object.entries(canonical.valueDomain.enumValues);
  const hasStateDomain = canonical.semantic.semanticType === "STATE" || canonical.semantic.semanticType === "ENUM" || enumEntries.length > 0;
  const timeline = signalTimeline(item.data ?? {});
  const message = item.message_id ? referenceNames[item.message_id] ?? item.message_id : "—";
  return (
    <>
      <div className="section-title signal-parameter-heading">
        <span>Signalparameter</span>
      </div>
      <dl className="overview-list eng-signal-parameter-list">
        <div><dt>Nachricht</dt><dd>{message}</dd></div>
        <div><dt>Anzeigename</dt><dd>{signalParameterValue(item.display_name)}</dd></div>
        <div><dt>Start-Bit</dt><dd>{signalParameterValue(item.start_bit)}</dd></div>
        <div><dt>Länge</dt><dd>{signalParameterValue(item.length_bits, "Bit")}</dd></div>
        <div><dt>Byte-Reihenfolge</dt><dd>{signalParameterValue(item.byte_order)}</dd></div>
        <div><dt>Datentyp</dt><dd>{signalParameterValue(item.data_type)}</dd></div>
        <div><dt>Faktor</dt><dd>{signalParameterValue(item.factor)}</dd></div>
        <div><dt>Offset</dt><dd>{signalParameterValue(item.offset_value)}</dd></div>
        <div><dt>Einheit</dt><dd>{signalParameterValue(item.unit)}</dd></div>
        <div><dt>Wertebereich</dt><dd>{signalRangeValue(item.min_value, item.max_value, item.unit)}</dd></div>
      </dl>

      {hasStateDomain && (
        <>
          <div className="section-title signal-parameter-heading">
            <span>Zustandsdefinition</span>
          </div>
          <div className="signal-state-domain">
            <div className="signal-state-code-grid">
              {enumEntries.map(([state, code]) => (
                <span key={state}>
                  <b>{state}</b>
                  <i>{signalValueText(code)}</i>
                </span>
              ))}
            </div>
            <dl className="overview-list eng-signal-parameter-list">
              <div><dt>Default</dt><dd>{signalValueText(canonical.valueDomain.defaultValue)}</dd></div>
              <div><dt>Reserviert</dt><dd>{canonical.valueDomain.reservedValues.map(signalValueText).join(", ") || "—"}</dd></div>
              <div><dt>Ungültig</dt><dd>{canonical.valueDomain.invalidValues.map(signalValueText).join(", ") || "—"}</dd></div>
              <div><dt>Semantik</dt><dd>{canonical.semantic.semanticType}</dd></div>
            </dl>
            {timeline.length > 0 && (
              <div className="signal-state-timeline" aria-label="Zustandsablauf">
                {timeline.map((step, index) => (
                  <span key={`${signalValueText(step.state)}:${index}`}>
                    {signalValueText(step.state)}
                    <small>
                      {signalValueText(step.from_s)}s bis {step.to_s === null || step.to_s === undefined ? "offen" : `${signalValueText(step.to_s)}s`}
                    </small>
                  </span>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      <div className="section-title signal-parameter-heading">
        <span>Timing &amp; Qualität</span>
      </div>
      <dl className="overview-list eng-signal-parameter-list">
        {REQUIREMENT_FIELDS.map((field) => (
          <div key={field.key}>
            <dt>{field.label}</dt>
            <dd>{signalParameterValue(communication[field.key], field.unit)}</dd>
          </div>
        ))}
        <div><dt>Priorität</dt><dd>{signalParameterValue(communication.priority)}</dd></div>
        <div><dt>Reliability</dt><dd>{signalParameterValue(communication.reliability_requirement)}</dd></div>
      </dl>
    </>
  );
}

function RequirementFields({ prefix, defaults = {} }: { prefix: string; defaults?: Record<string, unknown> }) {
  return (
    <fieldset className="eng-requirement-fields">
      <legend>Timing & Quality Requirements</legend>
      <div className="form-grid three">
        {REQUIREMENT_FIELDS.map((field) => (
          <div className="field" key={field.key}>
            <label htmlFor={`${prefix}${field.key}`}>{field.label} ({field.unit})</label>
            <input defaultValue={String(defaults[field.key] ?? "")} id={`${prefix}${field.key}`} min="0" name={`${prefix}${field.key}`} step="any" type="number" />
          </div>
        ))}
        <div className="field">
          <label htmlFor={`${prefix}priority`}>Priorität</label>
          <select defaultValue={String(defaults.priority ?? "NORMAL")} id={`${prefix}priority`} name={`${prefix}priority`}>
            {['LOW', 'NORMAL', 'HIGH', 'CRITICAL'].map((value) => <option key={value}>{value}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${prefix}reliability_requirement`}>Reliability</label>
          <select defaultValue={String(defaults.reliability_requirement ?? "RELIABLE")} id={`${prefix}reliability_requirement`} name={`${prefix}reliability_requirement`}>
            <option>BEST_EFFORT</option><option>RELIABLE</option><option>SAFETY_CRITICAL</option>
          </select>
        </div>
      </div>
    </fieldset>
  );
}

function SignalValueDomainFields({ item }: { item: EngSignal }) {
  const canonical = buildCanonicalSignalDefinition(item);
  const enumRows = Object.entries(canonical.valueDomain.enumValues)
    .map(([state, code]) => ({ state, code, kind: "defined" }));
  const reservedRows = canonical.valueDomain.reservedValues
    .map((code) => ({ state: `RESERVED_${signalValueText(code)}`, code, kind: "reserved" }));
  const tableRows = [
    ...enumRows,
    ...reservedRows,
    ...Array.from({ length: 3 }, () => ({ state: "", code: "", kind: "defined" })),
  ];
  return (
    <fieldset className="eng-requirement-fields eng-signal-edit-group">
      <legend>Wertcodierung</legend>
      <div className="signal-value-domain-editor">
        <div className="signal-value-domain-controls">
          <div className="field">
            <label htmlFor="edit_semantic_type">Semantik</label>
            <select defaultValue={canonical.semantic.semanticType} id="edit_semantic_type" name="edit_semantic_type">
              {["NUMERIC", "STATE", "ENUM", "BOOLEAN", "BITFIELD", "COUNTER", "FLAG", "RAW", "STRING", "BYTE_ARRAY", "CUSTOM"].map((type) => (
                <option key={type}>{type}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="edit_default_value">Default</label>
            <input defaultValue={signalValueText(canonical.valueDomain.defaultValue)} id="edit_default_value" name="edit_default_value" type="text" />
          </div>
          <div className="field">
            <label htmlFor="edit_invalid_values">Ungültig</label>
            <input defaultValue={formatSignalValueList(canonical.valueDomain.invalidValues)} id="edit_invalid_values" name="edit_invalid_values" placeholder="15, 255" type="text" />
          </div>
        </div>
        <div className="signal-code-table-field">
          <span>Definitionen</span>
          <div className="signal-code-table-scroll">
            <table className="signal-code-table">
              <thead>
                <tr>
                  <th>Zustand / Botschaft</th>
                  <th>Code</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {tableRows.map((row, index) => (
                  <tr key={`${row.state}:${index}`}>
                    <td>
                      <input
                        aria-label={`Zustand oder Botschaft ${index + 1}`}
                        defaultValue={row.state}
                        name="edit_enum_state"
                        placeholder={index >= enumRows.length + reservedRows.length ? "NEUER_WERT" : undefined}
                        type="text"
                      />
                    </td>
                    <td>
                      <input
                        aria-label={`Code ${index + 1}`}
                        defaultValue={signalValueText(row.code) === "—" ? "" : signalValueText(row.code)}
                        name="edit_enum_code"
                        placeholder={index >= enumRows.length + reservedRows.length ? String(index) : undefined}
                        type="text"
                      />
                    </td>
                    <td>
                      <select aria-label={`Status ${index + 1}`} defaultValue={row.kind} name="edit_enum_kind">
                        <option value="defined">Definiert</option>
                        <option value="reserved">Reserviert</option>
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </fieldset>
  );
}

function EditObjectForm({
  item,
  referenceObjects,
  referenceNames,
  resource,
  schema,
  onSaved,
}: {
  item: EngineeringObject;
  referenceObjects: EngineeringObject[];
  referenceNames: Record<string, string>;
  resource: EngineeringResource;
  schema: EngineeringSchema | null;
  onSaved: () => void;
}) {
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");

  function optionalNumber(form: FormData, name: string) {
    const value = form.get(name);
    return value === null || value === "" ? null : Number(value);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setFormError("");
    const form = new FormData(event.currentTarget);
    let normalizedName: unknown = form.get("edit_name");
    if (resource === "interfaces") normalizedName = normalizeInterfaceName(normalizedName);
    if (resource === "messages") normalizedName = normalizeMessageName(normalizedName);
    if (resource === "signals" && "message_id" in item) {
      normalizedName = normalizeSignalName(normalizedName, item.message_id ? referenceNames[item.message_id] : undefined);
    }
    const payload: Record<string, unknown> = {
      name: normalizedName,
      domain: form.get("edit_domain") || null,
      description: form.get("edit_description") || null,
    };
    if (resource === "hardware-nodes") {
      payload.device_type = form.get("edit_device_type");
      payload.device_class = optionalNumber(form, "edit_device_class");
      payload.device_typing = form.get("edit_device_typing") || null;
      payload.data_complexity = form.get("edit_data_complexity") || null;
      payload.classification_status = form.get("edit_classification_status") || "CONFIRMED";
    }
    if (resource === "hardware-interfaces") {
      payload.technology = form.get("edit_technology") || null;
      payload.controller_ref = form.get("edit_controller_ref") || null;
      payload.physical_port_ref = form.get("edit_physical_port_ref") || null;
      payload.channel_index = optionalNumber(form, "edit_channel_index");
      payload.network_ref = form.get("edit_network_ref") || null;
      payload.bitrate = optionalNumber(form, "edit_bitrate");
      payload.data_bitrate = optionalNumber(form, "edit_data_bitrate");
      payload.status = form.get("edit_status") || "UNMAPPED";
      payload.static_load = optionalNumber(form, "edit_static_load");
      payload.runtime_load = optionalNumber(form, "edit_runtime_load");
      payload.target_load_limit = optionalNumber(form, "edit_target_load_limit");
      payload.warning_load_limit = optionalNumber(form, "edit_warning_load_limit");
      payload.hard_load_limit = optionalNumber(form, "edit_hard_load_limit");
    }
    if (resource === "interfaces") payload.interface_type = form.get("edit_interface_type");
    if (resource === "messages") {
      payload.hardware_interface_id = form.get("edit_hardware_interface_id") || null;
      payload.message_id_hex = form.get("edit_message_id_hex") || null;
      payload.direction = form.get("edit_direction") || null;
      payload.cycle_ms = optionalNumber(form, "edit_cycle_ms");
      payload.dlc = optionalNumber(form, "edit_dlc");
      payload.configuration = {
        ...("configuration" in item ? item.configuration : {}),
        ...requirementPayload(form, "edit_requirement_"),
      };
    }
    if (resource === "signals") {
      payload.display_name = form.get("edit_display_name") || null;
      payload.start_bit = optionalNumber(form, "edit_start_bit");
      payload.length_bits = optionalNumber(form, "edit_length_bits");
      payload.byte_order = form.get("edit_byte_order") || null;
      payload.data_type = form.get("edit_data_type") || null;
      payload.factor = optionalNumber(form, "edit_factor");
      payload.offset_value = optionalNumber(form, "edit_offset_value");
      payload.unit = form.get("edit_unit") || null;
      payload.min_value = optionalNumber(form, "edit_min_value");
      payload.max_value = optionalNumber(form, "edit_max_value");
      payload.communication = {
        ...("communication" in item ? item.communication : {}),
        ...requirementPayload(form, "edit_requirement_"),
      };
      const semanticType = String(form.get("edit_semantic_type") || "UNKNOWN").toUpperCase();
      const { enumValues, reservedValues } = parseSignalEnumValueRows(form);
      const invalidValues = parseSignalValueList(form.get("edit_invalid_values"));
      const defaultValue = parseTypedSignalValue(String(form.get("edit_default_value") ?? ""));
      payload.data = {
        ...("data" in item ? item.data : {}),
        semantic_type: semanticType,
        enum_values: enumValues,
        allowed_values: Object.keys(enumValues),
        reserved_values: reservedValues,
        invalid_values: invalidValues,
        default_value: defaultValue,
      };
      payload.semantic = {
        ...("semantic" in item ? item.semantic : {}),
        semantic_type: semanticType,
        quantity: normalizedName,
      };
    }
    try {
      await updateEngineeringObject(resource, item.id, payload);
      onSaved();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Änderungen konnten nicht gespeichert werden.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="eng-create-form eng-edit-form" onSubmit={submit}>
      <div className="form-grid">
        <div className="field">
          <label htmlFor="edit_name">Name</label>
          <input autoFocus defaultValue={item.name} id="edit_name" name="edit_name" required type="text" />
        </div>
        <div className="field">
          <label htmlFor="edit_domain">Domäne</label>
          <input defaultValue={item.domain ?? ""} id="edit_domain" name="edit_domain" type="text" />
        </div>
      </div>

      {resource === "hardware-nodes" && "device_type" in item && (
        <fieldset className="eng-requirement-fields">
          <legend>Geräteklasse &amp; Typisierung</legend>
          <div className="form-grid three">
            <div className="field">
              <label htmlFor="edit_device_type">Gerätetyp</label>
              <select defaultValue={item.device_type} id="edit_device_type" name="edit_device_type" required>
                {(schema?.device_types ?? [item.device_type]).map((type) => <option key={type} value={type}>{engineeringDeviceTypeLabel(type)}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="edit_device_class">Class</label>
              <select defaultValue={item.device_class ?? 1} id="edit_device_class" name="edit_device_class" required>
                {(schema?.device_classes ?? [{ value: item.device_class ?? 1, label: "Basic" }]).map((option) => <option key={option.value} value={option.value}>{option.value} · {option.label}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="edit_device_typing">Typisierung</label>
              <select defaultValue={item.device_typing ?? "Basic Communication Device"} id="edit_device_typing" name="edit_device_typing" required>
                {(schema?.device_typings ?? [item.device_typing ?? "Basic Communication Device"]).map((type) => <option key={type} value={type}>{type}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="edit_data_complexity">Data Complexity</label>
              <select defaultValue={item.data_complexity ?? "SERVICE_DATA"} id="edit_data_complexity" name="edit_data_complexity" required>
                {(schema?.data_complexities ?? [item.data_complexity ?? "SERVICE_DATA"]).map((type) => <option key={type} value={type}>{type}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="edit_classification_status">Status</label>
              <select defaultValue={item.classification_status ?? "CONFIRMED"} id="edit_classification_status" name="edit_classification_status" required>
                {(schema?.classification_statuses ?? ["UNKNOWN", "PROPOSED", "CONFIRMED", "REVIEW_REQUIRED"]).map((type) => <option key={type} value={type}>{type}</option>)}
              </select>
            </div>
          </div>
        </fieldset>
      )}

      {resource === "hardware-interfaces" && isHardwareNetworkInterface(item) && (
        <>
        <div className="form-grid three">
          <div className="field">
            <label htmlFor="edit_technology">Technologie</label>
            <select defaultValue={item.technology} id="edit_technology" name="edit_technology" required>
              {(schema?.interface_types ?? [item.technology]).map((type) => <option key={type}>{type}</option>)}
            </select>
          </div>
          <div className="field"><label htmlFor="edit_controller_ref">Controller</label><input defaultValue={item.controller_ref ?? ""} id="edit_controller_ref" name="edit_controller_ref" type="text" /></div>
          <div className="field"><label htmlFor="edit_physical_port_ref">Physischer Port</label><input defaultValue={item.physical_port_ref ?? ""} id="edit_physical_port_ref" name="edit_physical_port_ref" type="text" /></div>
          <div className="field"><label htmlFor="edit_channel_index">Kanal</label><input defaultValue={item.channel_index ?? ""} id="edit_channel_index" min="1" name="edit_channel_index" type="number" /></div>
          <div className="field"><label htmlFor="edit_network_ref">Netzwerk / Bussegment</label><input defaultValue={item.network_ref ?? ""} id="edit_network_ref" name="edit_network_ref" type="text" /></div>
          <div className="field"><label htmlFor="edit_bitrate">Bitrate</label><input defaultValue={item.bitrate ?? ""} id="edit_bitrate" min="1" name="edit_bitrate" step="1" type="number" /></div>
          <div className="field"><label htmlFor="edit_data_bitrate">Data Bitrate</label><input defaultValue={item.data_bitrate ?? ""} id="edit_data_bitrate" min="1" name="edit_data_bitrate" step="1" type="number" /></div>
          <div className="field"><label htmlFor="edit_target_load_limit">Ziel-Last (%)</label><input defaultValue={item.target_load_limit ?? ""} id="edit_target_load_limit" min="0" name="edit_target_load_limit" step="any" type="number" /></div>
          <div className="field"><label htmlFor="edit_warning_load_limit">Warn-Last (%)</label><input defaultValue={item.warning_load_limit ?? ""} id="edit_warning_load_limit" min="0" name="edit_warning_load_limit" step="any" type="number" /></div>
          <div className="field"><label htmlFor="edit_hard_load_limit">Harte Last (%)</label><input defaultValue={item.hard_load_limit ?? ""} id="edit_hard_load_limit" min="0" name="edit_hard_load_limit" step="any" type="number" /></div>
          <div className="field"><label htmlFor="edit_static_load">Statische Last (%)</label><input defaultValue={item.static_load ?? ""} id="edit_static_load" min="0" name="edit_static_load" step="any" type="number" /></div>
          <div className="field"><label htmlFor="edit_runtime_load">Runtime Last (%)</label><input defaultValue={item.runtime_load ?? ""} id="edit_runtime_load" min="0" name="edit_runtime_load" step="any" type="number" /></div>
          <div className="field"><label htmlFor="edit_status">Status</label><select defaultValue={item.status} id="edit_status" name="edit_status">{["CONFIGURED", "UNMAPPED", "ACTIVE", "OUTDATED", "OVERLOADED", "ERROR"].map((value) => <option key={value}>{value}</option>)}</select></div>
        </div>
        </>
      )}

      {resource === "interfaces" && "interface_type" in item && (
        <div className="field">
          <label htmlFor="edit_interface_type">Interface-Typ</label>
          <select defaultValue={item.interface_type} id="edit_interface_type" name="edit_interface_type" required>
            {(schema?.interface_types ?? [item.interface_type]).map((type) => <option key={type}>{type}</option>)}
          </select>
        </div>
      )}

      {resource === "messages" && "message_id_hex" in item && (
        <>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="edit_hardware_interface_id">Hardware Interface</label>
            <select defaultValue={item.hardware_interface_id ?? ""} id="edit_hardware_interface_id" name="edit_hardware_interface_id">
              <option value="">Noch nicht zugewiesen</option>
              {referenceObjects.filter(isHardwareNetworkInterface).map((hardwareInterface) => (
                <option key={hardwareInterface.id} value={hardwareInterface.id}>
                  {hardwareInterface.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="edit_message_id_hex">Message-ID</label>
            <input defaultValue={item.message_id_hex ?? ""} id="edit_message_id_hex" name="edit_message_id_hex" type="text" />
          </div>
          <div className="field">
            <label htmlFor="edit_direction">Richtung</label>
            <select defaultValue={item.direction ?? ""} id="edit_direction" name="edit_direction">
              <option value="">—</option>
              {(schema?.message_directions ?? ["tx", "rx", "bidirectional"]).map((direction) => <option key={direction}>{direction}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="edit_cycle_ms">Zyklus (ms)</label>
            <input defaultValue={item.cycle_ms ?? ""} id="edit_cycle_ms" min="0.001" name="edit_cycle_ms" step="0.001" type="number" />
          </div>
          <div className="field">
            <label htmlFor="edit_dlc">DLC</label>
            <input defaultValue={item.dlc ?? ""} id="edit_dlc" min="0" name="edit_dlc" type="number" />
          </div>
        </div>
        <RequirementFields defaults={item.configuration} prefix="edit_requirement_" />
        </>
      )}

      {resource === "signals" && "start_bit" in item && (
        <>
        <fieldset className="eng-requirement-fields eng-signal-edit-group">
          <legend>Signal-Layout &amp; Codierung</legend>
          <div className="form-grid three">
            <div className="field"><label htmlFor="edit_display_name">Anzeigename</label><input defaultValue={item.display_name ?? ""} id="edit_display_name" name="edit_display_name" type="text" /></div>
            <div className="field"><label htmlFor="edit_start_bit">Start-Bit</label><input defaultValue={item.start_bit ?? ""} id="edit_start_bit" min="0" name="edit_start_bit" type="number" /></div>
            <div className="field"><label htmlFor="edit_length_bits">Länge (Bit)</label><input defaultValue={item.length_bits ?? ""} id="edit_length_bits" min="1" name="edit_length_bits" type="number" /></div>
            <div className="field"><label htmlFor="edit_byte_order">Byte-Reihenfolge</label><select defaultValue={item.byte_order ?? ""} id="edit_byte_order" name="edit_byte_order"><option value="">—</option><option value="little_endian">little_endian</option><option value="big_endian">big_endian</option></select></div>
            <div className="field"><label htmlFor="edit_data_type">Datentyp</label><input defaultValue={item.data_type ?? ""} id="edit_data_type" list="signal-data-types" name="edit_data_type" type="text" /><datalist id="signal-data-types"><option value="unsigned" /><option value="signed" /><option value="float" /><option value="boolean" /><option value="string" /><option value="bytes" /></datalist></div>
          </div>
        </fieldset>
        <fieldset className="eng-requirement-fields eng-signal-edit-group">
          <legend>Physikalische Skalierung</legend>
          <div className="form-grid three">
            <div className="field"><label htmlFor="edit_factor">Faktor</label><input defaultValue={item.factor ?? ""} id="edit_factor" name="edit_factor" step="any" type="number" /></div>
            <div className="field"><label htmlFor="edit_offset_value">Offset</label><input defaultValue={item.offset_value ?? ""} id="edit_offset_value" name="edit_offset_value" step="any" type="number" /></div>
            <div className="field"><label htmlFor="edit_unit">Einheit</label><input defaultValue={item.unit ?? ""} id="edit_unit" name="edit_unit" type="text" /></div>
            <div className="field"><label htmlFor="edit_min_value">Minimum</label><input defaultValue={item.min_value ?? ""} id="edit_min_value" name="edit_min_value" step="any" type="number" /></div>
            <div className="field"><label htmlFor="edit_max_value">Maximum</label><input defaultValue={item.max_value ?? ""} id="edit_max_value" name="edit_max_value" step="any" type="number" /></div>
          </div>
        </fieldset>
        <SignalValueDomainFields item={item} />
        <RequirementFields defaults={item.communication} prefix="edit_requirement_" />
        </>
      )}

      <div className="field">
        <label htmlFor="edit_description">Beschreibung</label>
        <textarea defaultValue={item.description ?? ""} id="edit_description" name="edit_description" rows={3} />
      </div>
      {formError && <div className="notice error">{formError}</div>}
      <div className="form-actions">
        <button className="button primary" disabled={submitting} type="submit">
          {submitting ? "Wird gespeichert …" : "Änderungen speichern"}
        </button>
      </div>
    </form>
  );
}

function RelationForm({
  sourceType,
  sourceId,
  onCreated,
}: {
  sourceType: string;
  sourceId: string;
  onCreated: () => void;
}) {
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setFormError("");
    const form = new FormData(event.currentTarget);
    try {
      await createEngineeringRelation({
        source_type: sourceType,
        source_id: sourceId,
        target_type: String(form.get("target_type")),
        target_id: String(form.get("target_id")),
        relation_type: String(form.get("relation_type")),
      });
      onCreated();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Relation konnte nicht erstellt werden.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="eng-create-form" onSubmit={submit}>
      <div className="field">
        <label htmlFor="relation_type">Relationstyp</label>
        <select id="relation_type" name="relation_type" required>
          {RELATION_TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
      </div>
      <div className="form-grid">
        <div className="field">
          <label htmlFor="target_type">Ziel-Typ</label>
          <select id="target_type" name="target_type" required>
            {["HardwareNode", "Function", "Interface", "Message", "Signal"].map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="target_id">Ziel-ID (UUID)</label>
          <input id="target_id" name="target_id" required type="text" placeholder="uuid" />
        </div>
      </div>
      {formError && <div className="notice error">{formError}</div>}
      <div className="form-actions">
        <button className="button primary" disabled={submitting} type="submit">
          {submitting ? "Wird verknüpft …" : "Relation anlegen"}
        </button>
      </div>
    </form>
  );
}
