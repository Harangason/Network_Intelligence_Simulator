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
};

export type TopologyEdge = {
  id: string;
  source: string;
  sourcePort: string;
  target: string;
  targetPort: string;
  bus: BusType;
  engineeringRelationId?: string;
  routingEntryId?: string;
  origin?: "ROUTING_TABLE";
};

export type TopologySyncResult = {
  topology_id: string;
  nodes: Array<{
    topology_node_id: string;
    engineering_id: string;
    function_id: string;
    interfaces: Array<{ topology_port_id: string; engineering_id: string }>;
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

  const communications = topology.edges.map((edge, index) => ({
    id: `route-${index + 1}-${slug(edge.source)}-${slug(edge.target)}`,
    source: edge.source,
    sender_interface: `${edge.sourcePort}-interface`,
    target: edge.target,
    receiver_interfaces: [`${edge.targetPort}-interface`],
    network: `network-${edge.bus}`,
    technology: edge.bus,
    cycle_ms: busProfiles[edge.bus].cycleMs,
    payload_bytes: Math.min(busProfiles[edge.bus].payload, 64),
  }));

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
