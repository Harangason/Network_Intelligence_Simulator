import type { NetworkTopology, TopologyEdge } from './topology';

export function transferableNodes(topology: NetworkTopology, edge: TopologyEdge) {
  const bus = topology.scene?.buses.find(b => b.id === edge.physicalNetworkId);
  if (!bus) return [];
  return topology.nodes.filter(n => [edge.source, edge.target].includes(n.id) && n.kind !== 'gateway'
    && (!bus.local || n.id !== bus.frameId))
    .sort((a, b) => a.name.localeCompare(b.name, 'de', { numeric: true }));
}

export function busTransferTargets(topology: NetworkTopology, sourceId: string, nodeId: string) {
  const scene = topology.scene, source = scene?.buses.find(b => b.id === sourceId);
  const cluster = scene?.clusters.find(c => c.memberIds.includes(nodeId));
  if (!scene || !source || !cluster || !source.branches.some(b => b.nodeId === nodeId)) return [];
  return scene.buses.filter(b => b.id !== sourceId && b.technology === source.technology
    && b.local === source.local && (!source.local || b.frameId === source.frameId)
    && b.branches.some(branch => cluster.memberIds.includes(branch.nodeId))
    && !b.branches.some(branch => branch.nodeId === nodeId))
    .sort((a, b) => a.name.localeCompare(b.name, 'de', { numeric: true }) || a.id.localeCompare(b.id));
}
