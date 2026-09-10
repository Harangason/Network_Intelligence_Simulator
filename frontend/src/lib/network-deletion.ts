import type { NetworkTopology } from './topology';

export type NetworkSelection =
  | {kind:'node'; nodeId:string}
  | {kind:'port'; nodeId:string; portId:string}
  | {kind:'branch'; busId:string; portId:string}
  | {kind:'bus'; busId:string}
  | {kind:'edge'; edgeId:string};

/** Delete only the selected physical drawing entity and its incident connections. */
export function deleteNetworkSelection(topology:NetworkTopology, selection:NetworkSelection):NetworkTopology {
  const edges = topology.edges.filter(edge => {
    switch(selection.kind) {
      case 'node': return edge.source !== selection.nodeId && edge.target !== selection.nodeId;
      case 'port': return edge.sourcePort !== selection.portId && edge.targetPort !== selection.portId;
      case 'branch': return edge.physicalNetworkId !== selection.busId || (edge.sourcePort !== selection.portId && edge.targetPort !== selection.portId);
      case 'bus': return edge.physicalNetworkId !== selection.busId;
      case 'edge': return edge.id !== selection.edgeId;
    }
  });
  const nodes = topology.nodes.filter(n => selection.kind !== 'node' || n.id !== selection.nodeId)
    .map(n => selection.kind === 'port' && n.id === selection.nodeId
      ? {...n,ports:n.ports.filter(p=>p.id!==selection.portId)} : n);
  // Retain scene and manual layout; the server rebuilds its derived paths after saving.
  return {...topology,nodes,edges};
}
