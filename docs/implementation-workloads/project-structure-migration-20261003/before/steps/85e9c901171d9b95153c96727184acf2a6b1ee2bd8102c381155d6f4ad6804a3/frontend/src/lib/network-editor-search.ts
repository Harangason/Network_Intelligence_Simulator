import type { NetworkTopology, NodeKind } from './topology';

export type NetworkSearchEntry = {
  key: string;
  id: string;
  kind: 'node' | 'bus' | 'edge';
  name: string;
  detail: string;
  terms: string;
  normalizedName: string;
};

const kinds: Record<NodeKind, string> = { ecu: 'ECU', gateway: 'Gateway', sensor: 'Sensor', actuator: 'Aktor' };
const technologies: Record<string, string> = { can: 'CAN', can_fd: 'CAN FD', can_xl: 'CAN XL', lin: 'LIN', automotive_ethernet: 'Ethernet ETH', flexray: 'FlexRay' };

// Match readable names even when an import uses ue instead of ü, or separators differ.
const normalize = (value: string) => value.toLocaleLowerCase('de')
  .replace(/ä/g, 'ae').replace(/ö/g, 'oe').replace(/ü/g, 'ue').replace(/ß/g, 'ss')
  .normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();

/** Search the complete model, including nodes outside the rendered viewport. */
export function networkSearchEntries(topology: NetworkTopology): NetworkSearchEntry[] {
  const entry = (kind: NetworkSearchEntry['kind'], id: string, name: string, detail: string, aliases: string[]): NetworkSearchEntry => ({
    key: `${kind}:${id}`, id, kind, name, detail,
    normalizedName: normalize(name), terms: normalize([name, detail, ...aliases].join(' ')),
  });
  const frames = new Map<string, string>();
  topology.scene?.frames.forEach(frame => frame.memberIds.forEach(id => frames.set(id, frame.label)));
  const nodes = topology.nodes.map(node => entry('node', node.id, node.name,
    [kinds[node.kind], ...new Set(node.ports.map(port => technologies[port.bus]?.replace(' ETH', '') ?? port.bus)), frames.get(node.id)].filter(Boolean).join(' · '),
    [node.id, node.engineeringId ?? '', ...node.ports.flatMap(port => [port.name, port.physicalNetworkName ?? '', port.hardwareInterfaceId ?? '', technologies[port.bus] ?? port.bus])],
  ));
  const buses = topology.scene ? topology.scene.buses.map(bus => entry('bus', bus.id, bus.name,
    `Bus · ${technologies[bus.technology]?.replace(' ETH', '') ?? bus.technology} · ${bus.participantCount} Teilnehmer`,
    [bus.id, bus.labelText ?? '', technologies[bus.technology] ?? bus.technology],
  )) : topology.edges.map(edge => entry('edge', edge.id, edge.physicalNetworkName || edge.name || 'Busverbindung',
    `Verbindung · ${technologies[edge.bus]?.replace(' ETH', '') ?? edge.bus}`,
    [edge.id, edge.physicalNetworkId ?? '', edge.sourceInterfaceName ?? '', edge.targetInterfaceName ?? ''],
  ));
  return [...nodes, ...buses];
}

export function searchNetworkEntries(entries: NetworkSearchEntry[], query: string): NetworkSearchEntry[] {
  const text = normalize(query);
  if (!text) return [];
  const tokens = text.split(/\s+/);
  const rank = (entry: NetworkSearchEntry) => entry.normalizedName === text ? 0
    : entry.normalizedName.startsWith(text) ? 1 : entry.normalizedName.includes(text) ? 2 : 3;
  return entries.filter(entry => tokens.every(token => entry.terms.includes(token)))
    .sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name, 'de', { numeric: true }) || a.key.localeCompare(b.key));
}
