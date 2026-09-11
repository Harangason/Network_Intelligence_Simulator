import type { RoutingInterface } from './routing-network-context';

/** Rank exact physical bus evidence before protocol affinity or display names. */
export function endpointInterfaceChoices(interfaces: RoutingInterface[], nodeId: string, neighborId: string, protocol: string, query = '') {
  const adjacent = new Set(interfaces.filter(i => i.hardware_node_id === neighborId).flatMap(i => i.physicalBindings?.map(b => b.id) ?? []));
  const terms = query.toLocaleLowerCase('de').split(/\s+/).filter(t => t && t !== 'und');
  return interfaces.filter(i => i.hardware_node_id === nodeId).map(item => {
    const common = (item.physicalBindings ?? []).filter(b => adjacent.has(b.id));
    const text = [item.name, item.interface_type, item.id, item.function_id, ...(item.physicalBindings ?? []).flatMap(b => [b.id, b.name, b.protocol])].join(' ').toLocaleLowerCase('de');
    const score = (common.length ? 10 : 0) + (item.interface_type.toUpperCase() === protocol.toUpperCase() ? 1 : 0);
    return { item, common, score, matches: terms.every(term => text.includes(term)) };
  }).filter(c => c.matches).sort((a, b) => b.score - a.score || a.item.name.localeCompare(b.item.name, 'de', { numeric: true }));
}
