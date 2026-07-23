export type NodeKind = "ecu" | "gateway" | "sensor" | "actuator";
export type BusType = "can_fd" | "lin" | "automotive_ethernet" | "flexray";

export type TopologyNode = {
  id: string;
  name: string;
  kind: NodeKind;
  x: number;
  y: number;
};

export type TopologyEdge = {
  id: string;
  source: string;
  target: string;
  bus: BusType;
};

export type NetworkTopology = {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
};

export const busProfiles: Record<BusType, { label: string; bitrate: number; cycleMs: number; payload: number; color: string }> = {
  can_fd: { label: "CAN FD", bitrate: 2_000_000, cycleMs: 10, payload: 64, color: "#9fea4e" },
  lin: { label: "LIN", bitrate: 19_200, cycleMs: 20, payload: 8, color: "#f2c94c" },
  automotive_ethernet: { label: "Ethernet", bitrate: 100_000_000, cycleMs: 5, payload: 1500, color: "#73a7ff" },
  flexray: { label: "FlexRay", bitrate: 10_000_000, cycleMs: 5, payload: 254, color: "#ef7d79" },
};

export const initialTopology: NetworkTopology = {
  nodes: [
    { id: "ecu-central", name: "Central ECU", kind: "gateway", x: 370, y: 205 },
    { id: "ecu-powertrain", name: "Powertrain", kind: "ecu", x: 80, y: 70 },
    { id: "ecu-brake", name: "Brake ECU", kind: "ecu", x: 80, y: 340 },
    { id: "ecu-display", name: "Display", kind: "actuator", x: 680, y: 70 },
    { id: "ecu-radar", name: "Radar", kind: "sensor", x: 680, y: 340 },
  ],
  edges: [
    { id: "edge-powertrain", source: "ecu-powertrain", target: "ecu-central", bus: "can_fd" },
    { id: "edge-brake", source: "ecu-brake", target: "ecu-central", bus: "can_fd" },
    { id: "edge-display", source: "ecu-central", target: "ecu-display", bus: "automotive_ethernet" },
    { id: "edge-radar", source: "ecu-central", target: "ecu-radar", bus: "automotive_ethernet" },
  ],
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
    devices: topology.nodes.map((node) => {
      const connected = topology.edges.filter((edge) => edge.source === node.id || edge.target === node.id);
      return {
        id: node.id,
        name: node.name,
        type: node.kind,
        interfaces: connected.map((edge, index) => ({
          id: `${node.id}-if-${index + 1}`,
          network_id: `network-${edge.bus}`,
          technology: edge.bus,
          port: index + 1,
        })),
      };
    }),
  };

  const communications = topology.edges.map((edge, index) => ({
    id: `route-${index + 1}-${slug(edge.source)}-${slug(edge.target)}`,
    source: edge.source,
    target: edge.target,
    network_id: `network-${edge.bus}`,
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
