import type { NetworkTopology, TopologyEdge } from './topology';

export type ConnectionEndpoint = { kind: 'port'; nodeId: string; portId: string } | { kind: 'bus'; busId: string };

/** Attach a channel to an existing network, never merge two independently wired buses. */
export function planNetworkConnection(topology: NetworkTopology, source: ConnectionEndpoint, target: ConnectionEndpoint, edgeId: string) {
  const connected = new Set(topology.edges.flatMap(e => [e.sourcePort, e.targetPort]));
  function resolve(endpoint: ConnectionEndpoint) {
    const candidates = topology.nodes.flatMap(node => node.ports.map(port => ({ node, port })));
    const bus = endpoint.kind === 'bus' ? topology.scene?.buses.find(b => b.id === endpoint.busId) : undefined;
    const found = endpoint.kind === 'port'
      ? candidates.find(c => c.node.id === endpoint.nodeId && c.port.id === endpoint.portId)
      : candidates.filter(c => c.port.physicalNetworkId === endpoint.busId && connected.has(c.port.id))
        .sort((a, b) => {
          // Local buses belong to their controller, not to an arbitrary sensor.
          const rank = (c: typeof a) => c.node.id === bus?.frameId || c.node.engineeringId === bus?.frameId ? 0
            : c.node.kind === 'ecu' ? 1 : c.node.kind === 'gateway' ? 2 : 3;
          return rank(a) - rank(b) || a.node.id.localeCompare(b.node.id) || a.port.id.localeCompare(b.port.id);
        })[0];
    if (!found) throw new Error('Der Anschluss ist nicht mehr vorhanden. Bitte den aktuellen Projektstand laden.');
    const networkId = found.port.physicalNetworkId || topology.edges.find(e => e.sourcePort === found.port.id || e.targetPort === found.port.id)?.physicalNetworkId;
    const active = endpoint.kind === 'bus' || candidates.some(c => connected.has(c.port.id) && (
      c.port.id === found.port.id || (networkId && c.port.physicalNetworkId === networkId)
      || (found.port.hardwareInterfaceId && c.port.hardwareInterfaceId === found.port.hardwareInterfaceId)));
    return { ...found, networkId, active, name: bus?.name || found.port.physicalNetworkName || found.port.name };
  }
  const from = resolve(source), to = resolve(target);
  if (from.port.bus !== to.port.bus) throw new Error('Die Bustypen passen nicht zusammen. Bitte einen Port oder Bus desselben Typs wählen.');
  if (from.node.id === to.node.id) throw new Error('Quelle und Ziel gehören zum selben Gerät. Bitte einen anderen Teilnehmer wählen.');
  if (from.active && to.active) {
    if (from.networkId && from.networkId === to.networkId) throw new Error('Dieser Anschluss ist bereits mit dem Bus verbunden.');
    throw new Error('Beide Anschlüsse sind bereits verdrahtet. Zum Umhängen bitte die Buszuordnung bearbeiten; getrennte Busse werden nicht zusammengeführt.');
  }
  const network = to.active ? to : from.active ? from : to.networkId ? to : from;
  const networkId = network.networkId || `network-${edgeId}`;
  for (const endpoint of [from, to]) {
    if (!endpoint.active && endpoint.node.ports.some(p => p.id !== endpoint.port.id && p.physicalNetworkId === networkId && connected.has(p.id))) {
      throw new Error('Dieses Gerät ist bereits an den Bus angeschlossen. Bitte den vorhandenen Anschluss verwenden.');
    }
  }
  const name = network.name;
  const rebound = new Set([from.port.id, to.port.id]);
  const nodes = topology.nodes.map(node => ({ ...node, ports: node.ports.map(port => rebound.has(port.id)
    ? { ...port, physicalNetworkId: networkId, physicalNetworkName: name } : port) }));
  const edge: TopologyEdge = { id: edgeId, source: from.node.id, sourcePort: from.port.id,
    target: to.node.id, targetPort: to.port.id, bus: from.port.bus,
    physicalNetworkId: networkId, physicalNetworkName: name, relationType: 'CONNECTED_VIA', direction: 'BIDIRECTIONAL' };
  return { nodes, edge, sourceName: from.node.name, targetName: to.node.name, networkName: name };
}

/** Screen coordinates: a generous hit area that stays the same size at every zoom. */
export function findConnectionTarget(root: HTMLElement, x: number, y: number, portsOnly = false): ConnectionEndpoint | null {
  const viewport = root.getBoundingClientRect();
  if (x < viewport.left || x > viewport.right || y < viewport.top || y > viewport.bottom) return null;
  const ports = [...root.querySelectorAll<HTMLElement>('[data-port-id][data-node-id]')].map(element => {
    const rect = element.getBoundingClientRect();
    return { element, rect, distance: Math.hypot(x - (rect.left + rect.width / 2), y - (rect.top + rect.height / 2)) };
  }).filter(p => p.rect.width && p.rect.height && p.distance <= Math.max(12, p.rect.width / 2 + 5))
    .sort((a, b) => a.distance - b.distance);
  if (ports[0]) return {kind: 'port', nodeId: ports[0].element.dataset.nodeId!, portId: ports[0].element.dataset.portId!};
  if (portsOnly) return null;
  // Use the actual painted hit paths, including branches. Do not hit a bus behind a card or dialog.
  for (const [dx, dy] of [[0,0], [-6,0], [6,0], [0,-6], [0,6]]) {
    const element = document.elementFromPoint(x + dx, y + dy);
    if (!element || !root.contains(element)) continue;
    const bus = element.closest<SVGElement>('[data-physical-network-id]');
    if (bus) return {kind:'bus', busId: bus.dataset.physicalNetworkId!};
    if (element.closest('.net-node')) break;
  }
  return null;
}
