import type { HardwareNode } from "./types";
import {
  inferTopologyClusterProfileFromText,
  topologyClusterForText,
  topologyClusterFamilyForKey,
} from "./topology-cluster-knowledge.ts";

export type NodeKind = "ecu" | "gateway" | "sensor" | "actuator";
export type BusType =
  | "can" | "can_xl" | "can_fd" | "lin" | "automotive_ethernet" | "flexray"
  | "i2c" | "spi" | "uart" | "modbus_rtu" | "modbus_tcp"
  | "gpio" | "pwm" | "adc" | "dac";
export type PortSide = "left" | "right" | "top" | "bottom";

export type TopologyPort = {
  id: string;
  name: string;
  nameSource?: "network" | "user";
  bus: BusType;
  side: PortSide;
  offset: number;
  engineeringId?: string;
  hardwareInterfaceId?: string;
  physicalNetworkId?: string;
  physicalNetworkName?: string;
  physicalNetworkNameSource?: "user" | "generated";
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
  engineeringFunctionId?: string | null;
  systemOwnerId?: string;
  systemOwnerSource?: string;
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
  engineeringSegmentId?: string;
  routingEntryId?: string;
  routingEntryIds?: string[];
  routingMetadata?: Record<string, TopologyRouteMetadata>;
  physicalNetworkId?: string;
  physicalNetworkName?: string;
  physicalNetworkNameSource?: "user" | "generated";
  origin?: "ROUTING_TABLE" | "WIZARD_PHYSICAL_COMPLETENESS" | "CANONICAL_BUS_BINDING";
};

export type TopologySyncResult = {
  topology_id: string;
  nodes: Array<{
    topology_node_id: string;
    engineering_id: string;
    engineering_name?: string;
    function_id?: string | null;
    interfaces: Array<{
      topology_port_id: string;
      engineering_id: string;
      engineering_name?: string;
      object_type?: "Interface" | "HardwareNetworkInterface";
      hardware_interface_id?: string;
    }>;
  }>;
  edges: Array<{ topology_edge_id: string; engineering_relation_id: string }>;
  counts: {
    hardware_nodes: number;
    interfaces: number;
    hardware_interfaces?: number;
    connections: number;
  };
};

export type NetworkTopology = {
  scene?: import("./network-scene").NetworkScene;
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

function collapseSharedHardwareInterfacePorts(topology: NetworkTopology): NetworkTopology {
  const replacements = new Map<string, string>();
  const nodes = topology.nodes.map((node) => {
    const canonicalByInterface = new Map<string, TopologyPort>();
    const ports: TopologyPort[] = [];
    for (const port of node.ports) {
      const interfaceId = port.hardwareInterfaceId;
      if (!interfaceId) {
        ports.push({ ...port });
        continue;
      }
      const key = `${interfaceId}\u0000${port.bus}\u0000${port.physicalNetworkId ?? ""}`;
      const canonical = canonicalByInterface.get(key);
      if (canonical) {
        replacements.set(`${node.id}\u0000${port.id}`, canonical.id);
        continue;
      }
      const normalized = {
        ...port,
        id: port.id.replace(/--connection-\d+$/, ""),
      };
      canonicalByInterface.set(key, normalized);
      replacements.set(`${node.id}\u0000${port.id}`, normalized.id);
      ports.push(normalized);
    }
    return { ...node, ports };
  });
  const edges = topology.edges.map((edge) => ({
    ...edge,
    sourcePort: replacements.get(`${edge.source}\u0000${edge.sourcePort}`) ?? edge.sourcePort,
    targetPort: replacements.get(`${edge.target}\u0000${edge.targetPort}`) ?? edge.targetPort,
  }));
  return { ...topology, nodes, edges };
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
      if (uses.length <= 1 || port.hardwareInterfaceId) return [{ ...port }];
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
  const collapsed = collapseSharedHardwareInterfacePorts(topology);
  const physical = assignSemanticPhysicalNetworks({ ...collapsed, edges: collapsePhysicalEdges(collapsed.edges) });
  const split = splitPortsByPhysicalNetwork(physical);
  const recollapsed = collapseSharedHardwareInterfacePorts(split);
  return expandSharedPhysicalPorts({ ...recollapsed, edges: collapsePhysicalEdges(recollapsed.edges) });
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

export type BusProfile = { label: string; bitrate: number; cycleMs: number; payload: number; color: string };

export const busProfiles: Record<BusType, BusProfile> = {
  can: { label: "CAN", bitrate: 500_000, cycleMs: 10, payload: 8, color: "#70c48c" },
  can_xl: { label: "CAN-XL", bitrate: 10_000_000, cycleMs: 10, payload: 2048, color: "#58bfc4" },
  can_fd: { label: "CAN FD", bitrate: 2_000_000, cycleMs: 10, payload: 64, color: "#9fea4e" },
  lin: { label: "LIN", bitrate: 19_200, cycleMs: 20, payload: 8, color: "#f2c94c" },
  automotive_ethernet: { label: "Ethernet", bitrate: 100_000_000, cycleMs: 5, payload: 1500, color: "#73a7ff" },
  flexray: { label: "FlexRay", bitrate: 10_000_000, cycleMs: 5, payload: 254, color: "#ef7d79" },
  i2c: { label: "I2C", bitrate: 400_000, cycleMs: 10, payload: 255, color: "#65c6c4" },
  spi: { label: "SPI", bitrate: 50_000_000, cycleMs: 5, payload: 65_535, color: "#cf8ee8" },
  uart: { label: "UART", bitrate: 115_200, cycleMs: 10, payload: 65_535, color: "#75a9e8" },
  modbus_rtu: { label: "Modbus RTU", bitrate: 115_200, cycleMs: 20, payload: 253, color: "#e5ad58" },
  modbus_tcp: { label: "Modbus TCP", bitrate: 100_000_000, cycleMs: 10, payload: 253, color: "#69b88d" },
  gpio: { label: "GPIO", bitrate: 1, cycleMs: 10, payload: 1, color: "#b6bec8" },
  pwm: { label: "PWM", bitrate: 1, cycleMs: 10, payload: 1, color: "#ed9368" },
  adc: { label: "ADC", bitrate: 1, cycleMs: 10, payload: 4, color: "#62b6a7" },
  dac: { label: "DAC", bitrate: 1, cycleMs: 10, payload: 4, color: "#dc85a6" },
};

const catalogBusProfiles: Record<string, BusProfile> = {
  profinet: { label: "PROFINET", bitrate: 100_000_000, cycleMs: 1, payload: 1440, color: "#4fb4d8" },
  io_link: { label: "IO-Link", bitrate: 230_400, cycleMs: 20, payload: 32, color: "#a3c95b" },
  ethercat: { label: "EtherCAT", bitrate: 100_000_000, cycleMs: 1, payload: 1486, color: "#e18a57" },
  opc_ua: { label: "OPC UA", bitrate: 100_000_000, cycleMs: 20, payload: 1500, color: "#5ba8a0" },
  ros2_dds: { label: "ROS 2 / DDS", bitrate: 1_000_000_000, cycleMs: 10, payload: 65_535, color: "#8b9fe8" },
};

function catalogTechnologyLabel(value: string) {
  return value
    .split(/[_\-\s]+/)
    .filter(Boolean)
    .map((part) => part.length <= 3 ? part.toUpperCase() : `${part[0].toUpperCase()}${part.slice(1)}`)
    .join(" ") || "Unbekannter Bus";
}

/** API topology data can contain technologies from the extensible catalog.
 * Render them deterministically even when the editor cannot offer them as a
 * manually selectable bus yet. */
export function busProfile(bus: string | null | undefined): BusProfile {
  const key = (bus ?? "").trim().toLowerCase();
  const known = busProfiles[key as BusType] ?? catalogBusProfiles[key];
  if (known) return known;
  let hash = 0;
  for (const character of key) hash = ((hash * 31) + character.charCodeAt(0)) >>> 0;
  return {
    label: catalogTechnologyLabel(key),
    bitrate: 1_000_000,
    cycleMs: 10,
    payload: 64,
    color: `hsl(${hash % 360} 48% 58%)`,
  };
}

const slug = (value: string) => value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");

export type PhysicalNetworkAssignment = {
  id: string;
  name: string;
  technology: BusType;
};

function busDisplayName(bus: BusType) {
  return bus === "can_fd" ? "CAN" : busProfile(bus).label;
}

/** Keep distinct physical buses distinct, while joining a complete semantic
 * system (for example motor, fuel, exhaust and transmission) on one domain bus. */
function inferredPhysicalNetworkAssignments(topology: NetworkTopology) {
  const nodes = new Map(topology.nodes.map((node) => [node.id, node]));
  const inferredProfile = inferTopologyClusterProfileFromText(
    topology.nodes.map((node) => `${node.name} ${node.kind}`).join(" "),
  );
  const profile = inferredProfile === "generic" && topology.edges.some((edge) => edge.bus === "can_fd")
    ? "automotive"
    : inferredProfile;
  const unknownComponents = new Map<string, number>();
  const componentByNode = new Map<string, number>();
  let nextComponent = 1;
  const result = new Map<string, PhysicalNetworkAssignment>();

  for (const bus of Object.keys(busProfiles) as BusType[]) {
    const busEdges = topology.edges.filter((edge) => edge.bus === bus);
    const adjacency = new Map<string, string[]>();
    busEdges.forEach((edge) => {
      adjacency.set(edge.source, [...(adjacency.get(edge.source) ?? []), edge.target]);
      adjacency.set(edge.target, [...(adjacency.get(edge.target) ?? []), edge.source]);
    });
    for (const nodeId of adjacency.keys()) {
      if (componentByNode.has(`${bus}:${nodeId}`)) continue;
      const component = nextComponent++;
      const pending = [nodeId];
      while (pending.length) {
        const current = pending.pop() as string;
        const key = `${bus}:${current}`;
        if (componentByNode.has(key)) continue;
        componentByNode.set(key, component);
        pending.push(...(adjacency.get(current) ?? []));
      }
    }
  }

  topology.edges.forEach((edge) => {
    const candidates = [nodes.get(edge.source), nodes.get(edge.target)]
      .filter((node): node is TopologyNode => Boolean(node && node.kind !== "gateway"));
    const families = candidates.map((node) => {
      const cluster = topologyClusterForText(`${node.name} ${node.systemOwnerSource ?? ""}`, profile);
      return {
        controller: node.kind === "ecu" ? 1 : 0,
        profileSpecific: profile === "generic" || !["control", "sensorics", "actuation"].includes(cluster.key) ? 1 : 0,
        family: topologyClusterFamilyForKey(cluster.key, profile),
      };
    }).filter((candidate) => !candidate.family.key.startsWith("system:"))
      .sort((left, right) => right.profileSpecific - left.profileSpecific || right.controller - left.controller);
    const family = families[0]?.family;
    const component = componentByNode.get(`${edge.bus}:${edge.source}`) ?? 0;
    const semanticKey = family?.key || `segment-${component}`;
    const label = family?.label || `Netzsegment ${component}`;
    const key = `${edge.bus}:${semanticKey}`;
    let ordinal = unknownComponents.get(key);
    if (!ordinal) {
      ordinal = unknownComponents.size + 1;
      unknownComponents.set(key, ordinal);
    }
    result.set(edge.id, {
      id: `${slug(label)}-${edge.bus.replaceAll("_", "-")}-${family ? "bus" : ordinal}`,
      name: `${label}-${busDisplayName(edge.bus)}`,
      technology: edge.bus,
    });
  });
  return result;
}

export function physicalNetworkAssignments(topology: NetworkTopology) {
  const inferred = inferredPhysicalNetworkAssignments(topology);
  const result = new Map<string, PhysicalNetworkAssignment>();
  topology.edges.forEach((edge) => {
    const fallback = inferred.get(edge.id) ?? {
      id: `network-${edge.bus}`,
      name: busProfile(edge.bus).label,
      technology: edge.bus,
    };
    result.set(edge.id, {
      id: edge.physicalNetworkId || fallback.id,
      name: edge.physicalNetworkName || fallback.name,
      technology: edge.bus,
    });
  });
  return result;
}

export function assignSemanticPhysicalNetworks(topology: NetworkTopology): NetworkTopology {
  const inferred = inferredPhysicalNetworkAssignments(topology);
  const isGenericPlaceholder = (id?: string) => !id || [
    "systemgruppe", "regelung", "aktorik", "sensorik", "netsegment", "system-",
  ].some((part) => id.includes(part));
  return {
    ...topology,
    edges: topology.edges.map((edge) => {
      const assignment = inferred.get(edge.id);
      if (!assignment) return edge;
      const replace = isGenericPlaceholder(edge.physicalNetworkId) && !isGenericPlaceholder(assignment.id);
      return {
        ...edge,
        physicalNetworkId: replace ? assignment.id : edge.physicalNetworkId || assignment.id,
        physicalNetworkName: replace ? assignment.name : edge.physicalNetworkName || assignment.name,
      };
    }),
  };
}

function splitPortsByPhysicalNetwork(topology: NetworkTopology): NetworkTopology {
  const uses = new Map<string, Array<{ edgeId: string; endpoint: "source" | "target"; networkId: string; networkName: string }>>();
  const addUse = (
    nodeId: string,
    portId: string,
    edgeId: string,
    endpoint: "source" | "target",
    networkId: string,
    networkName: string,
  ) => {
    const key = `${nodeId}\u0000${portId}`;
    uses.set(key, [...(uses.get(key) ?? []), { edgeId, endpoint, networkId, networkName }]);
  };
  topology.edges.forEach((edge) => {
    const networkId = edge.physicalNetworkId ?? `network-${edge.bus}`;
    const networkName = edge.physicalNetworkName ?? busProfile(edge.bus).label;
    addUse(edge.source, edge.sourcePort, edge.id, "source", networkId, networkName);
    addUse(edge.target, edge.targetPort, edge.id, "target", networkId, networkName);
  });

  const replacement = new Map<string, string>();
  const nodes = topology.nodes.map((node) => ({
    ...node,
    ports: node.ports.flatMap((port) => {
      const portUses = uses.get(`${node.id}\u0000${port.id}`) ?? [];
      const networks = [...new Map(portUses.map((use) => [use.networkId, use])).values()]
        .sort((left, right) => left.networkId.localeCompare(right.networkId));
      if (networks.length === 0) return [{ ...port }];
      if (networks.length === 1) {
        return [{
          ...port,
          name: port.physicalNetworkId ? networks[0].networkName : port.name,
          physicalNetworkId: networks[0].networkId,
          physicalNetworkName: networks[0].networkName,
        }];
      }
      return networks.map((network, index) => {
        const id = `${port.id}--network-${slug(network.networkId)}`;
        portUses.filter((use) => use.networkId === network.networkId).forEach((use) => {
          replacement.set(`${use.edgeId}\u0000${use.endpoint}`, id);
        });
        return {
          ...port,
          id,
          name: network.networkName,
          physicalNetworkId: network.networkId,
          physicalNetworkName: network.networkName,
          offset: (index + 1) / (networks.length + 1),
        };
      });
    }),
  }));
  return {
    nodes,
    edges: topology.edges.map((edge) => ({
      ...edge,
      sourcePort: replacement.get(`${edge.id}\u0000source`) ?? edge.sourcePort,
      targetPort: replacement.get(`${edge.id}\u0000target`) ?? edge.targetPort,
    })),
  };
}

export function topologyToConfig(topology: NetworkTopology, formats: string[] = ["universal-jsonl", "universal-csv"]) {
  if (topology.nodes.length < 2) throw new Error("Füge mindestens zwei Geräte hinzu.");
  if (topology.edges.length === 0) throw new Error("Verdrahte mindestens zwei Geräte miteinander.");

  const assignments = physicalNetworkAssignments(topology);
  const grouped = new Map<string, TopologyEdge[]>();
  topology.edges.forEach((edge) => {
    const networkId = assignments.get(edge.id)?.id ?? `network-${edge.bus}`;
    grouped.set(networkId, [...(grouped.get(networkId) ?? []), edge]);
  });

  const networks = Array.from(grouped.entries()).map(([id, edges]) => {
    const assignment = assignments.get(edges[0].id)!;
    const technology = assignment.technology;
    return ({
    id,
    name: assignment.name,
    technology,
    bitrate: busProfile(technology).bitrate,
    cycle_ms: busProfile(technology).cycleMs,
    nodes: Array.from(new Set(edges.flatMap((edge) => [edge.source, edge.target]))),
  }); });

  const networkByPort = new Map<string, string>();
  topology.edges.forEach((edge) => {
    const networkId = assignments.get(edge.id)?.id ?? `network-${edge.bus}`;
    networkByPort.set(`${edge.source}:${edge.sourcePort}`, networkId);
    networkByPort.set(`${edge.target}:${edge.targetPort}`, networkId);
  });

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
          network_id: networkByPort.get(`${node.id}:${item.id}`) ?? `network-${item.bus}`,
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
        network: assignments.get(edge.id)?.id ?? `network-${edge.bus}`,
        technology: edge.bus,
        cycle_ms: busProfile(edge.bus).cycleMs,
        payload_bytes: Math.min(busProfile(edge.bus).payload, 64),
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
        network: assignments.get(edge.id)?.id ?? `network-${edge.bus}`,
        technology: edge.bus,
        cycle_ms: busProfile(edge.bus).cycleMs,
        payload_bytes: Math.min(busProfile(edge.bus).payload, 64),
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
      cycle_ms: Math.min(...topology.edges.map((edge) => busProfile(edge.bus).cycleMs)),
      node_count: topology.nodes.length,
      max_events: 100_000,
      seed: 42,
      formats,
      technologies: [...new Set(topology.edges.map((edge) => edge.bus))],
      hardware,
      networks,
      communications,
      topology: { nodes: topology.nodes, edges: topology.edges },
    },
  };
}
