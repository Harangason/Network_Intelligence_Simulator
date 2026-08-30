import type { HardwareNode } from "./types";

export type NodeKind = "ecu" | "gateway" | "sensor" | "actuator";
export type BusType = "can_fd" | "lin" | "automotive_ethernet" | "flexray";
export type PortSide = "left" | "right";

export type TopologyPort = {
  id: string;
  name: string;
  bus: BusType;
  side: PortSide;
  offset: number;
  engineeringId?: string;
};

export type TopologyNode = {
  id: string;
  name: string;
  kind: NodeKind;
  x: number;
  y: number;
  width?: number;
  height?: number;
  ports: TopologyPort[];
  engineeringId?: string;
  engineeringFunctionId?: string;
  systemOwnerId?: string;
};

export type TopologyRouteMetadata = {
  routeId: string;
  routeCode: string;
  name: string;
  description?: string | null;
  source: string;
  target: string;
  sourceInterfaceId?: string | null;
  targetInterfaceId?: string | null;
  protocol?: string | null;
  approvalState: string;
};

export type TopologyEdge = {
  id: string;
  name?: string;
  sourceInterfaceName?: string;
  targetInterfaceName?: string;
  relationType?: "CONNECTED_TO" | "COMMUNICATES_WITH" | "CONNECTED_VIA";
  description?: string;
  direction?: "BIDIRECTIONAL" | "SOURCE_TO_TARGET" | "TARGET_TO_SOURCE";
  source: string;
  sourcePort: string;
  target: string;
  targetPort: string;
  bus: BusType;
  engineeringRelationId?: string;
  routingEntryId?: string;
  routingEntryIds?: string[];
  routingMetadata?: Record<string, TopologyRouteMetadata>;
  origin?: "ROUTING_TABLE";
};

export type TopologySyncResult = {
  topology_id: string;
  nodes: Array<{
    topology_node_id: string;
    engineering_id: string;
    engineering_name?: string;
    function_id: string;
    interfaces: Array<{ topology_port_id: string; engineering_id: string; engineering_name?: string }>;
  }>;
  edges: Array<{ topology_edge_id: string; engineering_relation_id: string }>;
  counts: {
    hardware_nodes: number;
    interfaces: number;
    connections: number;
  };
};

export type NetworkTopology = {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
};

function physicalEdgeKey(edge: TopologyEdge) {
  const endpoints = [
    `${edge.source}:${edge.sourcePort}`,
    `${edge.target}:${edge.targetPort}`,
  ].sort();
  return `${edge.bus}:${endpoints[0]}:${endpoints[1]}`;
}

export function collapsePhysicalEdges(edges: TopologyEdge[]): TopologyEdge[] {
  const physicalEdges = new Map<string, TopologyEdge>();
  for (const edge of edges) {
    const key = physicalEdgeKey(edge);
    const current = physicalEdges.get(key);
    const routeIds = [...new Set([
      ...(current?.routingEntryIds ?? []),
      ...(current?.routingEntryId ? [current.routingEntryId] : []),
      ...(edge.routingEntryIds ?? []),
      ...(edge.routingEntryId ? [edge.routingEntryId] : []),
    ])];
    if (current) {
      physicalEdges.set(key, {
        ...current,
        engineeringRelationId: current.engineeringRelationId ?? edge.engineeringRelationId,
        routingEntryId: current.routingEntryId ?? edge.routingEntryId,
        routingEntryIds: routeIds,
        routingMetadata: { ...(current.routingMetadata ?? {}), ...(edge.routingMetadata ?? {}) },
      });
      continue;
    }
    physicalEdges.set(key, {
      ...edge,
      routingEntryIds: routeIds,
    });
  }
  return [...physicalEdges.values()];
}

export function expandSharedPhysicalPorts(topology: NetworkTopology): NetworkTopology {
  type PortUse = { edgeId: string; endpoint: "source" | "target" };
  const portUses = new Map<string, PortUse[]>();
  const portKey = (nodeId: string, portId: string) => `${nodeId}\u0000${portId}`;

  for (const edge of topology.edges) {
    const sourceKey = portKey(edge.source, edge.sourcePort);
    const targetKey = portKey(edge.target, edge.targetPort);
    portUses.set(sourceKey, [...(portUses.get(sourceKey) ?? []), { edgeId: edge.id, endpoint: "source" }]);
    portUses.set(targetKey, [...(portUses.get(targetKey) ?? []), { edgeId: edge.id, endpoint: "target" }]);
  }

  const replacementIds = new Map<string, string>();
  const nodes = topology.nodes.map((node) => ({
    ...node,
    ports: node.ports.flatMap((port) => {
      const uses = [...(portUses.get(portKey(node.id, port.id)) ?? [])]
        .sort((left, right) => left.edgeId.localeCompare(right.edgeId) || left.endpoint.localeCompare(right.endpoint));
      if (uses.length <= 1) return [{ ...port }];
      return uses.map((use, index) => {
        const id = `${port.id}--connection-${index + 1}`;
        replacementIds.set(`${use.edgeId}\u0000${use.endpoint}`, id);
        return {
          ...port,
          id,
          offset: (index + 1) / (uses.length + 1),
        };
      });
    }),
  }));

  const edges = topology.edges.map((edge) => ({
    ...edge,
    sourcePort: replacementIds.get(`${edge.id}\u0000source`) ?? edge.sourcePort,
    targetPort: replacementIds.get(`${edge.id}\u0000target`) ?? edge.targetPort,
  }));
  return { ...topology, nodes, edges };
}

export function normalizePhysicalTopology(topology: NetworkTopology): NetworkTopology {
  return expandSharedPhysicalPorts({ ...topology, edges: collapsePhysicalEdges(topology.edges) });
}

export function engineeringHardwareKind(
  hardware: Pick<HardwareNode, "device_type" | "name">,
): NodeKind {
  if (hardware.device_type === "Gateway" || hardware.name.toLowerCase().includes("gateway")) {
    return "gateway";
  }
  if (hardware.device_type === "SensorController") return "sensor";
  if (hardware.device_type === "ActuatorController") return "actuator";
  return "ecu";
}

export const busProfiles: Record<BusType, { label: string; bitrate: number; cycleMs: number; payload: number; color: string }> = {
  can_fd: { label: "CAN FD", bitrate: 2_000_000, cycleMs: 10, payload: 64, color: "#9fea4e" },
  lin: { label: "LIN", bitrate: 19_200, cycleMs: 20, payload: 8, color: "#f2c94c" },
  automotive_ethernet: { label: "Ethernet", bitrate: 100_000_000, cycleMs: 5, payload: 1500, color: "#73a7ff" },
  flexray: { label: "FlexRay", bitrate: 10_000_000, cycleMs: 5, payload: 254, color: "#ef7d79" },
};

const slug = (value: string) => value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");

export function topologyToConfig(topology: NetworkTopology, formats: string[] = ["universal-jsonl", "universal-csv"]) {
  if (topology.nodes.length < 2) throw new Error("Füge mindestens zwei Geräte hinzu.");
  if (topology.edges.length === 0) throw new Error("Verdrahte mindestens zwei Geräte miteinander.");

  const grouped = new Map<BusType, TopologyEdge[]>();
  topology.edges.forEach((edge) => grouped.set(edge.bus, [...(grouped.get(edge.bus) ?? []), edge]));

  const networks = Array.from(grouped.entries()).map(([technology, edges]) => ({
    id: `network-${technology}`,
    technology,
    bitrate: busProfiles[technology].bitrate,
    cycle_ms: busProfiles[technology].cycleMs,
    nodes: Array.from(new Set(edges.flatMap((edge) => [edge.source, edge.target]))),
  }));

  const hardware = {
    nodes: topology.nodes.map((node) => ({
      id: node.id,
      name: node.name,
      type: node.kind,
      ports: node.ports.map((item, index) => ({
        id: item.id,
        name: item.name,
        port: index + 1,
        interfaces: [{
          id: `${item.id}-interface`,
          name: item.name,
          network_id: `network-${item.bus}`,
          technology: item.bus,
        }],
      })),
    })),
  };

  const nodeByEngineeringId = new Map(
    topology.nodes.filter((node) => node.engineeringId).map((node) => [node.engineeringId as string, node]),
  );
  const communications = topology.edges.flatMap((edge, edgeIndex) => {
    const metadata = Object.values(edge.routingMetadata ?? {});
    if (metadata.length === 0) {
      return [{
        id: `route-${edgeIndex + 1}-${slug(edge.source)}-${slug(edge.target)}`,
        source: edge.source,
        sender_interface: `${edge.sourcePort}-interface`,
        target: edge.target,
        receiver_interfaces: [`${edge.targetPort}-interface`],
        network: `network-${edge.bus}`,
        technology: edge.bus,
        cycle_ms: busProfiles[edge.bus].cycleMs,
        payload_bytes: Math.min(busProfiles[edge.bus].payload, 64),
        routing_entry_id: edge.routingEntryId,
        routing_entry_ids: edge.routingEntryIds ?? (edge.routingEntryId ? [edge.routingEntryId] : []),
      }];
    }
    return metadata.map((route) => {
      const sourceNode = nodeByEngineeringId.get(route.source);
      const targetNode = nodeByEngineeringId.get(route.target);
      const reversed = sourceNode?.id === edge.target && targetNode?.id === edge.source;
      return {
        id: route.routeId,
        name: route.name,
        source: sourceNode?.id ?? (reversed ? edge.target : edge.source),
        sender_interface: `${reversed ? edge.targetPort : edge.sourcePort}-interface`,
        target: targetNode?.id ?? (reversed ? edge.source : edge.target),
        receiver_interfaces: [`${reversed ? edge.sourcePort : edge.targetPort}-interface`],
        network: `network-${edge.bus}`,
        technology: edge.bus,
        cycle_ms: busProfiles[edge.bus].cycleMs,
        payload_bytes: Math.min(busProfiles[edge.bus].payload, 64),
        routing_entry_id: route.routeId,
        routing_entry_ids: [route.routeId],
      };
    });
  });

  return {
    config: {
      name: "ecu_network_topology",
      industry: "automotive",
      duration_s: 1,
      cycle_ms: Math.min(...Array.from(grouped.keys()).map((bus) => busProfiles[bus].cycleMs)),
      node_count: topology.nodes.length,
      max_events: 100_000,
      seed: 42,
      formats,
      technologies: Array.from(grouped.keys()),
      hardware,
      networks,
      communications,
      topology: { nodes: topology.nodes, edges: topology.edges },
    },
  };
}
