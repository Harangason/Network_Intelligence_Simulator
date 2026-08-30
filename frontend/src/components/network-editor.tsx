"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  busProfiles,
  engineeringHardwareKind,
  type BusType,
  type NetworkTopology,
  type NodeKind,
  type PortSide,
  type TopologyEdge,
  type TopologyNode,
  type TopologyPort,
} from "@/lib/topology";
import type { HardwareNode, RoutingEntry } from "@/lib/types";
import { setWorkflowContext } from "@/lib/workflow-api";

const NODE_DEFAULT_WIDTH = 168;
const NODE_MIN_WIDTH = 140;
const NODE_MIN_HEIGHT = 84;
const PORT_DIAMETER = 14;
const PORT_OFFSET = PORT_DIAMETER / 2 + 1;
const PORT_SAFE_INSET = 18;
const PORT_VISUAL_GAP = 7.5;
const PORT_CENTER_GAP = PORT_DIAMETER + PORT_VISUAL_GAP;
const EDGE_LANE_GAP = 7.5;
const ENDPOINT_NODE_WIDTH = 62;
const ENDPOINT_NAME_PADDING = 54;
const ENDPOINT_CHARACTER_WIDTH = 7.25;
const MENU_WIDTH = 210;
const MENU_EDGE_GAP = 8;
const CANVAS_MARGIN = 36;
const CANVAS_EXTRA_SPACE = 320;
const EVA_LABEL_HEIGHT = 72;
const EVA_ROW_GAP = 38;
const EVA_CLUSTER_GAP = 48;
const EVA_CLUSTER_PADDING = 18;
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 1.5;
const ZOOM_STEP = 0.1;
const LARGE_TOPOLOGY_NODE_THRESHOLD = 48;
const LARGE_TOPOLOGY_EDGE_THRESHOLD = 48;

const kindLabels: Record<NodeKind, string> = {
  ecu: "ECU",
  gateway: "Gateway",
  sensor: "Sensor",
  actuator: "Aktor",
};

const busOrder: BusType[] = ["can_fd", "lin", "automotive_ethernet", "flexray"];

type DragState =
  | { mode: "move"; nodeId: string; offsetX: number; offsetY: number }
  | {
      mode: "move-cluster";
      clusterId: string;
      startX: number;
      startY: number;
      members: Array<{ id: string; x: number; y: number }>;
    }
  | { mode: "resize"; nodeId: string; startX: number; startY: number; startWidth: number; startHeight: number }
  | { mode: "move-port"; nodeId: string; portId: string }
  | { mode: "wire"; nodeId: string; portId: string; bus: BusType; x: number; y: number };

type MenuState = { nodeId: string; x: number; y: number; side: PortSide; offset: number };
type RelationshipDraft = {
  edge: TopologyEdge;
  isNew: boolean;
  name: string;
  sourceInterfaceName: string;
  targetInterfaceName: string;
  relationType: NonNullable<TopologyEdge["relationType"]>;
  description: string;
  direction: NonNullable<TopologyEdge["direction"]>;
};

let counter = 0;
const nextId = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${(counter++).toString(36)}`;

const interfaceNameSuffix: Record<BusType, string> = {
  can_fd: "CAN_FD",
  lin: "LIN",
  automotive_ethernet: "Ethernet",
  flexray: "FlexRay",
};

function automaticInterfaceName(nodeName: string, bus: BusType) {
  const owner = nodeName
    .trim()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^A-Za-z0-9]+/g, "") || "Interface";
  return `${owner}_${interfaceNameSuffix[bus]}`;
}

function relationshipInterfaceName(
  savedName: string | undefined,
  node: TopologyNode | undefined,
  portId: string,
  bus: BusType,
) {
  if (savedName?.trim()) return savedName.trim();
  const portName = node?.ports.find((port) => port.id === portId)?.name.trim();
  const normalizedPortName = portName?.toLowerCase().replace(/[^a-z0-9]+/g, "");
  const genericNames = [busProfiles[bus].label, interfaceNameSuffix[bus], bus]
    .map((name) => name.toLowerCase().replace(/[^a-z0-9]+/g, ""));
  if (portName && normalizedPortName && !genericNames.includes(normalizedPortName)) return portName;
  return automaticInterfaceName(node?.name ?? "Interface", bus);
}

function nodeWidth(node: TopologyNode) {
  const minimumWidth = node.kind === "sensor" || node.kind === "actuator"
    ? ENDPOINT_NODE_WIDTH
    : NODE_MIN_WIDTH;
  const defaultWidth = node.kind === "sensor" || node.kind === "actuator"
    ? ENDPOINT_NODE_WIDTH
    : NODE_DEFAULT_WIDTH;
  return Math.max(minimumWidth, node.width ?? defaultWidth);
}

function nodeContentHeight(node: TopologyNode) {
  if (node.kind === "sensor" || node.kind === "actuator") return NODE_MIN_HEIGHT;
  const charactersPerLine = Math.max(10, Math.floor((nodeWidth(node) - 32) / 8));
  const nameLines = Math.max(1, Math.ceil(node.name.length / charactersPerLine));
  const contentHeight = node.ports.length === 0 ? 86 : 66;
  const visiblePortRows = Math.ceil(Math.min(node.ports.length, 8) / 2);
  return Math.max(
    NODE_MIN_HEIGHT,
    contentHeight + (nameLines - 1) * 18 + visiblePortRows * 12,
  );
}

function nodeHeight(node: TopologyNode) {
  return Math.max(nodeContentHeight(node), node.height ?? NODE_MIN_HEIGHT);
}

function endpointNameHeight(name: string) {
  return Math.ceil(Math.max(NODE_MIN_HEIGHT, ENDPOINT_NAME_PADDING + name.length * ENDPOINT_CHARACTER_WIDTH));
}

function endpointRowHeight(nodes: TopologyNode[]) {
  return Math.max(NODE_MIN_HEIGHT, ...nodes.map((node) => endpointNameHeight(node.name)));
}

function portTop(node: TopologyNode, port: TopologyPort) {
  const height = nodeHeight(node);
  return PORT_SAFE_INSET + Math.max(0, Math.min(1, port.offset ?? 0.5)) * (height - PORT_SAFE_INSET * 2);
}

function portLeft(node: TopologyNode, port: TopologyPort) {
  const width = nodeWidth(node);
  return PORT_SAFE_INSET + Math.max(0, Math.min(1, port.offset ?? 0.5)) * (width - PORT_SAFE_INSET * 2);
}

function nearestPortPlacement(node: TopologyNode, point: { x: number; y: number }) {
  const width = nodeWidth(node);
  const height = nodeHeight(node);
  const localX = Math.max(0, Math.min(width, point.x - node.x));
  const localY = Math.max(0, Math.min(height, point.y - node.y));
  const candidates: Array<{ side: PortSide; distance: number }> = [
    { side: "left", distance: localX },
    { side: "right", distance: width - localX },
    { side: "top", distance: localY },
    { side: "bottom", distance: height - localY },
  ];
  const side = candidates.sort((left, right) => left.distance - right.distance)[0].side;
  const horizontalAxis = side === "top" || side === "bottom";
  const coordinate = horizontalAxis ? localX : localY;
  const axisLength = horizontalAxis ? width : height;
  const offset = Math.max(0, Math.min(1, (coordinate - PORT_SAFE_INSET) / Math.max(1, axisLength - PORT_SAFE_INSET * 2)));
  return { side, offset };
}

function connectedPortSide(topology: NetworkTopology, node: TopologyNode, port: TopologyPort): PortSide {
  const nodeCenter = { x: node.x + nodeWidth(node) / 2, y: node.y + nodeHeight(node) / 2 };
  const connectedCenters = topology.edges.flatMap((edge) => {
    const usesSource = edge.source === node.id && edge.sourcePort === port.id;
    const usesTarget = edge.target === node.id && edge.targetPort === port.id;
    if (!usesSource && !usesTarget) return [];
    const otherId = usesSource ? edge.target : edge.source;
    const other = topology.nodes.find((item) => item.id === otherId);
    return other ? [{ x: other.x + nodeWidth(other) / 2, y: other.y + nodeHeight(other) / 2 }] : [];
  });
  if (!connectedCenters.length) return port.side;
  const averageOtherCenter = connectedCenters.reduce(
    (sum, value) => ({ x: sum.x + value.x, y: sum.y + value.y }),
    { x: 0, y: 0 },
  );
  averageOtherCenter.x /= connectedCenters.length;
  averageOtherCenter.y /= connectedCenters.length;
  const deltaX = averageOtherCenter.x - nodeCenter.x;
  const deltaY = averageOtherCenter.y - nodeCenter.y;
  if (Math.abs(deltaY) >= Math.abs(deltaX)) return deltaY < 0 ? "top" : "bottom";
  return deltaX < 0 ? "left" : "right";
}

function normalizePortSides(topology: NetworkTopology): NetworkTopology {
  return {
    ...topology,
    nodes: topology.nodes.map((node) => ({
      ...node,
      ports: node.ports.map((port) => ({ ...port, side: connectedPortSide(topology, node, port) })),
    })),
  };
}

function connectedNodesForPort(topology: NetworkTopology, node: TopologyNode, port: TopologyPort) {
  const nodesById = new Map(topology.nodes.map((item) => [item.id, item]));
  return topology.edges.flatMap((edge) => {
    if (edge.source === node.id && edge.sourcePort === port.id) {
      const other = nodesById.get(edge.target);
      return other ? [other] : [];
    }
    if (edge.target === node.id && edge.targetPort === port.id) {
      const other = nodesById.get(edge.source);
      return other ? [other] : [];
    }
    return [];
  });
}

const gatewayBusLabels: Record<BusType, string> = {
  can_fd: "CAN",
  lin: "LIN",
  automotive_ethernet: "Ethernet",
  flexray: "FlexRay",
};

function gatewayDomainLabel(nodeName: string) {
  const normalized = nodeName
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
  const domains: Array<[RegExp, string]> = [
    [/motorsteuer|getriebe|abgas|kraftstoff|inverter|elektromotor/, "Antriebs"],
    [/brems|stabil|fahrwerk|daempfer|dampfer|lenkung|reifen/, "Fahrdynamik"],
    [/klima|thermal/, "Klima"],
    [/batterie|energieversorgung|bordnetz/, "Energie"],
    [/bodycontrol|karosserie/, "Karosserie"],
    [/fahrassist|\badas\b|radar|kamera/, "ADAS"],
    [/infotainment/, "Infotainment"],
    [/konnektiv|telematik/, "Konnektivitaets"],
    [/diagnose/, "Diagnose"],
    [/zentralrechner/, "Backbone"],
  ];
  const match = domains.find(([pattern]) => pattern.test(normalized));
  if (match) return match[1];
  return nodeName
    .replace(/(?:-|\s)*(?:ECU|Gateway|Sensor|Aktor|Controller)$/i, "")
    .replace(/[^\p{L}\p{N}]+/gu, "-")
    .replace(/^-|-$/g, "") || "System";
}

function semanticGatewayInterfaceName(topology: NetworkTopology, gateway: TopologyNode, port: TopologyPort) {
  const connectedNode = connectedNodesForPort(topology, gateway, port)[0];
  if (!connectedNode) return port.name;
  return `${gatewayDomainLabel(connectedNode.name)}-${gatewayBusLabels[port.bus]}`;
}

function gatewayInterfaceNames(topology: NetworkTopology) {
  const names = new Map<string, string>();
  topology.nodes.filter((node) => node.kind === "gateway").forEach((gateway) => {
    const occurrences = new Map<string, number>();
    gateway.ports.forEach((port) => {
      const baseName = semanticGatewayInterfaceName(topology, gateway, port);
      const occurrence = (occurrences.get(baseName) ?? 0) + 1;
      occurrences.set(baseName, occurrence);
      names.set(`${gateway.id}\u0000${port.id}`, occurrence === 1 ? baseName : `${baseName} ${occurrence}`);
    });
  });
  return names;
}

function nameGatewayInterfaces(topology: NetworkTopology): NetworkTopology {
  const interfaceNames = gatewayInterfaceNames(topology);
  const nodes = topology.nodes.map((node) => {
    if (node.kind !== "gateway") return node;
    return {
      ...node,
      ports: node.ports.map((port) => {
        const name = interfaceNames.get(`${node.id}\u0000${port.id}`) ?? port.name;
        return { ...port, name };
      }),
    };
  });
  return {
    ...topology,
    nodes,
    edges: topology.edges.map((edge) => ({
      ...edge,
      sourceInterfaceName: interfaceNames.get(`${edge.source}\u0000${edge.sourcePort}`) ?? edge.sourceInterfaceName,
      targetInterfaceName: interfaceNames.get(`${edge.target}\u0000${edge.targetPort}`) ?? edge.targetInterfaceName,
    })),
  };
}

function schemaPortSide(topology: NetworkTopology, node: TopologyNode, port: TopologyPort): PortSide {
  const connectedNodes = connectedNodesForPort(topology, node, port);
  if (!connectedNodes.length) return port.side;
  if (node.kind === "gateway") {
    const primaryGateway = primaryGatewayFor(topology);
    if (primaryGateway && node.id !== primaryGateway.id && connectedNodes.some((other) => other.id === primaryGateway.id)) {
      return "top";
    }
    return "bottom";
  }
  if (node.kind === "sensor" || node.kind === "actuator") return "top";
  if (node.kind === "ecu") {
    return connectedNodes.some((other) => other.kind === "gateway") ? "top" : "bottom";
  }
  return connectedPortSide(topology, node, port);
}

function portAwareNodeSize(topology: NetworkTopology, node: TopologyNode) {
  const connectedPortIds = new Set(
    topology.edges.flatMap((edge) => {
      if (edge.source === node.id) return [edge.sourcePort];
      if (edge.target === node.id) return [edge.targetPort];
      return [];
    }),
  );
  const ports = topology.nodes.length >= LARGE_TOPOLOGY_NODE_THRESHOLD
    ? node.ports.filter((port) => connectedPortIds.has(port.id))
    : node.ports;
  const sideCounts: Record<PortSide, number> = { left: 0, right: 0, top: 0, bottom: 0 };
  ports.forEach((port) => {
    sideCounts[schemaPortSide(topology, node, port)] += 1;
  });
  const maximumVerticalSideCount = Math.max(sideCounts.left, sideCounts.right);
  const maximumHorizontalSideCount = Math.max(sideCounts.top, sideCounts.bottom);
  const portWidth = PORT_SAFE_INSET * 2 + Math.max(0, maximumHorizontalSideCount - 1) * PORT_CENTER_GAP;
  const defaultWidth = node.kind === "sensor" || node.kind === "actuator"
    ? ENDPOINT_NODE_WIDTH
    : NODE_DEFAULT_WIDTH;
  const width = Math.ceil(Math.max(defaultWidth, portWidth));
  const height = Math.ceil(Math.max(
    nodeContentHeight({ ...node, width, height: undefined }),
    PORT_SAFE_INSET * 2 + Math.max(0, maximumVerticalSideCount - 1) * PORT_CENTER_GAP,
  ));
  return { width, height };
}

function sizeNodesForPorts(topology: NetworkTopology): NetworkTopology {
  return {
    ...topology,
    nodes: topology.nodes.map((node) => ({ ...node, ...portAwareNodeSize(topology, node) })),
  };
}

function orderPortsByConnectedNodes(topology: NetworkTopology): NetworkTopology {
  const nodesById = new Map(topology.nodes.map((node) => [node.id, node]));
  return {
    ...topology,
    nodes: topology.nodes.map((node) => {
      const portLayout = node.ports.map((port) => {
        const connectedNodes = topology.edges.flatMap((edge) => {
          if (edge.source === node.id && edge.sourcePort === port.id) {
            const other = nodesById.get(edge.target);
            return other ? [other] : [];
          }
          if (edge.target === node.id && edge.targetPort === port.id) {
            const other = nodesById.get(edge.source);
            return other ? [other] : [];
          }
          return [];
        });
        const averageCounterpartX = connectedNodes.length > 0
          ? connectedNodes.reduce((total, other) => total + other.x + nodeWidth(other) / 2, 0) / connectedNodes.length
          : Number.POSITIVE_INFINITY;
        const averageCounterpartY = connectedNodes.length > 0
          ? connectedNodes.reduce((total, other) => total + other.y + nodeHeight(other) / 2, 0) / connectedNodes.length
          : Number.POSITIVE_INFINITY;
        return {
          port,
          side: schemaPortSide(topology, node, port),
          averageCounterpartX,
          averageCounterpartY,
          counterpartName: connectedNodes.map((other) => other.name).sort((left, right) => left.localeCompare(right, "de"))[0] ?? "",
        };
      });
      const updated = new Map<string, TopologyPort>();
      (["left", "right", "top", "bottom"] as const).forEach((side) => {
        const horizontalAxis = side === "top" || side === "bottom";
        const sidePorts = portLayout
          .filter((item) => item.side === side && Number.isFinite(
            horizontalAxis ? item.averageCounterpartX : item.averageCounterpartY,
          ))
          .sort((left, right) =>
            (horizontalAxis
              ? left.averageCounterpartX - right.averageCounterpartX
              : left.averageCounterpartY - right.averageCounterpartY)
            || left.counterpartName.localeCompare(right.counterpartName, "de")
            || busOrder.indexOf(left.port.bus) - busOrder.indexOf(right.port.bus)
            || left.port.name.localeCompare(right.port.name, "de")
            || left.port.id.localeCompare(right.port.id)
          );
        if (sidePorts.length === 0) return;
        const dimension = horizontalAxis ? nodeWidth(node) : nodeHeight(node);
        const usableLength = Math.max(1, dimension - PORT_SAFE_INSET * 2);
        const counterpartCoordinate = (item: (typeof sidePorts)[number]) =>
          horizontalAxis ? item.averageCounterpartX - node.x : item.averageCounterpartY - node.y;
        const centeredStart = dimension / 2 - (sidePorts.length - 1) * PORT_CENTER_GAP / 2;
        const centers = sidePorts.map((item, index) => side === "top"
          ? centeredStart + index * PORT_CENTER_GAP
          : Math.max(
              PORT_SAFE_INSET,
              Math.min(dimension - PORT_SAFE_INSET, counterpartCoordinate(item)),
            ));
        for (let index = 1; index < centers.length; index += 1) {
          centers[index] = Math.max(centers[index], centers[index - 1] + PORT_CENTER_GAP);
        }
        const overflow = centers[centers.length - 1] - (dimension - PORT_SAFE_INSET);
        if (overflow > 0) {
          centers[centers.length - 1] -= overflow;
          for (let index = centers.length - 2; index >= 0; index -= 1) {
            centers[index] = Math.min(centers[index], centers[index + 1] - PORT_CENTER_GAP);
          }
        }
        sidePorts.forEach((item, index) => {
          const offset = Math.max(0, Math.min(1, (centers[index] - PORT_SAFE_INSET) / usableLength));
          updated.set(item.port.id, { ...item.port, side, offset });
        });
      });
      return {
        ...node,
        ports: node.ports.map((port) => updated.get(port.id) ?? port),
      };
    }),
  };
}

function portPosition(topology: NetworkTopology, node: TopologyNode, port: TopologyPort) {
  const side = port.side;
  if (side === "top" || side === "bottom") {
    return {
      side,
      x: node.x + portLeft(node, port),
      y: side === "top" ? node.y : node.y + nodeHeight(node),
    };
  }
  return {
    side,
    x: side === "left" ? node.x : node.x + nodeWidth(node),
    y: node.y + portTop(node, port),
  };
}

function edgeLaneOffset(topology: NetworkTopology, edge: TopologyEdge, _from: TopologyNode, _to: TopologyNode) {
  const endpoints = (candidate: TopologyEdge) => {
    const candidateFrom = topology.nodes.find((node) => node.id === candidate.source);
    const candidateTo = topology.nodes.find((node) => node.id === candidate.target);
    const candidateFromPort = candidateFrom?.ports.find((port) => port.id === candidate.sourcePort);
    const candidateToPort = candidateTo?.ports.find((port) => port.id === candidate.targetPort);
    if (!candidateFrom || !candidateTo || !candidateFromPort || !candidateToPort) return undefined;
    const start = portPosition(topology, candidateFrom, candidateFromPort);
    const end = portPosition(topology, candidateTo, candidateToPort);
    return start.x <= end.x ? { left: start, right: end } : { left: end, right: start };
  };
  const corridorKey = (candidate: TopologyEdge) => {
    const candidateFrom = topology.nodes.find((node) => node.id === candidate.source);
    const candidateTo = topology.nodes.find((node) => node.id === candidate.target);
    const candidateFromPort = candidateFrom?.ports.find((port) => port.id === candidate.sourcePort);
    const candidateToPort = candidateTo?.ports.find((port) => port.id === candidate.targetPort);
    if (!candidateFrom || !candidateTo || !candidateFromPort || !candidateToPort) return "";
    const start = portPosition(topology, candidateFrom, candidateFromPort);
    const end = portPosition(topology, candidateTo, candidateToPort);
    const midX = Math.round(((start.x + end.x) / 2) / 80);
    const minColumn = Math.round(Math.min(candidateFrom.x, candidateTo.x) / 120);
    const maxColumn = Math.round(Math.max(candidateFrom.x, candidateTo.x) / 120);
    return `${candidate.bus}:${start.side}-${end.side}:${midX}:${minColumn}-${maxColumn}`;
  };
  const key = corridorKey(edge);
  const peers = topology.edges
    .filter((candidate) => corridorKey(candidate) === key)
    .sort((left, right) => {
      const leftEndpoints = endpoints(left);
      const rightEndpoints = endpoints(right);
      return (leftEndpoints?.left.y ?? 0) - (rightEndpoints?.left.y ?? 0)
        || (leftEndpoints?.right.y ?? 0) - (rightEndpoints?.right.y ?? 0)
        || left.id.localeCompare(right.id);
    });
  const index = peers.findIndex((candidate) => candidate.id === edge.id);
  const centeredIndex = index < 0 ? 0 : index - (peers.length - 1) / 2;
  return centeredIndex * EDGE_LANE_GAP;
}

type WirePoint = { x: number; y: number };
type WireObstacle = { left: number; right: number; top: number; bottom: number };

function compactWirePoints(points: WirePoint[]) {
  const unique = points.filter((point, index) => index === 0 || point.x !== points[index - 1].x || point.y !== points[index - 1].y);
  return unique.filter((point, index) => {
    if (index === 0 || index === unique.length - 1) return true;
    const previous = unique[index - 1];
    const next = unique[index + 1];
    return !(previous.x === point.x && point.x === next.x) && !(previous.y === point.y && point.y === next.y);
  });
}

function segmentHitsObstacle(start: WirePoint, end: WirePoint, obstacle: WireObstacle) {
  if (start.x === end.x) {
    return start.x > obstacle.left && start.x < obstacle.right
      && Math.max(start.y, end.y) > obstacle.top
      && Math.min(start.y, end.y) < obstacle.bottom;
  }
  if (start.y === end.y) {
    return start.y > obstacle.top && start.y < obstacle.bottom
      && Math.max(start.x, end.x) > obstacle.left
      && Math.min(start.x, end.x) < obstacle.right;
  }
  return true;
}

function wireRouteScore(points: WirePoint[], obstacles: WireObstacle[]) {
  const compact = compactWirePoints(points);
  let score = Math.max(0, compact.length - 2) * 22;
  for (let index = 1; index < compact.length; index += 1) {
    const start = compact[index - 1];
    const end = compact[index];
    score += Math.abs(end.x - start.x) + Math.abs(end.y - start.y);
    score += obstacles.filter((obstacle) => segmentHitsObstacle(start, end, obstacle)).length * 1_000_000;
  }
  return score;
}

function roundedWirePath(points: WirePoint[]) {
  const compact = compactWirePoints(points);
  if (compact.length < 2) return "";
  const commands = [`M ${compact[0].x} ${compact[0].y}`];
  for (let index = 1; index < compact.length - 1; index += 1) {
    const previous = compact[index - 1];
    const corner = compact[index];
    const next = compact[index + 1];
    const incoming = Math.abs(corner.x - previous.x) + Math.abs(corner.y - previous.y);
    const outgoing = Math.abs(next.x - corner.x) + Math.abs(next.y - corner.y);
    const radius = Math.min(10, incoming / 2, outgoing / 2);
    const before = {
      x: corner.x + Math.sign(previous.x - corner.x) * radius,
      y: corner.y + Math.sign(previous.y - corner.y) * radius,
    };
    const after = {
      x: corner.x + Math.sign(next.x - corner.x) * radius,
      y: corner.y + Math.sign(next.y - corner.y) * radius,
    };
    commands.push(`L ${before.x} ${before.y}`, `Q ${corner.x} ${corner.y} ${after.x} ${after.y}`);
  }
  const end = compact[compact.length - 1];
  commands.push(`L ${end.x} ${end.y}`);
  return commands.join(" ");
}

function largeTopologyEdgePath(
  topology: NetworkTopology,
  edge: TopologyEdge,
  from: TopologyNode,
  fromPort: TopologyPort,
  to: TopologyNode,
  toPort: TopologyPort,
) {
  const start = portPosition(topology, from, fromPort);
  const end = portPosition(topology, to, toPort);
  const startSide = start.side;
  const endSide = end.side;
  const usesHorizontalEdges = [startSide, endSide].every((side) => side === "top" || side === "bottom");
  if (usesHorizontalEdges) {
    const laneY = (start.y + end.y) / 2;
    return roundedWirePath([start, { x: start.x, y: laneY }, { x: end.x, y: laneY }, end]);
  }
  const laneOffset = edgeLaneOffset(topology, edge, from, to);
  const laneX = startSide === endSide
    ? startSide === "right"
      ? Math.max(from.x + nodeWidth(from), to.x + nodeWidth(to)) + 34 + Math.abs(laneOffset)
      : Math.min(from.x, to.x) - 34 - Math.abs(laneOffset)
    : (start.x + end.x) / 2 + laneOffset;
  return roundedWirePath([start, { x: laneX, y: start.y }, { x: laneX, y: end.y }, end]);
}

function routedEdgePath(topology: NetworkTopology, edge: TopologyEdge, from: TopologyNode, fromPort: TopologyPort, to: TopologyNode, toPort: TopologyPort) {
  if (
    topology.nodes.length >= LARGE_TOPOLOGY_NODE_THRESHOLD ||
    topology.edges.length >= LARGE_TOPOLOGY_EDGE_THRESHOLD
  ) {
    return largeTopologyEdgePath(topology, edge, from, fromPort, to, toPort);
  }
  const start = portPosition(topology, from, fromPort);
  const end = portPosition(topology, to, toPort);
  const usesHorizontalEdges = [start.side, end.side].every((side) => side === "top" || side === "bottom");
  if (usesHorizontalEdges) {
    const laneY = (start.y + end.y) / 2;
    return roundedWirePath([start, { x: start.x, y: laneY }, { x: end.x, y: laneY }, end]);
  }
  const startDirection = start.side === "right" ? 1 : -1;
  const endDirection = end.side === "right" ? 1 : -1;
  const clearance = 34;
  const obstacleMargin = 18;
  const portClearance = Math.min(clearance, Math.max(16, Math.abs(end.x - start.x) / 3));
  const laneOffset = edgeLaneOffset(topology, edge, from, to);
  const defaultLaneX = start.side === end.side
    ? start.side === "right"
      ? Math.max(from.x + nodeWidth(from), to.x + nodeWidth(to)) + clearance + Math.abs(laneOffset)
      : Math.min(from.x, to.x) - clearance - Math.abs(laneOffset)
    : (start.x + end.x) / 2 + laneOffset;
  const obstacles = topology.nodes
    .filter((node) => node.id !== from.id && node.id !== to.id)
    .map((node) => ({
      left: node.x - obstacleMargin,
      right: node.x + nodeWidth(node) + obstacleMargin,
      top: node.y - obstacleMargin,
      bottom: node.y + nodeHeight(node) + obstacleMargin,
    }));
  const candidates: WirePoint[][] = [];
  const laneXs = new Set<number>([defaultLaneX]);
  obstacles.forEach((obstacle) => {
    laneXs.add(obstacle.left - clearance + laneOffset);
    laneXs.add(obstacle.right + clearance + laneOffset);
  });
  laneXs.forEach((x) => {
    const leavesStartOutward = (x - start.x) * startDirection >= portClearance;
    const reachesEndOutward = (x - end.x) * endDirection >= portClearance;
    if (leavesStartOutward && reachesEndOutward) {
      candidates.push([start, { x, y: start.y }, { x, y: end.y }, end]);
    }
  });

  const startStubX = start.x + startDirection * Math.max(20, clearance + laneOffset);
  const endStubX = end.x + endDirection * Math.max(20, clearance - laneOffset);
  const nodeTops = topology.nodes.map((node) => node.y);
  const nodeBottoms = topology.nodes.map((node) => node.y + nodeHeight(node));
  const laneYs = new Set<number>([
    Math.max(CANVAS_MARGIN / 2, Math.min(...nodeTops) - clearance + laneOffset),
    Math.max(...nodeBottoms) + clearance + laneOffset,
  ]);
  obstacles.forEach((obstacle) => {
    laneYs.add(Math.max(CANVAS_MARGIN / 2, obstacle.top - clearance + laneOffset));
    laneYs.add(obstacle.bottom + clearance + laneOffset);
  });
  laneYs.forEach((y) => candidates.push([
    start,
    { x: startStubX, y: start.y },
    { x: startStubX, y },
    { x: endStubX, y },
    { x: endStubX, y: end.y },
    end,
  ]));

  const best = candidates.sort((left, right) => wireRouteScore(left, obstacles) - wireRouteScore(right, obstacles))[0];
  return roundedWirePath(best);
}

function pendingEdgePath(topology: NetworkTopology, from: TopologyNode, fromPort: TopologyPort, to: { x: number; y: number }) {
  const start = portPosition(topology, from, fromPort);
  if (start.side === "top" || start.side === "bottom") {
    const startDirection = start.side === "bottom" ? 1 : -1;
    const startStubY = start.y + startDirection * 28;
    const laneY = (startStubY + to.y) / 2;
    return roundedWirePath([
      start,
      { x: start.x, y: startStubY },
      { x: start.x, y: laneY },
      { x: to.x, y: laneY },
      to,
    ]);
  }
  const startDirection = start.side === "right" ? 1 : -1;
  const laneX = (start.x + to.x) / 2;
  const startStubX = start.x + startDirection * 28;
  return [
    `M ${start.x} ${start.y}`,
    `L ${startStubX} ${start.y}`,
    `L ${laneX} ${start.y}`,
    `L ${laneX} ${to.y}`,
    `L ${to.x} ${to.y}`,
  ].join(" ");
}

function nodeDegree(topology: NetworkTopology, nodeId: string) {
  return topology.edges.filter((edge) => edge.source === nodeId || edge.target === nodeId).length;
}

type EvaRole = "input" | "processing" | "output";

function evaRole(node: TopologyNode): EvaRole {
  if (node.kind === "sensor") return "input";
  if (node.kind === "actuator") return "output";
  return "processing";
}

function primaryGatewayFor(topology: NetworkTopology) {
  return [...topology.nodes]
    .filter((node) => node.kind === "gateway")
    .sort((left, right) =>
      nodeDegree(topology, right.id) - nodeDegree(topology, left.id) ||
      left.name.localeCompare(right.name, "de") ||
      left.id.localeCompare(right.id),
    )[0];
}

function stableTopologyOrder(topology: NetworkTopology, nodes: TopologyNode[]) {
  const nodesById = new Map(topology.nodes.map((node) => [node.id, node]));
  const neighbors = new Map(topology.nodes.map((node) => [node.id, [] as TopologyNode[]]));
  topology.edges.forEach((edge) => {
    const source = nodesById.get(edge.source);
    const target = nodesById.get(edge.target);
    if (source && target) {
      neighbors.get(source.id)?.push(target);
      neighbors.get(target.id)?.push(source);
    }
  });
  const sortKeys = new Map(nodes.map((node) => [
    node.id,
    (neighbors.get(node.id) ?? [])
      .map((neighbor) => `${evaRole(neighbor)}:${neighbor.name}:${neighbor.id}`)
      .sort()
      .join("|"),
  ]));
  const degrees = new Map(nodes.map((node) => [node.id, neighbors.get(node.id)?.length ?? 0]));
  return [...nodes].sort((left, right) =>
    (sortKeys.get(left.id) ?? "").localeCompare(sortKeys.get(right.id) ?? "", "de") ||
    (degrees.get(right.id) ?? 0) - (degrees.get(left.id) ?? 0) ||
    left.name.localeCompare(right.name, "de") ||
    left.id.localeCompare(right.id),
  );
}

type EvaGroup = {
  anchor: TopologyNode;
  inputs: TopologyNode[];
  outputs: TopologyNode[];
};

function topologyAdjacency(topology: NetworkTopology) {
  const adjacency = new Map<string, Set<string>>();
  topology.nodes.forEach((node) => adjacency.set(node.id, new Set()));
  topology.edges.forEach((edge) => {
    adjacency.get(edge.source)?.add(edge.target);
    adjacency.get(edge.target)?.add(edge.source);
  });
  return adjacency;
}

function graphDistances(adjacency: Map<string, Set<string>>, sourceId: string) {
  const visited = new Set([sourceId]);
  const distances = new Map([[sourceId, 0]]);
  let frontier = [sourceId];
  let distance = 0;
  while (frontier.length > 0) {
    distance += 1;
    const next: string[] = [];
    for (const nodeId of frontier) {
      for (const neighborId of adjacency.get(nodeId) ?? []) {
        if (visited.has(neighborId)) continue;
        visited.add(neighborId);
        distances.set(neighborId, distance);
        next.push(neighborId);
      }
    }
    frontier = next;
  }
  return distances;
}

const inactiveEvaRouteStatuses = new Set(["REJECTED", "OUTDATED", "SUPERSEDED", "DEPRECATED"]);

function routeAnchorForEndpoint(
  endpoint: TopologyNode,
  anchors: TopologyNode[],
  routingEntries: RoutingEntry[],
) {
  if (endpoint.systemOwnerId) {
    const explicitOwner = anchors.find(
      (anchor) => anchor.id === endpoint.systemOwnerId || anchor.engineeringId === endpoint.systemOwnerId,
    );
    if (explicitOwner) return explicitOwner;
  }
  if (!endpoint.engineeringId) return undefined;
  const anchorsByEngineeringId = new Map(
    anchors
      .filter((anchor) => anchor.engineeringId)
      .map((anchor) => [anchor.engineeringId as string, anchor]),
  );
  const candidates = routingEntries
    .filter((route) =>
      !inactiveEvaRouteStatuses.has(route.status.toUpperCase())
      && route.approval_state.toUpperCase() === "APPROVED"
      && route.validation?.valid === true
    )
    .flatMap((route) => {
      const anchorIds: string[] = [];
      if (route.source.node_id === endpoint.engineeringId) {
        anchorIds.push(...route.destinations.map((destination) => destination.node_id));
      }
      if (route.destinations.some((destination) => destination.node_id === endpoint.engineeringId)) {
        anchorIds.push(route.source.node_id);
      }
      return anchorIds.flatMap((anchorId) => {
        const anchor = anchorsByEngineeringId.get(anchorId);
        return anchor ? [{ anchor, route }] : [];
      });
    });

  return candidates.sort((left, right) =>
    Number(right.route.approval_state === "APPROVED") - Number(left.route.approval_state === "APPROVED") ||
    Number(right.route.validation?.valid === true) - Number(left.route.validation?.valid === true) ||
    Date.parse(right.route.modified_at) - Date.parse(left.route.modified_at) ||
    Number(left.anchor.kind === "gateway") - Number(right.anchor.kind === "gateway") ||
    left.anchor.name.localeCompare(right.anchor.name, "de") ||
    left.route.id.localeCompare(right.route.id),
  )[0]?.anchor;
}

function buildEvaGroups(topology: NetworkTopology, routingEntries: RoutingEntry[]): EvaGroup[] {
  const anchors = stableTopologyOrder(
    topology,
    topology.nodes.filter((node) => node.kind === "ecu" || node.kind === "gateway"),
  );
  const ecuAnchors = anchors.filter((node) => node.kind === "ecu");
  const gatewayAnchors = anchors.filter((node) => node.kind === "gateway");
  const groups = new Map(anchors.map((anchor) => [anchor.id, { anchor, inputs: [], outputs: [] } as EvaGroup]));
  const adjacency = topologyAdjacency(topology);
  const endpoints = stableTopologyOrder(
    topology,
    topology.nodes.filter((node) => node.kind === "sensor" || node.kind === "actuator"),
  );

  endpoints.forEach((endpoint) => {
    const routedAnchor = routeAnchorForEndpoint(endpoint, anchors, routingEntries);
    const distances = graphDistances(adjacency, endpoint.id);
    const reachableEcus = ecuAnchors
      .map((anchor) => ({ anchor, distance: distances.get(anchor.id) ?? Number.POSITIVE_INFINITY }))
      .filter((candidate) => Number.isFinite(candidate.distance));
    const candidates = reachableEcus.length > 0
      ? reachableEcus
      : gatewayAnchors
          .map((anchor) => ({ anchor, distance: distances.get(anchor.id) ?? Number.POSITIVE_INFINITY }))
          .filter((candidate) => Number.isFinite(candidate.distance));
    const selected = routedAnchor ?? candidates.sort((left, right) =>
      left.distance - right.distance ||
      nodeDegree(topology, right.anchor.id) - nodeDegree(topology, left.anchor.id) ||
      left.anchor.name.localeCompare(right.anchor.name, "de") ||
      left.anchor.id.localeCompare(right.anchor.id),
    )[0]?.anchor;
    if (!selected) return;
    const group = groups.get(selected.id);
    if (!group) return;
    if (endpoint.kind === "sensor") group.inputs.push(endpoint);
    else group.outputs.push(endpoint);
  });

  return anchors.map((anchor) => {
    const group = groups.get(anchor.id)!;
    return {
      ...group,
      inputs: stableTopologyOrder(topology, group.inputs),
      outputs: stableTopologyOrder(topology, group.outputs),
    };
  });
}

function nodeRowWidth(nodes: TopologyNode[]) {
  return nodes.reduce((total, node) => total + nodeWidth(node), 0) + Math.max(0, nodes.length - 1) * EVA_ROW_GAP;
}

function evaGroupWidth(group: EvaGroup) {
  return Math.max(nodeWidth(group.anchor), nodeRowWidth([...group.inputs, ...group.outputs]));
}

function evaClusterLayouts(
  topology: NetworkTopology,
  routingEntries: RoutingEntry[],
  groups = buildEvaGroups(topology, routingEntries),
) {
  return groups.flatMap((group) => {
    const members = [group.anchor, ...group.inputs, ...group.outputs];
    if (members.length < 2) return [];
    const left = Math.min(...members.map((node) => node.x));
    const top = Math.min(...members.map((node) => node.y));
    const right = Math.max(...members.map((node) => node.x + nodeWidth(node)));
    const bottom = Math.max(...members.map((node) => node.y + nodeHeight(node)));
    return [{
      id: group.anchor.id,
      memberIds: members.map((node) => node.id),
      label: `System ${group.anchor.name}`,
      count: members.length,
      inputs: group.inputs.length,
      outputs: group.outputs.length,
      kind: group.anchor.kind,
      left: Math.max(8, left - EVA_CLUSTER_PADDING),
      top: Math.max(EVA_LABEL_HEIGHT, top - EVA_CLUSTER_PADDING),
      width: right - left + EVA_CLUSTER_PADDING * 2,
      height: bottom - top + EVA_CLUSTER_PADDING * 2,
    }];
  });
}

function topologyStructureSignature(topology: NetworkTopology) {
  const nodes = topology.nodes
    .map((node) => `${node.id}:${node.kind}:${node.width ?? ""}:${node.height ?? ""}`)
    .sort()
    .join("|");
  const edges = topology.edges
    .map((edge) => `${edge.source}:${edge.target}:${edge.direction ?? "BIDIRECTIONAL"}`)
    .sort()
    .join("|");
  return `${nodes}::${edges}`;
}

function routingGroupSignature(routingEntries: RoutingEntry[]) {
  return routingEntries
    .filter((route) => !inactiveEvaRouteStatuses.has(route.status))
    .map((route) => [
      route.id,
      route.status,
      route.approval_state,
      route.validation?.valid ?? "",
      route.source.node_id,
      ...route.destinations.map((destination) => destination.node_id).sort(),
    ].join(":"))
    .sort()
    .join("|");
}

function topologyLayoutSignature(topology: NetworkTopology) {
  const nodes = topology.nodes
    .map((node) => [
      node.id,
      node.x,
      node.y,
      node.width ?? "",
      node.height ?? "",
      ...node.ports.map((port) => `${port.id}:${port.name}:${port.side}:${port.offset}`),
    ].join(":"))
    .sort()
    .join("|");
  const interfaces = topology.edges
    .map((edge) => `${edge.id}:${edge.sourceInterfaceName ?? ""}:${edge.targetInterfaceName ?? ""}`)
    .sort()
    .join("|");
  return `${nodes}::${interfaces}`;
}

function horizontalLayoutWidth(topology: NetworkTopology, surfaceWidth: number) {
  return Math.ceil(Math.max(
    1180,
    surfaceWidth,
    ...topology.nodes.map((node) => node.x + nodeWidth(node) + CANVAS_MARGIN),
  ));
}

function hasLayoutProblems(
  topology: NetworkTopology,
  surfaceWidth: number,
  routingEntries: RoutingEntry[],
  evaGroups = buildEvaGroups(topology, routingEntries),
) {
  const layoutWidth = horizontalLayoutWidth(topology, surfaceWidth);
  if (topology.nodes.some((node) =>
    node.x < CANVAS_MARGIN / 2 ||
    node.y < EVA_LABEL_HEIGHT ||
    node.x + nodeWidth(node) > layoutWidth
  )) return true;
  const primaryGateway = primaryGatewayFor(topology);
  if (primaryGateway) {
    const expectedTop = EVA_LABEL_HEIGHT + 24;
    if (Math.abs(primaryGateway.y - expectedTop) > 28) return true;
    if (nodeWidth(primaryGateway) < nodeHeight(primaryGateway) * 2) return true;
  }
  if (evaGroups.some((group) => {
    const members = [...group.inputs, ...group.outputs];
    if (members.length === 0) return false;
    const expectedHeight = endpointRowHeight(members);
    return members.some((node) =>
      node.y < group.anchor.y + nodeHeight(group.anchor) + 48 ||
      Math.abs(nodeWidth(node) - ENDPOINT_NODE_WIDTH) > 0.1 ||
      Math.abs(nodeHeight(node) - expectedHeight) > 0.1,
    );
  })) return true;
  const expectedGatewayNames = gatewayInterfaceNames(topology);
  if (topology.nodes.some((node) => node.kind === "gateway" && node.ports.some((port) => {
    const expectedName = expectedGatewayNames.get(`${node.id}\u0000${port.id}`);
    return expectedName != null && port.name !== expectedName;
  }))) return true;
  if (topology.nodes.some((node) => node.ports.some((port) => {
    if (connectedNodesForPort(topology, node, port).length === 0) return false;
    return port.side !== schemaPortSide(topology, node, port);
  }))) return true;
  if (topology.nodes.some((node) => (["top", "bottom", "left", "right"] as const).some((side) => {
    const axisLength = side === "top" || side === "bottom" ? nodeWidth(node) : nodeHeight(node);
    const coordinates = node.ports
      .filter((port) => port.side === side && connectedNodesForPort(topology, node, port).length > 0)
      .map((port) => PORT_SAFE_INSET + (port.offset ?? 0.5) * (axisLength - PORT_SAFE_INSET * 2))
      .sort((left, right) => left - right);
    return coordinates.some((coordinate, index) => index > 0 && coordinate - coordinates[index - 1] < PORT_CENTER_GAP - 0.1);
  }))) return true;
  return topology.nodes.some((node, index) =>
    topology.nodes.slice(index + 1).some((other) => {
      const separated =
        node.x + nodeWidth(node) + 26 < other.x ||
        other.x + nodeWidth(other) + 26 < node.x ||
        node.y + nodeHeight(node) + 24 < other.y ||
        other.y + nodeHeight(other) + 24 < node.y;
      return !separated;
    }),
  );
}

function arrangeTopology(
  topology: NetworkTopology,
  surfaceWidth: number,
  routingEntries: RoutingEntry[],
): NetworkTopology {
  const sizedTopology = sizeNodesForPorts(topology);
  const primaryGateway = primaryGatewayFor(sizedTopology);
  const groups = buildEvaGroups(sizedTopology, routingEntries);
  const primaryGroup = groups.find((group) => group.anchor.id === primaryGateway?.id);
  const branchGroups = groups.filter((group) => group.anchor.id !== primaryGateway?.id);
  const contentTop = EVA_LABEL_HEIGHT + 24;
  const gatewayHeight = primaryGateway ? nodeHeight(primaryGateway) : 0;
  const processingTop = primaryGateway ? contentTop + gatewayHeight + 112 : contentTop;
  const arranged = new Map<string, TopologyNode>();
  const groupedIds = new Set(groups.flatMap((group) => [
    group.anchor.id,
    ...group.inputs.map((node) => node.id),
    ...group.outputs.map((node) => node.id),
  ]));
  const primaryEndpoints = primaryGroup
    ? stableTopologyOrder(sizedTopology, [...primaryGroup.inputs, ...primaryGroup.outputs])
    : [];
  const orphanEndpoints = stableTopologyOrder(
    sizedTopology,
    sizedTopology.nodes.filter((node) =>
      (node.kind === "sensor" || node.kind === "actuator") && !groupedIds.has(node.id),
    ),
  );
  const directNodes = [...primaryEndpoints, ...orphanEndpoints];
  const directEndpointHeight = endpointRowHeight(directNodes);
  const units = [
    ...branchGroups.map((group) => ({ group, node: undefined as TopologyNode | undefined, width: evaGroupWidth(group) })),
    ...directNodes.map((node) => ({ group: undefined as EvaGroup | undefined, node, width: nodeWidth(node) })),
  ];
  const unitGap = EVA_CLUSTER_GAP;
  const totalUnitWidth = units.reduce((total, unit) => total + unit.width, 0) + Math.max(0, units.length - 1) * unitGap;
  const minimumSpan = Math.max(1180, surfaceWidth || 0) - CANVAS_MARGIN * 2;
  const layoutSpan = Math.max(totalUnitWidth, minimumSpan);
  const processingHeight = Math.max(
    NODE_MIN_HEIGHT,
    ...branchGroups.map((group) => nodeHeight(group.anchor)),
    ...directNodes.map(() => directEndpointHeight),
  );
  const endpointTop = processingTop + processingHeight + 112;
  let cursorX = CANVAS_MARGIN + Math.max(0, (layoutSpan - totalUnitWidth) / 2);

  units.forEach((unit) => {
    const centerX = cursorX + unit.width / 2;
    if (unit.group) {
      const anchor = { ...unit.group.anchor, width: unit.width };
      arranged.set(anchor.id, {
        ...anchor,
        x: Math.round(centerX - unit.width / 2),
        y: processingTop,
      });
      const endpoints = stableTopologyOrder(sizedTopology, [...unit.group.inputs, ...unit.group.outputs]);
      const groupEndpointHeight = endpointRowHeight(endpoints);
      const rowWidth = nodeRowWidth(endpoints);
      let endpointX = centerX - rowWidth / 2;
      endpoints.forEach((node) => {
        arranged.set(node.id, {
          ...node,
          x: Math.round(endpointX),
          y: endpointTop,
          width: ENDPOINT_NODE_WIDTH,
          height: groupEndpointHeight,
        });
        endpointX += nodeWidth(node) + EVA_ROW_GAP;
      });
    } else if (unit.node) {
      arranged.set(unit.node.id, {
        ...unit.node,
        x: Math.round(centerX - nodeWidth(unit.node) / 2),
        y: processingTop,
        width: ENDPOINT_NODE_WIDTH,
        height: directEndpointHeight,
      });
    }
    cursorX += unit.width + unitGap;
  });

  if (primaryGateway) {
    arranged.set(primaryGateway.id, {
      ...primaryGateway,
      x: CANVAS_MARGIN,
      y: contentTop,
      width: layoutSpan,
    });
  }

  return nameGatewayInterfaces(orderPortsByConnectedNodes({
    ...sizedTopology,
    nodes: sizedTopology.nodes.map((node) => arranged.get(node.id) ?? node),
  }));
}

export function NetworkEditor({
  topology,
  modelHardware,
  routingEntries,
  onChange,
  onRelationshipsChange,
}: {
  topology: NetworkTopology;
  modelHardware: HardwareNode[];
  routingEntries: RoutingEntry[];
  onChange: (next: NetworkTopology) => void;
  onRelationshipsChange?: (next: NetworkTopology) => void | boolean | Promise<void | boolean>;
}) {
  const surfaceRef = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<DragState | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);
  const [menu, setMenu] = useState<MenuState | null>(null);
  const [addMenu, setAddMenu] = useState<NodeKind | null>(null);
  const [rename, setRename] = useState<{ nodeId: string; name: string } | null>(null);
  const [relationship, setRelationship] = useState<RelationshipDraft | null>(null);
  const [relationshipSaving, setRelationshipSaving] = useState(false);
  const [relationshipError, setRelationshipError] = useState("");
  const [surfaceWidth, setSurfaceWidth] = useState(0);
  const [zoom, setZoom] = useState(1);
  const arrangedStructureRef = useRef("");

  useEffect(() => {
    const node = topology.nodes.find((item) => item.id === selectedNode);
    const edge = topology.edges.find((item) => item.id === selectedEdge);
    void setWorkflowContext({
      selected_object: node ? { id: node.id, type: "NetworkNode", name: node.name } : null,
      selected_network: edge?.bus ?? node?.ports[0]?.bus ?? null,
    }).catch(() => undefined);
  }, [selectedEdge, selectedNode, topology.edges, topology.nodes]);

  const pointFromEvent = useCallback((event: { clientX: number; clientY: number }) => {
    const rect = surfaceRef.current?.getBoundingClientRect();
    const surface = surfaceRef.current;
    return {
      x: (event.clientX - (rect?.left ?? 0) + (surface?.scrollLeft ?? 0)) / zoom,
      y: (event.clientY - (rect?.top ?? 0) + (surface?.scrollTop ?? 0)) / zoom,
    };
  }, [zoom]);

  useEffect(() => {
    const surface = surfaceRef.current;
    if (!surface) return;
    const update = () => setSurfaceWidth(surface.clientWidth);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(surface);
    return () => observer.disconnect();
  }, []);

  const findPort = useCallback(
    (nodeId: string, portId: string) => {
      const node = topology.nodes.find((n) => n.id === nodeId);
      return node?.ports.find((p) => p.id === portId);
    },
    [topology.nodes],
  );

  const commitRelationships = useCallback(
    (next: NetworkTopology) => {
      onChange(next);
      onRelationshipsChange?.(next);
    },
    [onChange, onRelationshipsChange],
  );

  useEffect(() => {
    if (!drag) return;
    const activeDrag = drag;
    function move(event: PointerEvent) {
      const point = pointFromEvent(event);
      if (activeDrag.mode === "move-cluster") {
        const minimumX = Math.min(...activeDrag.members.map((member) => member.x));
        const minimumY = Math.min(...activeDrag.members.map((member) => member.y));
        const deltaX = Math.max(
          point.x - activeDrag.startX,
          8 + EVA_CLUSTER_PADDING - minimumX,
        );
        const deltaY = Math.max(
          point.y - activeDrag.startY,
          EVA_LABEL_HEIGHT + EVA_CLUSTER_PADDING - minimumY,
        );
        const startPositions = new Map(activeDrag.members.map((member) => [member.id, member]));
        onChange({
          ...topology,
          nodes: topology.nodes.map((node) => {
            const start = startPositions.get(node.id);
            return start ? { ...node, x: start.x + deltaX, y: start.y + deltaY } : node;
          }),
        });
      } else if (activeDrag.mode === "move") {
        const node = topology.nodes.find((item) => item.id === activeDrag.nodeId);
        if (!node) return;
        onChange(normalizePortSides({
          ...topology,
          nodes: topology.nodes.map((node) =>
            node.id === activeDrag.nodeId
              ? { ...node, x: Math.max(CANVAS_MARGIN, point.x - activeDrag.offsetX), y: Math.max(CANVAS_MARGIN, point.y - activeDrag.offsetY) }
              : node,
          ),
        }));
      } else if (activeDrag.mode === "resize") {
        const node = topology.nodes.find((item) => item.id === activeDrag.nodeId);
        if (!node) return;
        const width = Math.max(NODE_MIN_WIDTH, activeDrag.startWidth + point.x - activeDrag.startX);
        const minimumHeight = nodeContentHeight({ ...node, width, height: undefined });
        const height = Math.max(
          minimumHeight,
          activeDrag.startHeight + point.y - activeDrag.startY,
        );
        onChange(normalizePortSides({
          ...topology,
          nodes: topology.nodes.map((item) =>
            item.id === node.id ? { ...item, width, height } : item,
          ),
        }));
      } else if (activeDrag.mode === "move-port") {
        const node = topology.nodes.find((item) => item.id === activeDrag.nodeId);
        if (!node) return;
        const { side, offset } = nearestPortPlacement(node, point);
        onChange({
          ...topology,
          nodes: topology.nodes.map((item) =>
            item.id === node.id
              ? { ...item, ports: item.ports.map((port) => port.id === activeDrag.portId ? { ...port, side, offset } : port) }
              : item,
          ),
        });
      } else {
        setDrag({ ...activeDrag, x: point.x, y: point.y });
      }
    }
    function up(event: PointerEvent) {
      if (activeDrag.mode === "wire") {
        const target = document
          .elementFromPoint(event.clientX, event.clientY)
          ?.closest<HTMLElement>("[data-port-id]");
        const targetNodeId = target?.getAttribute("data-node-id");
        const targetPortId = target?.getAttribute("data-port-id");
        const targetBus = target?.getAttribute("data-port-bus") as BusType | null;
        const validTarget =
          targetNodeId &&
          targetPortId &&
          targetNodeId !== activeDrag.nodeId &&
          targetBus === activeDrag.bus;
        if (validTarget) {
          const alreadyUsed = topology.edges.some(
            (edge) => edge.sourcePort === targetPortId || edge.targetPort === targetPortId || edge.sourcePort === activeDrag.portId || edge.targetPort === activeDrag.portId,
          );
          if (!alreadyUsed) {
            const sourceNode = topology.nodes.find((node) => node.id === activeDrag.nodeId);
            const targetNode = topology.nodes.find((node) => node.id === targetNodeId);
            setRelationshipError("");
            setRelationship({
              edge: {
                id: nextId("edge"),
                source: activeDrag.nodeId,
                sourcePort: activeDrag.portId,
                target: targetNodeId,
                targetPort: targetPortId,
                bus: activeDrag.bus,
              },
              isNew: true,
              name: `${sourceNode?.name ?? "Quelle"} ↔ ${targetNode?.name ?? "Ziel"}`,
              sourceInterfaceName: automaticInterfaceName(sourceNode?.name ?? "Quelle", activeDrag.bus),
              targetInterfaceName: automaticInterfaceName(targetNode?.name ?? "Ziel", activeDrag.bus),
              relationType: "CONNECTED_TO",
              description: "",
              direction: "BIDIRECTIONAL",
            });
          }
        }
      }
      setDrag(null);
    }
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  }, [commitRelationships, drag, topology, onChange, pointFromEvent]);

  useEffect(() => {
    if (!menu && !addMenu) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMenu(null);
        setAddMenu(null);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [addMenu, menu]);

  function addNode(kind: NodeKind, hardware?: HardwareNode) {
    const identityNodeId =
      typeof hardware?.identity?.topology_node_id === "string"
        ? hardware.identity.topology_node_id
        : null;
    const preferredId = identityNodeId ?? (hardware ? `engineering-${hardware.id}` : null);
    const extraIndex = topology.nodes.length;
    const node: TopologyNode = {
      id: preferredId && !topology.nodes.some((item) => item.id === preferredId)
        ? preferredId
        : nextId(kind),
      name: hardware?.name ?? `${kindLabels[kind]} ${topology.nodes.filter((item) => item.kind === kind).length + 1}`,
      kind,
      x: 60 + (extraIndex % 5) * 205,
      y: 460 + Math.floor(extraIndex / 5) * 120,
      ports: [],
      engineeringId: hardware?.id,
    };
    onChange({ ...topology, nodes: [...topology.nodes, node] });
    setSelectedNode(node.id);
    setAddMenu(null);
  }

  function addPort(nodeId: string, bus: BusType) {
    const position = menu;
    onChange({
      ...topology,
      nodes: topology.nodes.map((node) => {
        if (node.id !== nodeId) return node;
        return {
          ...node,
          ports: [...node.ports, {
            id: nextId("port"),
            name: busProfiles[bus].label,
            bus,
            side: position?.side ?? "right",
            offset: position?.offset ?? 0.5,
          }],
        };
      }),
    });
    setMenu(null);
  }

  function removePort(nodeId: string, portId: string) {
    const next = {
      nodes: topology.nodes.map((node) =>
        node.id === nodeId ? { ...node, ports: node.ports.filter((p) => p.id !== portId) } : node,
      ),
      edges: topology.edges.filter((edge) => edge.sourcePort !== portId && edge.targetPort !== portId),
    };
    if (next.edges.length !== topology.edges.length) commitRelationships(next);
    else onChange(next);
  }

  function removeSelected() {
    if (selectedEdge) {
      commitRelationships({ ...topology, edges: topology.edges.filter((edge) => edge.id !== selectedEdge) });
      setSelectedEdge(null);
      return;
    }
    if (selectedNode) {
      const next = {
        nodes: topology.nodes.filter((node) => node.id !== selectedNode),
        edges: topology.edges.filter((edge) => edge.source !== selectedNode && edge.target !== selectedNode),
      };
      if (next.edges.length !== topology.edges.length) commitRelationships(next);
      else onChange(next);
      setSelectedNode(null);
    }
  }

  function openRenameNode(id: string) {
    const current = topology.nodes.find((node) => node.id === id);
    if (current) setRename({ nodeId: id, name: current.name });
  }

  function saveRenamedNode() {
    if (!rename?.name.trim()) return;
    onChange({
      ...topology,
      nodes: topology.nodes.map((node) => (node.id === rename.nodeId ? { ...node, name: rename.name.trim() } : node)),
    });
    setRename(null);
  }

  async function saveRelationship() {
    if (!relationship?.name.trim() || !relationship.sourceInterfaceName.trim() || !relationship.targetInterfaceName.trim()) return;
    const sourceInterfaceName = relationship.sourceInterfaceName.trim();
    const targetInterfaceName = relationship.targetInterfaceName.trim();
    const edge: TopologyEdge = {
      ...relationship.edge,
      name: relationship.name.trim(),
      sourceInterfaceName,
      targetInterfaceName,
      relationType: relationship.relationType,
      description: relationship.description.trim() || undefined,
      direction: relationship.direction,
    };
    const edges = relationship.isNew
      ? [...topology.edges, edge]
      : topology.edges.map((item) => item.id === edge.id ? edge : item);
    const nodes = topology.nodes.map((node) => ({
      ...node,
      ports: node.ports.map((port) => {
        if (node.id === edge.source && port.id === edge.sourcePort) return { ...port, name: sourceInterfaceName };
        if (node.id === edge.target && port.id === edge.targetPort) return { ...port, name: targetInterfaceName };
        return port;
      }),
    }));
    const next = normalizePortSides({ ...topology, nodes, edges });
    setRelationshipSaving(true);
    setRelationshipError("");
    onChange(next);
    try {
      const persisted = await onRelationshipsChange?.(next);
      if (persisted === false) throw new Error("Die Engineering-Relation konnte nicht gespeichert werden.");
      setSelectedEdge(edge.id);
      setSelectedNode(null);
      setRelationship(null);
    } catch (error) {
      onChange(topology);
      setRelationshipError(error instanceof Error ? error.message : "Die Beziehung konnte nicht gespeichert werden.");
    } finally {
      setRelationshipSaving(false);
    }
  }

  function editRelationship(edge: TopologyEdge) {
    const from = topology.nodes.find((node) => node.id === edge.source);
    const to = topology.nodes.find((node) => node.id === edge.target);
    setRelationshipError("");
    setRelationship({
      edge,
      isNew: false,
      name: edge.name || `${from?.name ?? "Quelle"} ↔ ${to?.name ?? "Ziel"}`,
      sourceInterfaceName: relationshipInterfaceName(edge.sourceInterfaceName, from, edge.sourcePort, edge.bus),
      targetInterfaceName: relationshipInterfaceName(edge.targetInterfaceName, to, edge.targetPort, edge.bus),
      relationType: edge.relationType ?? "CONNECTED_TO",
      description: edge.description ?? "",
      direction: edge.direction ?? "BIDIRECTIONAL",
    });
  }

  const connectedPortIds = useMemo(() => new Set(
    topology.edges.flatMap((edge) => [edge.sourcePort, edge.targetPort]),
  ), [topology.edges]);
  const portIsConnected = (portId: string) => connectedPortIds.has(portId);
  const selectedRelationship = topology.edges.find((edge) => edge.id === selectedEdge);
  const selectedRelationshipRouteIds = new Set([
    ...(selectedRelationship?.routingEntryIds ?? []),
    ...(selectedRelationship?.routingEntryId ? [selectedRelationship.routingEntryId] : []),
  ]);
  const selectedRelationshipRoutes = routingEntries.filter((route) => selectedRelationshipRouteIds.has(route.id));
  const routingNodeNames = useMemo(
    () => new Map(modelHardware.map((node) => [node.id, node.name])),
    [modelHardware],
  );
  const primaryGatewayId = useMemo(() => primaryGatewayFor(topology)?.id, [topology]);
  const structureSignature = useMemo(
    () => `${topologyStructureSignature(topology)}::${routingGroupSignature(routingEntries)}`,
    [routingEntries, topology],
  );
  const evaGroups = useMemo(() => buildEvaGroups(topology, routingEntries), [routingEntries, topology]);
  const evaStable = useMemo(
    () => topology.nodes.length > 0 && surfaceWidth > 0 && !hasLayoutProblems(
      topology,
      surfaceWidth,
      routingEntries,
      evaGroups,
    ),
    [evaGroups, routingEntries, surfaceWidth, topology],
  );
  const evaClusters = useMemo(
    () => evaClusterLayouts(topology, routingEntries, evaGroups),
    [evaGroups, routingEntries, topology],
  );
  const renderedEdges = useMemo(() => {
    const nodesById = new Map(topology.nodes.map((node) => [node.id, node]));
    return topology.edges.flatMap((edge) => {
      const from = nodesById.get(edge.source);
      const to = nodesById.get(edge.target);
      const fromPort = from?.ports.find((port) => port.id === edge.sourcePort);
      const toPort = to?.ports.find((port) => port.id === edge.targetPort);
      if (!from || !to || !fromPort || !toPort) return [];
      return [{ edge, path: routedEdgePath(topology, edge, from, fromPort, to, toPort) }];
    });
  }, [topology]);
  const arrangeCurrentTopology = useCallback((persist: boolean) => {
    const next = arrangeTopology(topology, surfaceWidth, routingEntries);
    arrangedStructureRef.current = `${topologyStructureSignature(next)}::${routingGroupSignature(routingEntries)}`;
    if (persist && topologyLayoutSignature(next) !== topologyLayoutSignature(topology)) {
      commitRelationships(next);
    } else {
      onChange(next);
    }
  }, [commitRelationships, onChange, routingEntries, surfaceWidth, topology]);

  const applyAutoLayout = useCallback(() => {
    arrangeCurrentTopology(true);
  }, [arrangeCurrentTopology]);

  useEffect(() => {
    if (drag || surfaceWidth <= 0 || topology.nodes.length < 2) return;
    if (arrangedStructureRef.current === structureSignature) return;
    arrangedStructureRef.current = structureSignature;
    if (!evaStable) arrangeCurrentTopology(true);
  }, [arrangeCurrentTopology, drag, evaStable, structureSignature, surfaceWidth, topology.nodes.length]);

  const surfaceHeight = Math.max(
    620,
    ...topology.nodes.map((node) => node.y + nodeHeight(node) + CANVAS_EXTRA_SPACE),
  );
  const layoutGuideWidth = horizontalLayoutWidth(topology, surfaceWidth);
  const canvasWidth = Math.max(
    surfaceWidth + CANVAS_EXTRA_SPACE,
    layoutGuideWidth + CANVAS_EXTRA_SPACE,
    ...topology.nodes.map((node) => node.x + nodeWidth(node) + CANVAS_EXTRA_SPACE),
  );

  function changeZoom(value: number) {
    const nextZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Math.round(value * 10) / 10));
    const surface = surfaceRef.current;
    if (!surface || nextZoom === zoom) {
      setZoom(nextZoom);
      return;
    }
    const centerX = (surface.scrollLeft + surface.clientWidth / 2) / zoom;
    const centerY = (surface.scrollTop + surface.clientHeight / 2) / zoom;
    setZoom(nextZoom);
    requestAnimationFrame(() => {
      surface.scrollTo({
        left: Math.max(0, centerX * nextZoom - surface.clientWidth / 2),
        top: Math.max(0, centerY * nextZoom - surface.clientHeight / 2),
      });
    });
  }

  function fitCanvas() {
    const surface = surfaceRef.current;
    if (!surface) return;
    const nextZoom = Math.max(
      MIN_ZOOM,
      Math.min(1, (surface.clientWidth - 32) / canvasWidth, (surface.clientHeight - 32) / surfaceHeight),
    );
    setZoom(Math.round(nextZoom * 10) / 10);
    requestAnimationFrame(() => surface.scrollTo({ left: 0, top: 0 }));
  }

  const largeTopology = topology.nodes.length >= LARGE_TOPOLOGY_NODE_THRESHOLD;

  return (
    <div className={`net-editor ${largeTopology ? "large-topology" : ""}`}>
      <div className="net-toolbar">
        <div className="net-palette" role="group" aria-label="Geräte hinzufügen">
          {(Object.keys(kindLabels) as NodeKind[]).map((kind) => {
            const available = modelHardware.filter(
              (hardware) =>
                engineeringHardwareKind(hardware) === kind &&
                !topology.nodes.some((node) => node.engineeringId === hardware.id),
            );
            return (
              <div className="net-add-control" key={kind}>
                <button
                  aria-expanded={addMenu === kind}
                  aria-haspopup="menu"
                  className={`net-add ${addMenu === kind ? "active" : ""}`}
                  onClick={() => setAddMenu((current) => current === kind ? null : kind)}
                  type="button"
                >
                  + {kindLabels[kind]}
                </button>
                {addMenu === kind && (
                  <div className="net-add-menu" role="menu" aria-label={`${kindLabels[kind]} auswählen`}>
                    <button onClick={() => addNode(kind)} role="menuitem" type="button">
                      <strong>Neue {kindLabels[kind]}</strong>
                      <span>Ohne Modellzuordnung</span>
                    </button>
                    {available.map((hardware) => (
                      <button
                        key={hardware.id}
                        onClick={() => addNode(kind, hardware)}
                        role="menuitem"
                        type="button"
                      >
                        <strong>{hardware.name}</strong>
                        <span>{hardware.device_type}</span>
                      </button>
                    ))}
                    {available.length === 0 && <p>Keine weiteren Modellknoten</p>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <div className="net-toolbar-actions">
          <div aria-label="Zoom" className="net-zoom-controls" role="group">
            <button aria-label="Verkleinern" disabled={zoom <= MIN_ZOOM} onClick={() => changeZoom(zoom - ZOOM_STEP)} title="Verkleinern" type="button">−</button>
            <button aria-label="Zoom auf 100 Prozent zurücksetzen" className="net-zoom-value" onClick={() => changeZoom(1)} title="Zoom zurücksetzen" type="button">{Math.round(zoom * 100)} %</button>
            <button aria-label="Vergrößern" disabled={zoom >= MAX_ZOOM} onClick={() => changeZoom(zoom + ZOOM_STEP)} title="Vergrößern" type="button">+</button>
            <button className="net-zoom-fit" onClick={fitCanvas} title="Gesamtes Netzwerk einpassen" type="button">Einpassen</button>
          </div>
          <span className={`net-eva-status ${evaStable ? "stable" : "pending"}`} title="KI-gestützte EVA-Anordnung mit Verbindungsgruppen">
            <i aria-hidden="true" />
            KI-Layout · EVA
          </span>
          <button
            className="net-add danger"
            disabled={!selectedNode && !selectedEdge}
            onClick={removeSelected}
            type="button"
          >
            Auswahl löschen
          </button>
          <button
            className="net-add net-eva-action"
            disabled={topology.nodes.length < 2}
            onClick={applyAutoLayout}
            title="Zusammenhängende Geräte nach EVA sortieren und gruppieren"
            type="button"
          >
            EVA gruppieren
          </button>
        </div>
      </div>

      <div
        className="net-surface"
        onContextMenu={(event) => event.preventDefault()}
        onPointerDown={() => {
          setSelectedNode(null);
          setSelectedEdge(null);
          setMenu(null);
          setAddMenu(null);
        }}
        ref={surfaceRef}
      >
        <div
          className="net-canvas-viewport"
          style={{ height: Math.max(960, surfaceHeight * zoom), width: Math.max(surfaceWidth, canvasWidth * zoom) }}
        >
          <div className="net-canvas" style={{ height: surfaceHeight, transform: `scale(${zoom})`, width: canvasWidth }}>
          <div
            aria-hidden="true"
            className="net-eva-zones"
            style={{ width: layoutGuideWidth }}
          >
            <span>Gateway / BCM</span>
            <span>ECU</span>
            <span>Sensor / Aktor</span>
          </div>
          <div className="net-eva-clusters">
            {evaClusters.map((cluster) => (
              <div
                className={`net-eva-cluster ${cluster.kind} ${drag?.mode === "move-cluster" && drag.clusterId === cluster.id ? "dragging" : ""}`}
                key={cluster.id}
                style={{
                  height: cluster.height,
                  left: cluster.left,
                  top: cluster.top,
                  width: cluster.width,
                }}
              >
                <button
                  aria-label={`${cluster.label} verschieben`}
                  className="net-eva-cluster-handle"
                  onPointerDown={(event) => {
                    if (event.button !== 0) return;
                    event.preventDefault();
                    event.stopPropagation();
                    const members = topology.nodes
                      .filter((node) => cluster.memberIds.includes(node.id))
                      .map((node) => ({ id: node.id, x: node.x, y: node.y }));
                    if (members.length === 0) return;
                    const point = pointFromEvent(event);
                    setSelectedNode(null);
                    setSelectedEdge(null);
                    setMenu(null);
                    setAddMenu(null);
                    setDrag({
                      mode: "move-cluster",
                      clusterId: cluster.id,
                      startX: point.x,
                      startY: point.y,
                      members,
                    });
                  }}
                  title="Systemrahmen verschieben"
                  type="button"
                >
                  {cluster.label} · {cluster.inputs} Eingang · 1 Verarbeitung · {cluster.outputs} Ausgang
                </button>
              </div>
            ))}
          </div>
          <svg aria-hidden="true" className="net-wires">
          {renderedEdges.map(({ edge, path }) => {
            return (
              <g
                key={edge.id}
                onDoubleClick={(event) => {
                  event.stopPropagation();
                  editRelationship(edge);
                }}
                onPointerDown={(event) => {
                  event.stopPropagation();
                  if (selectedEdge === edge.id) {
                    editRelationship(edge);
                    return;
                  }
                  setSelectedEdge(edge.id);
                  setSelectedNode(null);
                  setMenu(null);
                }}
              >
                <path className="net-wire-hit" d={path} />
                <path
                  className={`net-wire ${selectedEdge === edge.id ? "selected" : ""}`}
                  d={path}
                  stroke={busProfiles[edge.bus].color}
                />
              </g>
            );
          })}
          {drag?.mode === "wire" &&
            (() => {
              const from = topology.nodes.find((node) => node.id === drag.nodeId);
              const fromPort = from?.ports.find((p) => p.id === drag.portId);
              if (!from || !fromPort) return null;
              return (
                <path
                  className="net-wire pending"
                  d={pendingEdgePath(topology, from, fromPort, { x: drag.x, y: drag.y })}
                  stroke={busProfiles[drag.bus].color}
                />
              );
            })()}
          </svg>

          {topology.nodes.map((node) => {
          const height = nodeHeight(node);
          const visiblePorts = largeTopology && selectedNode !== node.id
            ? node.ports.filter((port) => connectedPortIds.has(port.id))
            : node.ports;
          return (
            <div
              className={`net-node ${node.kind} eva-${evaRole(node)} ${node.id === primaryGatewayId ? "eva-hub" : ""} ${selectedNode === node.id ? "selected" : ""}`}
              data-node-id={node.id}
              key={node.id}
              onContextMenu={(event) => {
                event.preventDefault();
                event.stopPropagation();
                setSelectedNode(node.id);
                setSelectedEdge(null);
                const point = pointFromEvent(event);
                const { side, offset } = nearestPortPlacement(node, point);
                setMenu({ nodeId: node.id, x: point.x, y: point.y, side, offset });
              }}
              onDoubleClick={() => openRenameNode(node.id)}
              onPointerDown={(event) => {
                if (event.button !== 0) return;
                event.stopPropagation();
                setSelectedNode(node.id);
                setSelectedEdge(null);
                setMenu(null);
                const point = pointFromEvent(event);
                setDrag({ mode: "move", nodeId: node.id, offsetX: point.x - node.x, offsetY: point.y - node.y });
              }}
              style={{ left: node.x, top: node.y, width: nodeWidth(node), height }}
            >
              <span className="net-node-kind">
                {kindLabels[node.kind]}{node.id === primaryGatewayId ? " · EVA-Zentrum" : ""}
              </span>
              {node.engineeringId && (
                <span
                  aria-label="Mit Engineering-Modell verknüpft"
                  className="net-node-model-link"
                  title="Mit Engineering-Modell verknüpft"
                />
              )}
              <strong className="net-node-name">{node.name}</strong>
              {node.ports.length === 0 && <span className="net-node-empty">Rechtsklick → Port anlegen</span>}
              {visiblePorts.map((port) => {
                const portSide = port.side;
                const compatible =
                  drag?.mode === "wire" && drag.bus === port.bus && drag.nodeId !== node.id && !portIsConnected(port.id);
                const sideLabel: Record<PortSide, string> = {
                  left: "links",
                  right: "rechts",
                  top: "oben",
                  bottom: "unten",
                };
                const portStyle = portSide === "top" || portSide === "bottom"
                  ? { [portSide]: -PORT_OFFSET, left: portLeft(node, port) }
                  : { [portSide]: -PORT_OFFSET, top: portTop(node, port) };
                return (
                  <button
                    aria-label={`${port.name}-Port ${sideLabel[portSide]}`}
                    className={`net-port ${portSide} ${compatible ? "compatible" : ""} ${portIsConnected(port.id) ? "linked" : ""} ${drag?.mode === "move-port" && drag.portId === port.id ? "dragging" : ""}`}
                    data-node-id={node.id}
                    data-port-bus={port.bus}
                    data-port-id={port.id}
                    key={port.id}
                    onContextMenu={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      removePort(node.id, port.id);
                    }}
                    onPointerDown={(event) => {
                      if (event.button !== 0) return;
                      event.stopPropagation();
                      setMenu(null);
                      const point = pointFromEvent(event);
                      setDrag(
                        event.shiftKey || portIsConnected(port.id)
                          ? { mode: "move-port", nodeId: node.id, portId: port.id }
                          : { mode: "wire", nodeId: node.id, portId: port.id, bus: port.bus, x: point.x, y: point.y },
                      );
                    }}
                    style={{
                      ...portStyle,
                      ["--bus" as string]: busProfiles[port.bus].color,
                    }}
                    title={
                      portIsConnected(port.id)
                        ? `${port.name} · Ziehen zum Verschieben · Rechtsklick zum Entfernen`
                        : `${port.name} · zu einem gleichfarbigen Port ziehen zum Verbinden · Shift + Ziehen zum Verschieben · Rechtsklick zum Entfernen`
                    }
                    type="button"
                  />
                );
              })}
              <button
                aria-label={`${node.name} Größe ändern`}
                className="net-node-resize"
                onPointerDown={(event) => {
                  if (event.button !== 0) return;
                  event.preventDefault();
                  event.stopPropagation();
                  const point = pointFromEvent(event);
                  setSelectedNode(node.id);
                  setSelectedEdge(null);
                  setMenu(null);
                  setDrag({
                    mode: "resize",
                    nodeId: node.id,
                    startX: point.x,
                    startY: point.y,
                    startWidth: nodeWidth(node),
                    startHeight: nodeHeight(node),
                  });
                }}
                title="Boxgröße ändern"
                type="button"
              />
            </div>
          );
          })}

          {menu &&
          (() => {
            const node = topology.nodes.find((n) => n.id === menu.nodeId);
            if (!node) return null;
            return (
              <div
                className="net-menu"
                onPointerDown={(event) => event.stopPropagation()}
                role="menu"
                style={{
                  left: Math.max(
                    MENU_EDGE_GAP,
                    Math.min(
                      menu.x,
                      canvasWidth - MENU_WIDTH - MENU_EDGE_GAP,
                    ),
                  ),
                  ...(menu.y > surfaceHeight / 2
                    ? { bottom: Math.max(MENU_EDGE_GAP, surfaceHeight - menu.y) }
                    : { top: Math.max(MENU_EDGE_GAP, menu.y) }),
                }}
              >
                <p className="net-menu-title">Port anlegen an „{node.name}"</p>
                {busOrder.map((bus) => (
                  <button
                    className="net-menu-item"
                    key={bus}
                    onClick={() => addPort(node.id, bus)}
                    role="menuitem"
                    style={{ ["--bus" as string]: busProfiles[bus].color }}
                    type="button"
                  >
                    <span className="net-bus-dot" /> {busProfiles[bus].label}
                  </button>
                ))}
              </div>
            );
          })()}
          </div>
        </div>
      </div>

      <p className="net-hint">
        Karte ziehen zum Verschieben · Doppelklick auf Gerät zum Umbenennen · Doppelklick auf Verbindung zum Bearbeiten · <strong>Port zu einem gleichfarbigen Port ziehen</strong> zum Verdrahten · Shift + Port ziehen zum Versetzen · Rechtsklick auf einen Block legt einen Port an der Klickposition an · Rechtsklick auf einen Port entfernt ihn.
      </p>
      {selectedRelationship && (
        <div className="net-relationship-summary">
          <div>
            <span>Beziehung</span>
            <strong>{selectedRelationship.name || `${selectedRelationship.source} ↔ ${selectedRelationship.target}`}</strong>
            <small>{selectedRelationship.relationType ?? "CONNECTED_TO"} · {selectedRelationship.direction ?? "BIDIRECTIONAL"} · {busProfiles[selectedRelationship.bus].label}</small>
          </div>
          {selectedRelationshipRoutes.length > 0 && (
            <div className="net-relationship-routes">
              {selectedRelationshipRoutes.map((route) => (
                <section key={route.id}>
                  <span>{route.route_code}</span>
                  <strong>{route.name}</strong>
                  <small>
                    {routingNodeNames.get(route.source.node_id) ?? route.source.node_id} → {route.destinations.map((destination) => routingNodeNames.get(destination.node_id) ?? destination.node_id).join(", ")}
                    {' · '}{(route.payload.message_ids?.length ?? (route.payload.message_id ? 1 : 0))} Message(s) · {route.payload.signal_ids.length} Signal(e)
                  </small>
                </section>
              ))}
            </div>
          )}
          <button className="button secondary" onClick={() => editRelationship(selectedRelationship)} type="button">
            Beziehung bearbeiten
          </button>
        </div>
      )}
      {rename && (
        <div className="net-rename-backdrop" role="presentation">
          <section
            aria-labelledby="net-rename-title"
            aria-modal="true"
            className="net-rename-dialog"
            role="dialog"
          >
            <header>
              <div>
                <p className="eyebrow">Netzwerk-Node</p>
                <h2 id="net-rename-title">Gerät umbenennen</h2>
              </div>
              <button aria-label="Dialog schließen" onClick={() => setRename(null)} type="button">×</button>
            </header>
            <label>
              <span>Name</span>
              <input
                autoFocus
                onChange={(event) => setRename({ ...rename, name: event.target.value })}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    saveRenamedNode();
                  }
                  if (event.key === "Escape") setRename(null);
                }}
                value={rename.name}
              />
            </label>
            <footer>
              <button className="button secondary" onClick={() => setRename(null)} type="button">Abbrechen</button>
              <button className="button primary" disabled={!rename.name.trim()} onClick={saveRenamedNode} type="button">Speichern</button>
            </footer>
          </section>
        </div>
      )}
      {relationship && (
        <div className="net-rename-backdrop" onPointerDown={(event) => event.target === event.currentTarget && setRelationship(null)} role="presentation">
          <section
            aria-labelledby="net-relationship-title"
            aria-modal="true"
            className="net-rename-dialog net-relationship-dialog"
            onPointerDown={(event) => event.stopPropagation()}
            role="dialog"
          >
            <header>
              <div>
                <p className="eyebrow">Netzwerk-Beziehung</p>
                <h2 id="net-relationship-title">Verbindung definieren</h2>
              </div>
              <button aria-label="Dialog schließen" disabled={relationshipSaving} onClick={() => setRelationship(null)} type="button">×</button>
            </header>
            <div className="net-relationship-endpoints">
              <div><span>Quelle</span><strong>{topology.nodes.find((node) => node.id === relationship.edge.source)?.name ?? relationship.edge.source}</strong><small>{topology.nodes.find((node) => node.id === relationship.edge.source)?.ports.find((port) => port.id === relationship.edge.sourcePort)?.name ?? relationship.edge.sourcePort}</small></div>
              <span aria-hidden="true">→</span>
              <div><span>Ziel</span><strong>{topology.nodes.find((node) => node.id === relationship.edge.target)?.name ?? relationship.edge.target}</strong><small>{topology.nodes.find((node) => node.id === relationship.edge.target)?.ports.find((port) => port.id === relationship.edge.targetPort)?.name ?? relationship.edge.targetPort}</small></div>
            </div>
            <div className="net-relationship-fields">
              <label className="full-width"><span>Name</span><input autoFocus onChange={(event) => setRelationship({ ...relationship, name: event.target.value })} value={relationship.name} /></label>
              <label><span>Beziehungstyp</span><select onChange={(event) => setRelationship({ ...relationship, relationType: event.target.value as RelationshipDraft["relationType"] })} value={relationship.relationType}><option value="CONNECTED_TO">Physisch verbunden · CONNECTED_TO</option><option value="COMMUNICATES_WITH">Kommuniziert mit · COMMUNICATES_WITH</option><option value="CONNECTED_VIA">Über Bus verbunden · CONNECTED_VIA</option></select></label>
              <label><span>Richtung</span><select onChange={(event) => setRelationship({ ...relationship, direction: event.target.value as RelationshipDraft["direction"] })} value={relationship.direction}><option value="BIDIRECTIONAL">Bidirektional</option><option value="SOURCE_TO_TARGET">Quelle → Ziel</option><option value="TARGET_TO_SOURCE">Ziel → Quelle</option></select></label>
              <label><span>Quell-Interface</span><input onChange={(event) => setRelationship({ ...relationship, sourceInterfaceName: event.target.value })} value={relationship.sourceInterfaceName} /></label>
              <label><span>Ziel-Interface</span><input onChange={(event) => setRelationship({ ...relationship, targetInterfaceName: event.target.value })} value={relationship.targetInterfaceName} /></label>
              <label><span>Bus</span><input readOnly value={busProfiles[relationship.edge.bus].label} /></label>
              <label className="full-width"><span>Beschreibung</span><textarea onChange={(event) => setRelationship({ ...relationship, description: event.target.value })} placeholder="Technischer Zweck, Randbedingungen oder Verantwortlichkeit" rows={3} value={relationship.description} /></label>
            </div>
            {relationshipError && <div className="notice error net-relationship-error">{relationshipError}</div>}
            <footer>
              <button className="button secondary" disabled={relationshipSaving} onClick={() => setRelationship(null)} type="button">Abbrechen</button>
              <button className="button primary" disabled={relationshipSaving || !relationship.name.trim() || !relationship.sourceInterfaceName.trim() || !relationship.targetInterfaceName.trim()} onClick={() => void saveRelationship()} type="button">{relationshipSaving ? "Wird gespeichert …" : "Beziehung übernehmen"}</button>
            </footer>
          </section>
        </div>
      )}
    </div>
  );
}
