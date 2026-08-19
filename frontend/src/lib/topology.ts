export type NodeKind = "ecu" | "gateway" | "sensor" | "actuator";
export type BusType = "can_fd" | "lin" | "automotive_ethernet" | "flexray";
export type PortSide = "left" | "right";

export type TopologyPort = {
  id: string;
  name: string;
  bus: BusType;
  side: PortSide;
  offset: number;
};

export type TopologyNode = {
  id: string;
  name: string;
  kind: NodeKind;
  x: number;
  y: number;
  ports: TopologyPort[];
};

export type TopologyEdge = {
  id: string;
  source: string;
  sourcePort: string;
  target: string;
  targetPort: string;
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

const port = (id: string, bus: BusType, side: PortSide, offset = 0.5): TopologyPort => ({
  id,
  name: busProfiles[bus].label,
  bus,
  side,
  offset,
});

export const initialTopology: NetworkTopology = {
  nodes: [
    { id: "ecu-central", name: "Central ECU", kind: "gateway", x: 370, y: 205, ports: [port("central-can-a", "can_fd", "left", 0.3), port("central-can-b", "can_fd", "left", 0.7), port("central-eth-a", "automotive_ethernet", "right", 0.3), port("central-eth-b", "automotive_ethernet", "right", 0.7)] },
    { id: "ecu-powertrain", name: "Powertrain", kind: "ecu", x: 80, y: 70, ports: [port("powertrain-can", "can_fd", "right")] },
    { id: "ecu-brake", name: "Brake ECU", kind: "ecu", x: 80, y: 340, ports: [port("brake-can", "can_fd", "right")] },
    { id: "ecu-display", name: "Display", kind: "actuator", x: 680, y: 70, ports: [port("display-eth", "automotive_ethernet", "left")] },
    { id: "ecu-radar", name: "Radar", kind: "sensor", x: 680, y: 340, ports: [port("radar-eth", "automotive_ethernet", "left")] },
  ],
  edges: [
    { id: "edge-powertrain", source: "ecu-powertrain", sourcePort: "powertrain-can", target: "ecu-central", targetPort: "central-can-a", bus: "can_fd" },
    { id: "edge-brake", source: "ecu-brake", sourcePort: "brake-can", target: "ecu-central", targetPort: "central-can-b", bus: "can_fd" },
    { id: "edge-display", source: "ecu-central", sourcePort: "central-eth-a", target: "ecu-display", targetPort: "display-eth", bus: "automotive_ethernet" },
    { id: "edge-radar", source: "ecu-central", sourcePort: "central-eth-b", target: "ecu-radar", targetPort: "radar-eth", bus: "automotive_ethernet" },
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
    devices: topology.nodes.map((node) => ({
      id: node.id,
      name: node.name,
      type: node.kind,
      interfaces: node.ports.map((item, index) => ({
        id: item.id,
        name: item.name,
        network_id: `network-${item.bus}`,
        technology: item.bus,
        port: index + 1,
      })),
    })),
  };

  const communications = topology.edges.map((edge, index) => ({
    id: `route-${index + 1}-${slug(edge.source)}-${slug(edge.target)}`,
    source: edge.source,
    source_interface: edge.sourcePort,
    target: edge.target,
    target_interface: edge.targetPort,
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
