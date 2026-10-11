import type { EngInterface, EngMessage, HardwareNetworkInterface, RoutingEntry } from "./types";
import { networkLabel } from "./network-names.ts";

export type PhysicalBinding = { id: string; name: string; portId: string; protocol: string };
export type RoutingInterface = EngInterface & { physicalBindings?: PhysicalBinding[] };

export function withPhysicalBindings(interfaces: EngInterface[], messages: EngMessage[], ports: HardwareNetworkInterface[], routes: RoutingEntry[], networks: Array<{id: string; name?: string}> = []): RoutingInterface[] {
  const networkNames = new Map(networks.map(network => [network.id, network.name || network.id]));
  const byPort = new Map(ports.map((port) => [port.id, port]));
  const bindings = new Map<string, Map<string, PhysicalBinding>>();
  const byInterface = new Map(interfaces.map((item) => [item.id, item]));
  const add = (interfaceId: string | null | undefined, portId: string | null | undefined) => {
    const iface = byInterface.get(interfaceId ?? "");
    const port = byPort.get(portId ?? "");
    if (!iface || !port?.network_ref || iface.hardware_node_id !== port.hardware_node_id) return;
    const items = bindings.get(iface.id) ?? new Map<string, PhysicalBinding>();
    items.set(port.id, { id: port.network_ref, name: networkNames.get(port.network_ref) ?? networkLabel(port.name || port.network_ref, port.technology), portId: port.id, protocol: port.technology });
    bindings.set(iface.id, items);
  };
  for (const message of messages) {
    add(message.interface_id, message.hardware_interface_id);
    const extra = message.configuration?.physical_transmit_bindings;
    if (Array.isArray(extra)) for (const item of extra) add(message.interface_id, item?.hardware_interface_id);
  }
  for (const route of routes) for (const endpoint of [route.source, ...route.destinations]) add(endpoint.interface_id, endpoint.port_id);
  return interfaces.map((item) => ({ ...item, physicalBindings: [...(bindings.get(item.id)?.values() ?? [])]
    .sort((a, b) => a.name.localeCompare(b.name, "de", { numeric: true }) || a.id.localeCompare(b.id)) }));
}

/** A bus technology is never a physical network identity. Multiple bindings stay explicit. */
export function interfaceNetworkId(item?: RoutingInterface): string | null {
  if (!item) return null;
  const ids = [...new Set(item.physicalBindings?.map((binding) => binding.id))];
  if (ids.length) return ids.length === 1 ? ids[0] : null;
  const configured = item.configuration?.network_id ?? item.configuration?.network;
  return typeof configured === "string" && configured.trim() ? configured.trim() : null;
}

export function physicalNetworkAliases(interfaces: RoutingInterface[]): Map<string, string> {
  const aliases = new Map<string, string>();
  for (const item of interfaces) for (const binding of item.physicalBindings ?? []) aliases.set(binding.id, binding.name);
  return aliases;
}

export function physicalNetworkName(id: string | null | undefined, aliases: Map<string, string>): string {
  if (!id) return "Nicht eindeutig zugeordnet";
  return aliases.get(id) ?? `Unbekanntes Netz (${id})`;
}

/** Resolve an endpoint's explicit identity before falling back to interface bindings.
 * The full network catalog also covers routes without a bound physical port.
 */
export function routeEndpointNetworkLabel(
  endpoint: Pick<RoutingEntry["source"], "network_id" | "interface_id">,
  interfaceNetworkLabels: Map<string, string>,
  networkNames: Map<string, string>,
): string {
  if (endpoint.network_id) return physicalNetworkName(endpoint.network_id, networkNames);
  return interfaceNetworkLabels.get(endpoint.interface_id ?? "") ?? "—";
}

export function routeNetworkLabel(
  route: Pick<RoutingEntry, "source" | "destinations">,
  interfaceNetworkLabels: Map<string, string>,
  networkNames: Map<string, string>,
): string {
  const labels = [route.source, ...route.destinations]
    .map((endpoint) => routeEndpointNetworkLabel(endpoint, interfaceNetworkLabels, networkNames))
    .filter((label) => label !== "—");
  return [...new Set(labels)].join(" → ") || "—";
}

export function interfaceBindingLabel(item: RoutingInterface, compact = false): string {
  const names = [...new Set(item.physicalBindings?.map((binding) => binding.name))];
  if (compact && names.length > 1) return `${names.length} physische Busse`;
  return names.length ? names.join(", ") : "Kein physischer Anschluss nachgewiesen";
}

function supportsProtocol(type: string, protocol: string) {
  const capabilities: Record<string, string[]> = {
    CAN_FD: ["CAN", "CAN_FD"], CAN_XL: ["CAN", "CAN_FD", "CAN_XL"],
    ETHERNET: ["ETHERNET", "SOME_IP", "TCP", "UDP", "DDS", "ROS_2", "OPC_UA"],
    MODBUSTCP: ["MODBUS", "TCP"], MODBUSRTU: ["MODBUS"], OPCUA: ["OPC_UA"], ETB: ["ETB", "TRDP"],
  };
  return type.toUpperCase() === "OTHER" || (capabilities[type.toUpperCase()] ?? [type.toUpperCase()]).includes(protocol.toUpperCase());
}

export function selectPhysicalBinding(item?: RoutingInterface, networkId?: string, portId?: string): PhysicalBinding | undefined {
  const bindings = item?.physicalBindings ?? [];
  const selected = bindings.find((binding) => binding.portId === portId && (!networkId || binding.id === networkId));
  if (selected) return selected;
  const matching = bindings.filter((binding) => binding.id === networkId);
  if (matching.length === 1) return matching[0];
  return bindings.length === 1 ? bindings[0] : undefined;
}

export function assessInterfaceBinding(item: RoutingInterface, nodeId: string, protocol: string, networkId?: string) {
  const conflicts: string[] = [];
  if (item.hardware_node_id !== nodeId) conflicts.push("Schnittstelle gehört zu einem anderen Gerät");
  if (!supportsProtocol(item.interface_type, protocol)) conflicts.push("Logischer Schnittstellentyp passt nicht zum Protokoll");
  const bindings = item.physicalBindings ?? [];
  const relevant = networkId ? bindings.filter((binding) => binding.id === networkId) : bindings;
  if (!relevant.length) conflicts.push(networkId ? "Für das gewählte Netz fehlt ein Anschlussnachweis" : "Physischer Anschluss fehlt");
  else if (relevant.some((binding) => !supportsProtocol(binding.protocol, protocol))) conflicts.push("Physischer Bustyp widerspricht dem Protokoll");
  if (!networkId && new Set(bindings.map((binding) => binding.id)).size > 1) conflicts.push("Mehrere Busse: Anschluss auswählen");
  return { compatible: conflicts.length === 0, reason: conflicts.length ? conflicts.join(" · ") : "Gerät, Schnittstellentyp und physischer Anschluss stimmen überein" };
}
