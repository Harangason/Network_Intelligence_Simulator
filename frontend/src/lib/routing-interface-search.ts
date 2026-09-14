import type { RoutingInterface, PhysicalBinding } from './routing-network-context';
import type { HardwareNetworkInterface } from './types';

export type NodeBuses = Record<string, PhysicalBinding[]>;

export function physicalNodeBuses(ports: HardwareNetworkInterface[], names: Map<string, string>): NodeBuses {
  const result: NodeBuses = {};
  for (const port of ports) if (port.network_ref) {
    (result[port.hardware_node_id] ??= []).push({ id: port.network_ref, name: names.get(port.network_ref) ?? port.network_ref, portId: port.id, protocol: port.technology });
  }
  return result;
}

/** Rank exact physical bus evidence before protocol affinity or display names. */
export function endpointInterfaceChoices(interfaces: RoutingInterface[], nodeId: string, neighborId: string, protocol: string, query = '', nodeBuses?: NodeBuses) {
  const adjacent = new Set(nodeBuses ? (nodeBuses[neighborId] ?? []).map(b => b.id) : interfaces.filter(i => i.hardware_node_id === neighborId).flatMap(i => i.physicalBindings?.map(b => b.id) ?? []));
  const terms = query.toLocaleLowerCase('de').split(/\s+/).filter(t => t && t !== 'und');
  return interfaces.filter(i => i.hardware_node_id === nodeId).map(item => {
    const common = (item.physicalBindings ?? []).filter(b => adjacent.has(b.id));
    const text = [item.name, item.interface_type, item.id, item.function_id, ...(item.physicalBindings ?? []).flatMap(b => [b.id, b.name, b.protocol])].join(' ').toLocaleLowerCase('de');
    const score = (common.length ? 10 : 0) + (item.interface_type.toUpperCase() === protocol.toUpperCase() ? 1 : 0);
    return { item, common, score, matches: terms.every(term => text.includes(term)) };
  }).filter(c => c.matches).sort((a, b) => b.score - a.score || a.item.name.localeCompare(b.item.name, 'de', { numeric: true }));
}

/** A recommendation may change protocol across a gateway, but needs physical evidence. */
export function suggestedEndpointInterface(interfaces: RoutingInterface[], nodeId: string, neighborId: string, protocol: string, nodeBuses?: NodeBuses) {
  return endpointInterfaceChoices(interfaces, nodeId, neighborId, protocol, '', nodeBuses).find(c => c.common.length)?.item;
}

export function endpointPhysicalBinding(item: RoutingInterface | undefined, neighborId: string, nodeBuses: NodeBuses, networkId = '', portId = '') {
  const bindings = item?.physicalBindings ?? [];
  const common = bindings.filter(b => (nodeBuses[neighborId] ?? []).some(n => n.id === b.id));
  const candidates = common.length ? common : bindings;
  const exact = candidates.find(b => b.portId === portId && (!networkId || b.id === networkId));
  if (exact) return exact;
  const network = candidates.filter(b => b.id === networkId);
  if (network.length === 1) return network[0];
  return candidates.length === 1 ? candidates[0] : undefined;
}
