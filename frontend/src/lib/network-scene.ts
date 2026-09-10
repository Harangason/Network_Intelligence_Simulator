import type { BusType, NetworkTopology, NodeKind, PortSide, TopologyNode } from "./topology";
import { withWireCrossings, type WireBridge } from './network-crossings.ts';

export type SceneBounds = { left: number; top: number; width: number; height: number };
export type ScenePoint = { x: number; y: number };
export type SceneFrame = SceneBounds & {
  id: string; memberIds: string[]; label: string; kind: NodeKind; count: number;
  inputs: number; processors: number; outputs: number; clusterId: string;
};
export type SceneCluster = SceneBounds & { id: string; label: string; memberIds: string[]; busLabel: string };
export type SceneBranch = {
  nodeId: string; portId: string; hardwareInterfaceId?: string; points: ScenePoint[]; path: string; bounds: SceneBounds;
  displayPath?: string;
};
export type SceneBus = {
  id: string; name: string; technology: BusType; edgeIds: string[]; routeIds: string[];
  participantCount: number; local: boolean; frameId: string | null; path: string; bounds: SceneBounds;
  label: ScenePoint; branches: SceneBranch[]; junctions: ScenePoint[];
  labelText?: string;
  displayPath?: string;
};
export type NetworkScene = {
  version: number; revision: string; modelSignature: string; width: number; height: number;
  frames: SceneFrame[]; clusters: SceneCluster[]; buses: SceneBus[];
  manualPositions: Record<string, Pick<TopologyNode, "x" | "y" | "width" | "height">>;
  manualBusRoutes?: Record<string, {trunkX?: number; branchY?: Record<string, number>}>;
  routingVersion?: number;
  routingWarnings?: string[];
  crossingVersion?: number;
  wireBridges?: WireBridge[];
};
const path = (points: ScenePoint[]) => points.map((p, i) => `${i ? "L" : "M"} ${p.x} ${p.y}`).join(" ");
const bounds = (points: ScenePoint[]): SceneBounds => {
  const left = Math.min(...points.map(p=>p.x)), top = Math.min(...points.map(p=>p.y));
  return {left, top, width: Math.max(...points.map(p=>p.x))-left, height: Math.max(...points.map(p=>p.y))-top};
};

// Rotated text extends to the left of its baseline; leave room for the glyphs.
export const BUS_LABEL_OFFSET = 26;
const LOCAL_BUS_LABEL_OFFSET = 20;

function branchPoints(first: ScenePoint, side: PortSide, x: number, y: number): ScenePoint[] {
  if (side === 'bottom') y = Math.max(first.y + 18, y);
  if (side === 'top') y = Math.max(0, Math.min(first.y - 18, y));
  if (side === 'bottom' || side === 'top') return [first, {x: first.x, y}, {x, y}];
  if (Math.abs(y - first.y) > .001) {
    const escape = first.x + (side === 'right' ? 24 : -24);
    return [first, {x: escape, y: first.y}, {x: escape, y}, {x, y}];
  }
  return [first, {x, y}];
}

function withBranches(bus: SceneBus, branches: SceneBranch[]): SceneBus {
  const anchors = branches.map(b => b.points[b.points.length - 1]);
  const x = anchors[0]?.x ?? bus.label.x;
  const trunk = [{x, y: Math.min(...anchors.map(p => p.y))}, {x, y: Math.max(...anchors.map(p => p.y))}];
  return {...bus, branches, junctions: busJunctions(branches), path: path(trunk),
    label: {x: x + (bus.local ? LOCAL_BUS_LABEL_OFFSET : BUS_LABEL_OFFSET), y: trunk[0].y + 16},
    bounds: bounds(branches.flatMap(b => b.points))};
}

/** Edit drawing coordinates only. Bus, device and routing identities stay intact. */
export function moveSceneWire(topology: NetworkTopology, busId: string, coordinate: number, portId?: string): NetworkTopology {
  if (!topology.scene) return topology;
  const scene = topology.scene, manual = structuredClone(scene.manualBusRoutes ?? {});
  coordinate = Math.max(0, Math.min(1000000, coordinate));
  const buses = scene.buses.map(bus => {
    if (bus.id !== busId) return bus;
    const entry = manual[busId] ??= {};
    if (!portId) entry.trunkX = coordinate;
    const branches = bus.branches.map(branch => {
      if (portId && portId !== branch.portId) return branch;
      const port = topology.nodes.find(n => n.id === branch.nodeId)?.ports.find(p => p.id === branch.portId);
      if (!port) return branch;
      const last = branch.points[branch.points.length - 1];
      const points = branchPoints(branch.points[0], port.side, portId ? last.x : coordinate, portId ? coordinate : last.y);
      if (portId) (entry.branchY ??= {})[portId] = points[points.length - 1].y;
      return {...branch, points, path: path(points), bounds: bounds(points)};
    });
    return withBranches(bus, branches);
  });
  return {...topology, scene: withWireCrossings({...scene, buses, manualBusRoutes: manual,
    width: Math.max(scene.width, ...buses.map(b => b.bounds.left + b.bounds.width + 60)),
    height: Math.max(scene.height, ...buses.map(b => b.bounds.top + b.bounds.height + 60))})};
}

export function isInlineBusBranch(branch: Pick<SceneBranch, "points">): boolean {
  return branch.points.length > 1 && branch.points.every(p => p.x === branch.points[0].x);
}

/** Real three-way connections only; also corrects previously saved scenes. */
export function busJunctions(branches: Pick<SceneBranch, "points">[]): ScenePoint[] {
  const anchors = branches.flatMap(b => b.points.length ? [b.points[b.points.length - 1]] : []);
  if (!anchors.length) return [];
  const trunk: [ScenePoint, ScenePoint] = [
    {x: anchors[0].x, y: Math.min(...anchors.map(p => p.y))},
    {x: anchors[0].x, y: Math.max(...anchors.map(p => p.y))},
  ];
  const segments = [trunk, ...branches.flatMap(b => b.points.slice(1).map((p, i) => [b.points[i], p]))];
  const unique = new Map(anchors.map(p => [`${p.x}:${p.y}`, p]));
  return [...unique.values()].filter(({x, y}) => {
    const directions = new Set<string>();
    for (const [a, b] of segments) {
      if (a.x === x && b.x === x && Math.min(a.y, b.y) <= y && y <= Math.max(a.y, b.y)) {
        if (Math.min(a.y, b.y) < y) directions.add("north");
        if (Math.max(a.y, b.y) > y) directions.add("south");
      }
      if (a.y === y && b.y === y && Math.min(a.x, b.x) <= x && x <= Math.max(a.x, b.x)) {
        if (Math.min(a.x, b.x) < x) directions.add("west");
        if (Math.max(a.x, b.x) > x) directions.add("east");
      }
    }
    return directions.size >= 3;
  });
}

/** Cheap drag preview only. The server persists and validates the final geometry. */
export function previewNetworkScene(scene: NetworkScene, baseline: NetworkTopology, current: NetworkTopology): NetworkScene {
  const manual = structuredClone(scene.manualBusRoutes ?? {});
  const old = new Map(baseline.nodes.map(n=>[n.id,n])), nodes = new Map(current.nodes.map(n=>[n.id,n]));
  const frames = scene.frames.map(frame => {
    const members = frame.memberIds.map(id=>nodes.get(id)).filter((n): n is TopologyNode=>!!n);
    if (!members.length || members.every(n => { const before=old.get(n.id); return before && before.x===n.x && before.y===n.y && before.width===n.width && before.height===n.height; })) return frame;
    const box = bounds(members.flatMap(n=>[{x:n.x-20,y:n.y-46},{x:n.x+(n.width??168)+20,y:n.y+(n.height??88)+26}]));
    return {...frame,...box};
  });
  const frameById = new Map(frames.map(frame => [frame.id, frame]));
  const buses = scene.buses.map(bus=>{
    const beforeFrame = scene.frames.find(frame => frame.id === bus.frameId), frame = bus.frameId ? frameById.get(bus.frameId) : undefined;
    const trunkDelta = frame && beforeFrame ? frame.left + frame.width/2 - beforeFrame.left - beforeFrame.width/2 : 0;
    const branches = bus.branches.map(branch=>{
      const node = nodes.get(branch.nodeId), before = old.get(branch.nodeId);
      if (!node || !before) return branch;
      const port = node.ports.find(p=>p.id===branch.portId);
      if (!port) return branch;
      const width=node.width??168, height=node.height??88, offset=port.offset??.5;
      const first = {x: node.x+(port.side==="left"?0:port.side==="right"?width:18+(width-36)*offset),
        y: node.y+(port.side==="top"?0:port.side==="bottom"?height:18+(height-36)*offset)};
      const last = {...branch.points[branch.points.length-1]};
      last.x += trunkDelta;
      last.y += first.y - branch.points[0].y;
      const points = branchPoints(first, port.side, last.x, last.y);
      const entry = manual[bus.id];
      if (entry?.branchY?.[branch.portId] !== undefined) entry.branchY[branch.portId] = points[points.length - 1].y;
      return {...branch,points,path:path(points),bounds:bounds(points)};
    });
    if (manual[bus.id]?.trunkX !== undefined) manual[bus.id].trunkX! += trunkDelta;
    return withBranches(bus, branches);
  });
  return withWireCrossings({...scene,frames,buses,manualBusRoutes:manual});
}
