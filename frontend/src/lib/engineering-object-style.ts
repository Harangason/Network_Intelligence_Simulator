import type { EngineeringObjectType, EngineeringResource } from "@/lib/types";

export const ENGINEERING_OBJECT_LABELS: Record<EngineeringObjectType, string> = {
  HardwareNode: "Hardware",
  HardwareNetworkInterface: "Hardware Interface",
  Function: "Funktion",
  Interface: "Interface",
  Message: "Nachricht",
  Signal: "Signal",
};

const RESOURCE_TYPES: Record<EngineeringResource, EngineeringObjectType> = {
  "hardware-nodes": "HardwareNode",
  "hardware-interfaces": "HardwareNetworkInterface",
  functions: "Function",
  interfaces: "Interface",
  messages: "Message",
  signals: "Signal",
};

const TYPE_ALIASES: Record<string, EngineeringObjectType> = {
  hardware: "HardwareNode",
  hardwarenode: "HardwareNode",
  hardwarenodes: "HardwareNode",
  hardwareinterface: "HardwareNetworkInterface",
  hardwareinterfaces: "HardwareNetworkInterface",
  hardwarenetworkinterface: "HardwareNetworkInterface",
  hardwarenetworkinterfaces: "HardwareNetworkInterface",
  funktion: "Function",
  funktionen: "Function",
  function: "Function",
  functions: "Function",
  interface: "Interface",
  interfaces: "Interface",
  nachricht: "Message",
  nachrichten: "Message",
  message: "Message",
  messages: "Message",
  signal: "Signal",
  signale: "Signal",
  signals: "Signal",
};

export function normalizeEngineeringObjectType(value: unknown): EngineeringObjectType | null {
  const normalized = String(value ?? "").trim().toLocaleLowerCase("de-DE").replace(/[\s_-]+/g, "");
  return TYPE_ALIASES[normalized] ?? null;
}

export function engineeringResourceType(resource: EngineeringResource): EngineeringObjectType {
  return RESOURCE_TYPES[resource];
}

export function engineeringObjectTypeClass(value: unknown): string {
  const type = normalizeEngineeringObjectType(value);
  return type ? `eng-type-${type.toLocaleLowerCase("en-US")}` : "eng-type-generic";
}

export function engineeringObjectTypeLabel(value: unknown): string {
  const type = normalizeEngineeringObjectType(value);
  return type ? ENGINEERING_OBJECT_LABELS[type] : String(value ?? "Objekt");
}

export function engineeringDeviceTypeLabel(value: unknown): string {
  return String(value ?? "")
    .replace(/([a-z0-9])([A-ZÄÖÜ])/g, "$1 $2")
    .replace(/([A-ZÄÖÜ])([A-ZÄÖÜ][a-zäöü])/g, "$1 $2")
    .trim();
}

export function engineeringHardwareName(value: unknown): string {
  const original = String(value ?? "").trim();
  const normalized = original
    .replace(/(?:[-_ ]?(?:ECU|Gateway|Sensor|Aktor|Aktuator|Actuator|Controller|Steuerger(?:ä|ae|a|�)t))+$/i, "")
    .replace(/^[-_ ]+|[-_ ]+$/g, "")
    .trim();
  return normalized || original;
}

export function isMergedHardwareAlias(value: unknown): boolean {
  if (!value || typeof value !== "object") return false;
  const item = value as {
    object_type?: unknown;
    lifecycle_state?: unknown;
    provenance?: { canonical_system_merge?: { role?: unknown } };
  };
  return item.object_type === "HardwareNode"
    && item.lifecycle_state === "superseded"
    && item.provenance?.canonical_system_merge?.role === "alias";
}
