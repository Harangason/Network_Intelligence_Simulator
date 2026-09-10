import type { EngFunction } from './types';
import type { BusType, NetworkTopology, TopologyNode, TopologyEdge } from './topology';

export type DiagramMode = 'hardware' | 'functions' | 'combined';
export type GraphKind = TopologyNode['kind'] | 'root' | 'group' | 'function' | 'unmapped';
export type GraphNode = {
  id: string; name: string; kind: GraphKind; parentId?: string; children: string[]; depth: number;
  hardware?: TopologyNode; functionRef?: EngFunction; groupRole?: 'cluster' | 'frame'; buses?: BusType[];
  x: number; y: number; z: number; space: [number, number, number];
};
export type GraphLink = { id: string; source: string; target: string; kind: 'hierarchy' | 'physical' | 'mapping'; bus?: BusType; edge?: TopologyEdge };
export type HardwareGraph = { nodes: GraphNode[]; links: GraphLink[]; byId: Map<string, GraphNode>; maxDepth: number };
export const kindLabels: Record<GraphKind, string> = { root: 'Topologie', group: 'Gruppe', gateway: 'Gateway', ecu: 'ECU', sensor: 'Sensor', actuator: 'Aktor', function: 'Funktion', unmapped: 'Funktion ohne Hardware' };
export const kindColors: Record<GraphKind, string> = { root: '#a9ef52', group: '#6d9fb4', gateway: '#a9ef52', ecu: '#87cfff', sensor: '#ffd45b', actuator: '#f28b91', function: '#bc9bff', unmapped: '#ffad66' };
export const compareNames = (a: { name: string }, b: { name: string }) => a.name.localeCompare(b.name, 'de', { numeric: true, sensitivity: 'base' });

/** A read-only projection. Saved membership and exact IDs define the hierarchy;
 * names, bus labels and drawing coordinates never establish ownership or location. */
export function buildHardwareGraph(topology: NetworkTopology, functions: EngFunction[], mode: DiagramMode): HardwareGraph {
  const byId = new Map<string, GraphNode>();
  const add = (id: string, name: string, kind: GraphKind, parentId?: string, extra: Partial<GraphNode> = {}) => {
    if (!byId.has(id)) byId.set(id, { id, name, kind, parentId, children: [], depth: 0, x: 0, y: 0, z: 0, space: [0, 0, 0], ...extra });
    return id;
  };
  const root = add('view:root', 'Projekt-Topologie', 'root');
  const hardwareById = new Map(topology.nodes.flatMap(n => [[n.id, n], ...(n.engineeringId ? [[n.engineeringId, n] as const] : [])]));
  const clusters = new Map((topology.scene?.clusters ?? []).map(c => [c.id, c]));
  const frames = new Map((topology.scene?.frames ?? []).map(f => [f.id, f]));
  const framesByMember = new Map<string, string[]>();
  for (const frame of frames.values()) for (const id of frame.memberIds) framesByMember.set(id, [...(framesByMember.get(id) ?? []), frame.id]);
  const parentFor = (hardware?: TopologyNode) => {
    if (hardware?.kind === 'gateway') return root;
    const memberships = hardware ? framesByMember.get(hardware.id) ?? [] : [];
    // Ambiguous or missing saved membership stays explicitly unassigned.
    const frame = memberships.length === 1 ? frames.get(memberships[0]) : undefined;
    if (frame) {
      const cluster = clusters.get(frame.clusterId);
      const parent = cluster ? add(`view:cluster:${cluster.id}`, cluster.label, 'group', root, { groupRole: 'cluster' }) : root;
      return add(`view:frame:${frame.id}`, frame.label, 'group', parent, { groupRole: 'frame' });
    }
    const owner = hardware?.systemOwnerId ? hardwareById.get(hardware.systemOwnerId) : undefined;
    if (owner && owner.id !== hardware?.id) return add(`view:owner:${owner.id}`, owner.name, 'group', root, { groupRole: 'frame' });
    return add('view:unassigned', 'Zuordnung offen', 'group', root);
  };
  const links: GraphLink[] = [];
  if (mode !== 'functions') {
    for (const node of topology.nodes) add(node.id, node.name, node.kind, parentFor(node), { hardware: node });
    for (const edge of topology.edges) {
      if (byId.has(edge.source) && byId.has(edge.target)) links.push({ id: `edge:${edge.id}`, source: edge.source, target: edge.target, kind: 'physical', bus: edge.bus, edge });
    }
  }
  if (mode !== 'hardware') for (const fn of functions) {
    const hardware = fn.hardware_node_id ? hardwareById.get(fn.hardware_node_id) : undefined;
    const id = add(`function:${fn.id}`, fn.name, hardware ? 'function' : 'unmapped', parentFor(hardware), { functionRef: fn, buses: hardware?.ports.map(p => p.bus) });
    if (hardware && mode === 'combined') links.push({ id: `mapping:${fn.id}`, source: id, target: hardware.id, kind: 'mapping' });
  }
  for (const node of byId.values()) if (node.parentId) {
    byId.get(node.parentId)?.children.push(node.id);
    links.push({ id: `hierarchy:${node.id}`, source: node.parentId, target: node.id, kind: 'hierarchy' });
  }
  for (const node of byId.values()) node.children.sort((a, b) => compareNames(byId.get(a)!, byId.get(b)!));
  const weight = new Map<string, number>();
  const weigh = (id: string): number => {
    const children = byId.get(id)!.children;
    const value = children.length ? children.reduce((sum, child) => sum + weigh(child), 0) + Math.max(0, children.length - 1) * .5 : 1;
    weight.set(id, value); return value;
  };
  weigh(root);
  let maxDepth = 0;
  const place = (id: string, depth: number, start: number, span: number, branch: number) => {
    const node = byId.get(id)!;
    node.depth = depth; maxDepth = Math.max(maxDepth, depth);
    const angle = start + span / 2 - Math.PI / 2;
    const radius = depth * 225;
    node.x = Math.cos(angle) * radius; node.y = Math.sin(angle) * radius;
    if (depth) {
      // Hierarchical spherical sectors, deliberately independent of installation zones.
      const branches = byId.get(root)!.children.length;
      const vertical = branches <= 1 ? 0 : 1 - 2 * (branch + .5) / branches;
      const phi = branch * Math.PI * (3 - Math.sqrt(5));
      let direction = [Math.sqrt(1 - vertical * vertical) * Math.cos(phi), vertical, Math.sqrt(1 - vertical * vertical) * Math.sin(phi)];
      if (depth > 1) {
        const parent = byId.get(node.parentId!)!, length = Math.hypot(...parent.space);
        const axis = parent.space.map(v => v / length);
        const side = Math.abs(axis[1]) < .9 ? [-axis[2], 0, axis[0]] : [0, axis[2], -axis[1]];
        const sideLength = Math.hypot(...side); side.forEach((v, i) => { side[i] = v / sideLength; });
        const up = [axis[1] * side[2] - axis[2] * side[1], axis[2] * side[0] - axis[0] * side[2], axis[0] * side[1] - axis[1] * side[0]];
        const index = parent.children.indexOf(id), theta = index * Math.PI * (3 - Math.sqrt(5));
        const spread = (depth === 2 ? .72 : .28) * Math.sqrt((index + .5) / parent.children.length);
        direction = axis.map((v, i) => v + spread * (Math.cos(theta) * side[i] + Math.sin(theta) * up[i]));
      }
      const length = Math.hypot(...direction);
      node.space = direction.map(v => v * radius / length) as [number, number, number];
    }
    let cursor = start;
    node.children.forEach((child, index) => {
      const childSpan = span * weight.get(child)! / weight.get(id)!;
      place(child, depth + 1, cursor, childSpan, depth === 0 ? index : branch);
      cursor += childSpan + span * .5 / weight.get(id)!;
    });
  };
  place(root, 0, 0, Math.PI * 2, 0);
  return { nodes: [...byId.values()], links, byId, maxDepth };
}

export function nodePath(graph: HardwareGraph, id: string): GraphNode[] {
  const path: GraphNode[] = [], seen = new Set<string>();
  let node = graph.byId.get(id);
  while (node && !seen.has(node.id)) { path.unshift(node); seen.add(node.id); node = node.parentId ? graph.byId.get(node.parentId) : undefined; }
  return path;
}

export function visibleHardwareGraph(graph: HardwareGraph, options: { query: string; kind: string; bus: string; depth: number; collapsed: Set<string>; physical: boolean }) {
  const query = options.query.trim().toLocaleLowerCase('de');
  const matches = graph.nodes.filter(node => {
    const matchesBus = !options.bus || node.buses?.some(b => b === options.bus) || node.hardware?.ports.some(p => p.bus === options.bus) || graph.links.some(l => l.bus === options.bus && (l.source === node.id || l.target === node.id));
    return (!query || node.name.toLocaleLowerCase('de').includes(query)) && (!options.kind || node.kind === options.kind) && matchesBus;
  }).sort(compareNames);
  const context = new Set(matches.flatMap(n => nodePath(graph, n.id).map(p => p.id)));
  const searching = Boolean(query || options.kind || options.bus);
  const nodes = graph.nodes.filter(n => context.has(n.id) && (searching || n.depth <= options.depth && !nodePath(graph, n.id).slice(0, -1).some(p => options.collapsed.has(p.id))));
  const ids = new Set(nodes.map(n => n.id));
  return { nodes, links: graph.links.filter(l => ids.has(l.source) && ids.has(l.target) && (options.physical || l.kind !== 'physical') && (!options.bus || l.kind !== 'physical' || l.bus === options.bus)), matches, matchIds: new Set(matches.map(n => n.id)) };
}

export type ViewTransform = { x: number; y: number; scale: number };
export function fitGraph2D(nodes: Pick<GraphNode, 'x' | 'y'>[], width: number, height: number): ViewTransform {
  if (!nodes.length) return { x: width / 2, y: height / 2, scale: 1 };
  const minX = Math.min(...nodes.map(n => n.x)) - 135, maxX = Math.max(...nodes.map(n => n.x)) + 135;
  const minY = Math.min(...nodes.map(n => n.y)) - 45, maxY = Math.max(...nodes.map(n => n.y)) + 45;
  const scale = Math.max(.05, Math.min(2, (width - 48) / (maxX - minX), (height - 48) / (maxY - minY)));
  return { x: width / 2 - (minX + maxX) * scale / 2, y: height / 2 - (minY + maxY) * scale / 2, scale };
}

export function graphLinkPath(source: GraphNode, target: GraphNode, kind: GraphLink['kind']) {
  if (kind !== 'hierarchy') return `M ${source.x} ${source.y} L ${target.x} ${target.y}`;
  return `M ${source.x} ${source.y} C ${source.x * .55} ${source.y * .55} ${target.x * .55} ${target.y * .55} ${target.x} ${target.y}`;
}
