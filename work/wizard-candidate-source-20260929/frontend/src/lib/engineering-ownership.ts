import type { EngineeringObject, EngineeringObjectType, HardwareNode } from "./types";

export type EngineeringParent = { id: string | null; type: EngineeringObjectType; field: string; relation: string };

/** The same parent alternatives as repository.parent_link_for_payload. */
export function engineeringParent(item: EngineeringObject): EngineeringParent | null {
  const fields: Partial<Record<EngineeringObjectType, [string, EngineeringObjectType, string]>> = {
    HardwareNetworkInterface: ["hardware_node_id", "HardwareNode", "HAS_HARDWARE_INTERFACE"],
    Function: ["hardware_node_id", "HardwareNode", "HAS_FUNCTION"],
    Interface: "function_id" in item && item.function_id
      ? ["function_id", "Function", "HAS_INTERFACE"]
      : ["hardware_node_id", "HardwareNode", "HAS_INTERFACE"],
    Message: ["interface_id", "Interface", "HAS_MESSAGE"],
    Signal: ["message_id", "Message", "CONTAINS_SIGNAL"],
  };
  const link = fields[item.object_type];
  if (!link) return null;
  const [field, type, relation] = link;
  const value = (item as unknown as Record<string, unknown>)[field];
  return { id: typeof value === "string" && value ? value : null, type, field, relation };
}

export function requiresFunctionModel(item: EngineeringObject | undefined): boolean {
  if (!item || !("device_type" in item)) return false;
  if (item.device_class !== null && item.device_class !== undefined) return item.device_class >= 3;
  return !["SensorController", "ActuatorController"].includes(item.device_type);
}

export function canAssignEngineeringParent(child: EngineeringObject, parent: EngineeringObject): boolean {
  if (child.id === parent.id) return false;
  if (child.object_type === "Interface") {
    return parent.object_type === "Function" || (parent.object_type === "HardwareNode" && !requiresFunctionModel(parent));
  }
  return engineeringParent(child)?.type === parent.object_type;
}

/** Explicit system identity is authoritative; suggestions never change ownership. */
export function explicitSystemOwner(item: HardwareNode, hardware: ReadonlyMap<string, EngineeringObject>): HardwareNode | null {
  const id = item.identity?.system_owner_id ?? item.identity?.systemOwnerId;
  if (typeof id === "string" && id) {
    const owner = hardware.get(id);
    return owner && "device_type" in owner ? owner : null;
  }
  return requiresFunctionModel(item) && !["SensorController", "ActuatorController", "Gateway"].includes(item.device_type) ? item : null;
}

export function engineeringOwnership(item: EngineeringObject, objects: ReadonlyMap<string, EngineeringObject>) {
  let current: EngineeringObject | undefined = item;
  let fn: EngineeringObject | null = null;
  let hardware: HardwareNode | null = null;
  let error: string | null = null;
  const visited = new Set<string>();
  while (current) {
    if (visited.has(current.id)) { error = "Zyklische Eigentümerzuordnung"; break; }
    visited.add(current.id);
    if (current.object_type === "Function") fn = current;
    if (current.object_type === "HardwareNode" && "device_type" in current) { hardware = current; break; }
    const link = engineeringParent(current);
    const parent = link?.id ? objects.get(link.id) : undefined;
    if (!link || !parent || parent.object_type !== link.type) { error = `Zuordnung fehlt: ${link?.field ?? "Eigentümer"}`; break; }
    current = parent;
  }
  const system = hardware ? explicitSystemOwner(hardware, objects) : null;
  return { hardware, function: fn, system, error };
}
