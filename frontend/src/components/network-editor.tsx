"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { createPortal } from "react-dom";
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
import { busJunctions, moveSceneWire, previewNetworkScene, type SceneBranch, type SceneBus } from "@/lib/network-scene";
import { withWireCrossings } from '@/lib/network-crossings';
import { deleteNetworkSelection, type NetworkSelection } from '@/lib/network-deletion';
import { findConnectionTarget, planNetworkConnection, type ConnectionEndpoint } from '@/lib/network-connections';
import { networkLabel, branchPath } from "@/lib/network-names";
import { NetworkLasso } from './network-lasso';
import { NetworkAssignmentDialog } from './network-assignment-dialog';
import { NetworkFrameDeviceDialog } from './network-frame-device-dialog';
import { NetworkBusNameDialog } from './network-bus-name-dialog';
import { NetworkBusTransferDialog } from './network-bus-transfer-dialog';
import { NetworkEditorSearch } from './network-editor-search';
import { queueEngineeringAgentTask } from '@/lib/agent-task-events';
import { networkSearchEntries, type NetworkSearchEntry } from '@/lib/network-editor-search';
import type { NetworkAssignmentRequest, FrameDeviceRequest } from '@/lib/workflow-api';
import type { HardwareNode, RoutingEntry } from "@/lib/types";
import {
  getWorkflowTopologyLayout,
  previewBusChange,
  type BusChangePreview,
  type BusChangeRequest,
  saveWorkflowTopologyLayout,
  setWorkflowContext,
  type WorkflowTopologyLayout,
  type WorkflowTopologyLayoutNode,
} from "@/lib/workflow-api";
import { readActiveProjectId } from "@/lib/user-settings";
import {
  compareTopologyClusterKeys,
  inferTopologyClusterProfileFromText,
  recordTopologyClusterNeighborLesson,
  topologyClusterAffinity,
  topologyClusterFamilyForKey,
  topologyClusterForText,
  topologySystemIdentityForText,
} from "@/lib/topology-cluster-knowledge";

const NODE_DEFAULT_WIDTH = 168;
const NODE_MIN_WIDTH = 140;
const NODE_MIN_HEIGHT = 84;
const PORT_DIAMETER = 16;
const PORT_OFFSET = PORT_DIAMETER / 2;
const PORT_SAFE_INSET = 18;
const PORT_VISUAL_GAP = 7.5;
const PORT_CENTER_GAP = PORT_DIAMETER + PORT_VISUAL_GAP;
const EDGE_LANE_GAP = PORT_CENTER_GAP;
const ENDPOINT_NODE_WIDTH = 148;
const MENU_WIDTH = 210;
const MENU_EDGE_GAP = 8;
const CANVAS_MARGIN = 36;
const CANVAS_EXTRA_SPACE = 320;
const EVA_LABEL_HEIGHT = 72;
const EVA_ROW_GAP = 38;
const EVA_GATEWAY_TO_PROCESSING_GAP = 140;
const EVA_PROCESSING_TO_ENDPOINT_GAP = 108;
const EVA_CLUSTER_GAP = 240;
const EVA_CLUSTER_PADDING = 24;
const EVA_GATEWAY_MIN_WIDTH = 280;
const EVA_ENDPOINT_COLUMN_GAP = 44;
const EVA_ENDPOINT_ROW_GAP = 36;
const EVA_ENDPOINT_GRID_COLUMNS = 6;
const EVA_CLUSTER_ROW_GAP = 168;
const EVA_DOMAIN_CLUSTER_PADDING = 32;
const EVA_DOMAIN_CLUSTER_GAP = 180;
const EVA_SYSTEMS_PER_FAMILY_ROW = 3;
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 1.5;
const ZOOM_STEP = 0.1;
const WIRE_ALIGNMENT_DEFAULT_OFFSET = 0;
const WIRE_ALIGNMENT_STEP = 0.5;
const WIRE_ALIGNMENT_LIMIT = 12;
const WIRE_ALIGNMENT_OFFSET_STORAGE_KEY = "networkis:wire-alignment-offset-x:v2";
const LARGE_TOPOLOGY_NODE_THRESHOLD = 48;
const LARGE_TOPOLOGY_EDGE_THRESHOLD = 48;
const LARGE_TOPOLOGY_RENDER_BATCH = 48;
const LARGE_TOPOLOGY_VIEWPORT_OVERSCAN = 320;
const NETWORK_LAYOUT_VERSION = 21;
const NETWORK_LAYOUT_CACHE_PREFIX = `networkis:network-layout:v${NETWORK_LAYOUT_VERSION}:`;

const kindLabels: Record<NodeKind, string> = {
  ecu: "ECU",
  gateway: "Gateway",
  sensor: "Sensor",
  actuator: "Aktor",
};

function normalizeWireAlignmentOffset(value: number) {
  return Math.max(
    -WIRE_ALIGNMENT_LIMIT,
    Math.min(WIRE_ALIGNMENT_LIMIT, Math.round(value / WIRE_ALIGNMENT_STEP) * WIRE_ALIGNMENT_STEP),
  );
}

const busOrder: BusType[] = ["can", "can_fd", "can_xl", "lin", "automotive_ethernet", "flexray"];

type DragState =
  | { mode: "move-bus"; busId: string; portId?: string; startX: number; startY: number; coordinate: number; baseline: NetworkTopology }
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
  | { mode: "wire"; nodeId: string; portId: string; bus: BusType; x: number; y: number; startX: number; startY: number };

type MenuState = { nodeId: string; x: number; y: number; side: PortSide; offset: number };
type RelationshipDraft = {
  connection?: { source: ConnectionEndpoint; target: ConnectionEndpoint };
  edge: TopologyEdge;
  bus?: BusType;
  isNew: boolean;
  name: string;
  sourceInterfaceName: string;
  targetInterfaceName: string;
  relationType: NonNullable<TopologyEdge["relationType"]>;
  description: string;
  direction: NonNullable<TopologyEdge["direction"]>;
};
type CachedNetworkLayout = {
  createdAt: string;
  nodes: Record<string, {
    x: number;
    y: number;
    width?: number;
    height?: number;
    ports: Record<string, { side: PortSide; offset: number }>;
  }>;
};
type NetworkContextOverlay = {
  x: number;
  y: number;
  accent: string;
  title: string;
  subtitle: string;
  rows: Array<{ label: string; value: string }>;
  chips: string[];
};
type CanvasViewportBounds = {
  left: number;
  top: number;
  right: number;
  bottom: number;
};

function canvasRectangleIsVisible(
  rectangle: { left: number; top: number; width: number; height: number },
  bounds: CanvasViewportBounds,
) {
  return rectangle.left + rectangle.width >= bounds.left
    && rectangle.left <= bounds.right
    && rectangle.top + rectangle.height >= bounds.top
    && rectangle.top <= bounds.bottom;
}

let counter = 0;
const nextId = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${(counter++).toString(36)}`;

const interfaceNameSuffix: Record<BusType, string> = {
  can: "CAN", can_xl: "CAN_XL",
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

function uniqueLabels(values: Array<string | null | undefined>) {
  return [...new Set(values.map((value) => value?.trim()).filter(Boolean) as string[])];
}

function usesVerticalCardFormat(node: TopologyNode) {
  return node.kind === "sensor"
    || node.kind === "actuator"
    || (node.kind === "ecu" && (node.width ?? NODE_DEFAULT_WIDTH) <= ENDPOINT_NODE_WIDTH);
}

function nodeWidth(node: TopologyNode) {
  const minimumWidth = usesVerticalCardFormat(node)
    ? ENDPOINT_NODE_WIDTH
    : NODE_MIN_WIDTH;
  const defaultWidth = usesVerticalCardFormat(node)
    ? ENDPOINT_NODE_WIDTH
    : NODE_DEFAULT_WIDTH;
  return Math.max(minimumWidth, node.width ?? defaultWidth);
}

function nodeContentHeight(node: TopologyNode) {
  if (usesVerticalCardFormat(node)) return endpointNameHeight(node.name);
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
  return Math.max(NODE_MIN_HEIGHT, node.height ?? nodeContentHeight(node));
}

function endpointNameHeight(name: string) {
  const lines = Math.max(1, Math.ceil(name.length / 18));
  return Math.max(96, 66 + lines * 16);
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

function unusedPortPlacement(node: TopologyNode, preferred: { side: PortSide; offset: number }) {
  const point = (port: { side: PortSide; offset: number }) => {
    const horizontal = port.side === "top" || port.side === "bottom";
    const axis = horizontal ? nodeWidth(node) : nodeHeight(node);
    const along = PORT_SAFE_INSET + port.offset * (axis - 2 * PORT_SAFE_INSET);
    return horizontal
      ? { x: along, y: port.side === "top" ? 0 : nodeHeight(node) }
      : { x: port.side === "left" ? 0 : nodeWidth(node), y: along };
  };
  const desired = point(preferred);
  const candidates = [preferred];
  for (const side of ["left", "right", "top", "bottom"] as PortSide[]) {
    const axis = side === "top" || side === "bottom" ? nodeWidth(node) : nodeHeight(node);
    const intervals = Math.max(1, Math.floor((axis - 2 * PORT_SAFE_INSET) / PORT_CENTER_GAP));
    for (let i = 0; i <= intervals; i++) candidates.push({ side, offset: i / intervals });
  }
  const distance = (a: { x: number; y: number }, b: { x: number; y: number }) => Math.hypot(a.x - b.x, a.y - b.y);
  return candidates.sort((a, b) => distance(point(a), desired) - distance(point(b), desired))
    .find(candidate => node.ports.every(port => distance(point(candidate), point(port)) >= PORT_CENTER_GAP));
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
  can: "CAN", can_xl: "CAN-XL",
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
      if ((port.hardwareInterfaceId || port.engineeringId) && port.name.trim()) {
        names.set(`${gateway.id}\u0000${port.id}`, port.name);
        return;
      }
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

function primaryGatewayLayoutWidth(topology: NetworkTopology, node: TopologyNode, layoutSpan: number) {
  return Math.max(EVA_GATEWAY_MIN_WIDTH, layoutSpan);
}

function primaryGatewayManualSpan(topology: NetworkTopology, surfaceWidth: number, primaryGatewayId: string) {
  const primaryGateway = topology.nodes.find((node) => node.id === primaryGatewayId);
  return primaryGateway
    ? Math.max(nodeWidth(primaryGateway), surfaceWidth - CANVAS_MARGIN * 2, EVA_GATEWAY_MIN_WIDTH)
    : EVA_GATEWAY_MIN_WIDTH;
}

function viewportAlignedTopology(topology: NetworkTopology): NetworkTopology {
  if (topology.nodes.length === 0) return topology;
  const minimumX = Math.min(...topology.nodes.map((node) => node.x));
  const minimumY = Math.min(...topology.nodes.map((node) => node.y));
  const deltaX = Math.max(0, CANVAS_MARGIN - minimumX);
  const deltaY = Math.max(0, EVA_LABEL_HEIGHT + 8 - minimumY);
  if (deltaX === 0 && deltaY === 0) return topology;
  return {
    ...topology,
    nodes: topology.nodes.map((node) => ({
      ...node,
      x: node.x + deltaX,
      y: node.y + deltaY,
    })),
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

const edgeLaneOffsetCache = new WeakMap<NetworkTopology, Map<string, number>>();

function buildEdgeLaneOffsets(topology: NetworkTopology) {
  const nodesById = new Map(topology.nodes.map((node) => [node.id, node]));
  const portsByNodeId = new Map(topology.nodes.map((node) => [
    node.id,
    new Map(node.ports.map((port) => [port.id, port])),
  ]));
  const corridors = new Map<string, Array<{ edge: TopologyEdge; start: WirePoint; end: WirePoint }>>();

  topology.edges.forEach((edge) => {
    const from = nodesById.get(edge.source);
    const to = nodesById.get(edge.target);
    const fromPort = portsByNodeId.get(edge.source)?.get(edge.sourcePort);
    const toPort = portsByNodeId.get(edge.target)?.get(edge.targetPort);
    if (!from || !to || !fromPort || !toPort) return;
    const start = portPosition(topology, from, fromPort);
    const end = portPosition(topology, to, toPort);
    const minRow = Math.round(Math.min(start.y, end.y) / 96);
    const maxRow = Math.round(Math.max(start.y, end.y) / 96);
    const minColumn = Math.round(Math.min(from.x, to.x, start.x, end.x) / 560);
    const maxColumn = Math.round(Math.max(
      from.x + nodeWidth(from),
      to.x + nodeWidth(to),
      start.x,
      end.x,
    ) / 560);
    const key = `${edge.bus}:${start.side}-${end.side}:${minRow}-${maxRow}:${minColumn}-${maxColumn}`;
    corridors.set(key, [...(corridors.get(key) ?? []), { edge, start, end }]);
  });

  const offsets = new Map<string, number>();
  corridors.forEach((items) => {
    items.sort((left, right) => {
      const leftStart = left.start.x <= left.end.x ? left.start : left.end;
      const leftEnd = left.start.x <= left.end.x ? left.end : left.start;
      const rightStart = right.start.x <= right.end.x ? right.start : right.end;
      const rightEnd = right.start.x <= right.end.x ? right.end : right.start;
      return leftStart.y - rightStart.y
        || leftEnd.y - rightEnd.y
        || left.edge.id.localeCompare(right.edge.id);
    });
    items.forEach((item, index) => {
      offsets.set(item.edge.id, (index - (items.length - 1) / 2) * EDGE_LANE_GAP);
    });
  });
  return offsets;
}

function edgeLaneOffset(topology: NetworkTopology, edge: TopologyEdge, _from: TopologyNode, _to: TopologyNode) {
  let offsets = edgeLaneOffsetCache.get(topology);
  if (!offsets) {
    offsets = buildEdgeLaneOffsets(topology);
    edgeLaneOffsetCache.set(topology, offsets);
  }
  return offsets.get(edge.id) ?? 0;
}

type WirePoint = { x: number; y: number };
type WireObstacle = { left: number; right: number; top: number; bottom: number };
type WireBounds = { left: number; right: number; top: number; bottom: number };
type WireClusterLayout = {
  id: string;
  memberIds: string[];
  left: number;
  top: number;
  width: number;
  height: number;
};

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

function obstacleOverlapsBounds(obstacle: WireObstacle, bounds: WireBounds) {
  return obstacle.right >= bounds.left
    && obstacle.left <= bounds.right
    && obstacle.bottom >= bounds.top
    && obstacle.top <= bounds.bottom;
}

function nodeWireObstacles(topology: NetworkTopology, excludedNodeIds: Set<string>, margin = 18, bounds?: WireBounds) {
  return topology.nodes
    .filter((node) => !excludedNodeIds.has(node.id))
    .map((node) => ({
      left: node.x - margin,
      right: node.x + nodeWidth(node) + margin,
      top: node.y - margin,
      bottom: node.y + nodeHeight(node) + margin,
    }))
    .filter((obstacle) => !bounds || obstacleOverlapsBounds(obstacle, bounds));
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

function pointStub(point: WirePoint & { side?: PortSide }, distance: number) {
  if (point.side === "left") return { x: point.x - distance, y: point.y };
  if (point.side === "right") return { x: point.x + distance, y: point.y };
  if (point.side === "top") return { x: point.x, y: point.y - distance };
  return { x: point.x, y: point.y + distance };
}

function sharedBusLaneOffset(bus: BusType, availableGap: number) {
  const index = Math.max(0, busOrder.indexOf(bus));
  const centeredIndex = index - (busOrder.length - 1) / 2;
  return Math.max(-availableGap * 0.22, Math.min(availableGap * 0.22, centeredIndex * 18));
}

function clusterForNode(clusters: WireClusterLayout[], nodeId: string) {
  return clusters.find((cluster) => cluster.memberIds.includes(nodeId));
}

function clusterWireObstacle(cluster: WireClusterLayout, clearance = 20): WireObstacle {
  return {
    left: cluster.left - clearance,
    right: cluster.left + cluster.width + clearance,
    top: cluster.top - clearance,
    bottom: cluster.top + cluster.height + clearance,
  };
}

function localWireBounds(from: TopologyNode, to: TopologyNode, start: WirePoint, end: WirePoint, padding: number): WireBounds {
  return {
    left: Math.min(from.x, to.x, start.x, end.x) - padding,
    right: Math.max(from.x + nodeWidth(from), to.x + nodeWidth(to), start.x, end.x) + padding,
    top: Math.min(from.y, to.y, start.y, end.y) - padding,
    bottom: Math.max(from.y + nodeHeight(from), to.y + nodeHeight(to), start.y, end.y) + padding,
  };
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
  systemFrames: WireClusterLayout[] = [],
) {
  const start = portPosition(topology, from, fromPort);
  const end = portPosition(topology, to, toPort);
  const startSide = start.side;
  const endSide = end.side;
  const laneOffset = edgeLaneOffset(topology, edge, from, to);
  const primaryGateway = primaryGatewayFor(topology);
  const gatewayNode = from.id === primaryGateway?.id ? from : to.id === primaryGateway?.id ? to : undefined;
  const branchNode = gatewayNode?.id === from.id ? to : gatewayNode?.id === to.id ? from : undefined;
  const gatewayPoint = gatewayNode?.id === from.id ? start : gatewayNode?.id === to.id ? end : undefined;
  const branchPoint = branchNode?.id === from.id ? start : branchNode?.id === to.id ? end : undefined;
  const sourceFrame = clusterForNode(systemFrames, from.id);
  const targetFrame = clusterForNode(systemFrames, to.id);
  const branchFrame = branchNode ? clusterForNode(systemFrames, branchNode.id) : undefined;
  if (
    gatewayNode && branchNode && gatewayPoint && branchPoint
    && gatewayPoint.side === "bottom" && branchPoint.side === "top"
    && branchNode.y > gatewayNode.y + nodeHeight(gatewayNode)
  ) {
    const gatewayBottom = gatewayNode.y + nodeHeight(gatewayNode);
    const firstFrameTop = systemFrames.length > 0
      ? Math.min(...systemFrames.map((frame) => frame.top), branchFrame?.top ?? branchNode.y)
      : branchFrame?.top ?? branchNode.y;
    const gatewayGap = Math.max(48, firstFrameTop - gatewayBottom);
    const gatewayLane = gatewayBottom + gatewayGap / 2 + sharedBusLaneOffset(edge.bus, gatewayGap);
    const branchLane = branchFrame
      ? branchFrame.top - 42 + sharedBusLaneOffset(edge.bus, 84)
      : branchNode.y - 42;
    const excludedFrameIds = new Set(
      systemFrames
        .filter((frame) => branchNode && frame.memberIds.includes(branchNode.id))
        .map((frame) => frame.id),
    );
    const frameObstacles = systemFrames
      .filter((frame) => !excludedFrameIds.has(frame.id))
      .map((frame) => clusterWireObstacle(frame, 28));
    const corridorXs = new Set<number>([branchPoint.x]);
    if (branchFrame) {
      corridorXs.add(branchFrame.left - EVA_CLUSTER_GAP / 2);
      corridorXs.add(branchFrame.left + branchFrame.width + EVA_CLUSTER_GAP / 2);
    }
    systemFrames.forEach((frame) => {
      corridorXs.add(frame.left - EVA_CLUSTER_GAP / 2);
      corridorXs.add(frame.left + frame.width + EVA_CLUSTER_GAP / 2);
    });
    const candidates = [...corridorXs].map((corridorX) => [
      gatewayPoint,
      { x: gatewayPoint.x, y: gatewayLane },
      { x: corridorX, y: gatewayLane },
      { x: corridorX, y: branchLane },
      { x: branchPoint.x, y: branchLane },
      branchPoint,
    ]);
    const pathFromGateway = candidates.sort((left, right) => (
      wireRouteScore(left, frameObstacles) - wireRouteScore(right, frameObstacles)
    ))[0];
    return roundedWirePath(gatewayNode.id === from.id ? pathFromGateway : [...pathFromGateway].reverse());
  }
  const fromAbove = from.y + nodeHeight(from) <= to.y && startSide === "bottom" && endSide === "top";
  const toAbove = to.y + nodeHeight(to) <= from.y && endSide === "bottom" && startSide === "top";
  if ((fromAbove || toAbove) && sourceFrame?.id === targetFrame?.id) {
    const upperNode = fromAbove ? from : to;
    const lowerNode = fromAbove ? to : from;
    const upperPoint = fromAbove ? start : end;
    const lowerPoint = fromAbove ? end : start;
    const availableGap = lowerNode.y - (upperNode.y + nodeHeight(upperNode));
    const laneY = upperNode.y + nodeHeight(upperNode)
      + availableGap / 2
      + sharedBusLaneOffset(edge.bus, availableGap);
    const hierarchyPath = [
      upperPoint,
      { x: upperPoint.x, y: laneY },
      { x: lowerPoint.x, y: laneY },
      lowerPoint,
    ];
    return roundedWirePath(fromAbove ? hierarchyPath : [...hierarchyPath].reverse());
  }
  const outwardLaneOffset = Math.abs(laneOffset) + (laneOffset > 0 ? EDGE_LANE_GAP / 2 : 0);
  const clearance = 42 + Math.min(180, outwardLaneOffset);
  const startStub = pointStub(start, clearance);
  const endStub = pointStub(end, clearance);
  const bounds = localWireBounds(from, to, start, end, 190);
  const excludedFrameIds = new Set(
    systemFrames
      .filter((frame) => frame.memberIds.includes(from.id) || frame.memberIds.includes(to.id))
      .map((frame) => frame.id),
  );
  const obstacles = [
    ...nodeWireObstacles(topology, new Set([from.id, to.id]), 28, bounds),
    ...systemFrames
      .filter((frame) => !excludedFrameIds.has(frame.id))
      .map((frame) => clusterWireObstacle(frame, 28))
      .filter((obstacle) => obstacleOverlapsBounds(obstacle, bounds)),
  ];
  const fromBottom = from.y + nodeHeight(from);
  const toBottom = to.y + nodeHeight(to);
  const laneYs = new Set<number>([
    (startStub.y + endStub.y) / 2 + laneOffset,
    Math.min(from.y, to.y, start.y, end.y) - clearance + laneOffset,
    Math.max(fromBottom, toBottom, start.y, end.y) + clearance + laneOffset,
  ]);
  const laneXs = new Set<number>([
    (startStub.x + endStub.x) / 2 + laneOffset,
    Math.min(from.x, to.x, start.x, end.x) - clearance + laneOffset,
    Math.max(from.x + nodeWidth(from), to.x + nodeWidth(to), start.x, end.x) + clearance + laneOffset,
  ]);
  obstacles.forEach((obstacle) => {
    laneYs.add(obstacle.top - clearance + laneOffset);
    laneYs.add(obstacle.bottom + clearance + laneOffset);
    laneXs.add(obstacle.left - clearance + laneOffset);
    laneXs.add(obstacle.right + clearance + laneOffset);
  });
  const candidates: WirePoint[][] = [
    [start, startStub, { x: endStub.x, y: startStub.y }, endStub, end],
    [start, startStub, { x: startStub.x, y: endStub.y }, endStub, end],
  ];
  laneYs.forEach((laneY) => {
    candidates.push([start, startStub, { x: startStub.x, y: laneY }, { x: endStub.x, y: laneY }, endStub, end]);
  });
  laneXs.forEach((laneX) => {
    candidates.push([start, startStub, { x: laneX, y: startStub.y }, { x: laneX, y: endStub.y }, endStub, end]);
  });
  const best = candidates.sort((left, right) => wireRouteScore(left, obstacles) - wireRouteScore(right, obstacles))[0];
  return roundedWirePath(best);
}

function fastLargeTopologyEdgePath(
  topology: NetworkTopology,
  _edge: TopologyEdge,
  from: TopologyNode,
  fromPort: TopologyPort,
  to: TopologyNode,
  toPort: TopologyPort,
) {
  const start = portPosition(topology, from, fromPort);
  const end = portPosition(topology, to, toPort);
  const clearance = 34;
  const startStub = pointStub(start, clearance);
  const endStub = pointStub(end, clearance);
  const startHorizontal = start.side === "top" || start.side === "bottom";
  const endHorizontal = end.side === "top" || end.side === "bottom";
  const primaryGateway = primaryGatewayFor(topology);
  const horizontalSpan = Math.abs(start.x - end.x);
  const sharedGatewayLaneY =
    primaryGateway &&
    horizontalSpan < 620 &&
    (
      (from.id === primaryGateway.id && start.side === "bottom" && end.side === "top") ||
      (to.id === primaryGateway.id && end.side === "bottom" && start.side === "top")
    )
      ? primaryGateway.y + nodeHeight(primaryGateway) + clearance
      : null;

  if (startHorizontal && endHorizontal) {
    const laneY = sharedGatewayLaneY ?? (start.side === "top" && end.side === "top"
      ? Math.min(start.y, end.y) - clearance
      : start.side === "bottom" && end.side === "bottom"
        ? Math.max(start.y, end.y) + clearance
        : (startStub.y + endStub.y) / 2);
    return roundedWirePath([start, startStub, { x: startStub.x, y: laneY }, { x: endStub.x, y: laneY }, endStub, end]);
  }

  if (!startHorizontal && !endHorizontal) {
    const laneX = start.side === "left" && end.side === "left"
      ? Math.min(start.x, end.x) - clearance
      : start.side === "right" && end.side === "right"
        ? Math.max(start.x, end.x) + clearance
        : (startStub.x + endStub.x) / 2;
    return roundedWirePath([start, startStub, { x: laneX, y: startStub.y }, { x: laneX, y: endStub.y }, endStub, end]);
  }

  const corner = startHorizontal
    ? { x: endStub.x, y: startStub.y }
    : { x: startStub.x, y: endStub.y };
  return roundedWirePath([start, startStub, corner, endStub, end]);
}

function routedEdgePath(
  topology: NetworkTopology,
  edge: TopologyEdge,
  from: TopologyNode,
  fromPort: TopologyPort,
  to: TopologyNode,
  toPort: TopologyPort,
  systemFrames: WireClusterLayout[] = [],
) {
  if (
    topology.nodes.length >= LARGE_TOPOLOGY_NODE_THRESHOLD ||
    topology.edges.length >= LARGE_TOPOLOGY_EDGE_THRESHOLD
  ) {
    if (topology.edges.length <= 360) {
      return largeTopologyEdgePath(topology, edge, from, fromPort, to, toPort, systemFrames);
    }
    return fastLargeTopologyEdgePath(topology, edge, from, fromPort, to, toPort);
  }
  const start = portPosition(topology, from, fromPort);
  const end = portPosition(topology, to, toPort);
  const usesHorizontalEdges = [start.side, end.side].every((side) => side === "top" || side === "bottom");
  if (usesHorizontalEdges) {
    return largeTopologyEdgePath(topology, edge, from, fromPort, to, toPort, systemFrames);
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
  const obstacles = nodeWireObstacles(topology, new Set([from.id, to.id]), obstacleMargin);
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
  processors: TopologyNode[];
  inputs: TopologyNode[];
  outputs: TopologyNode[];
};

function evaSystemKey(node: TopologyNode) {
  const cleaned = node.name
    .trim()
    .replace(/(?:[-_ ]?(?:ECU|Gateway|Sensor|Aktor|Aktuator|Actuator|Controller|Steuergeraet|Steuergerät))+([-_ ]\d+)?$/i, "$1")
    .replace(/^[-_ ]+|[-_ ]+$/g, "") || node.name;
  return cleaned
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ä/g, "ae")
    .replace(/ö/g, "oe")
    .replace(/ü/g, "ue")
    .replace(/ß/g, "ss")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "");
}

const evaSemanticStopwords = new Set([
  "ecu",
  "gateway",
  "sensor",
  "aktor",
  "aktuat",
  "actuator",
  "controller",
  "steuerung",
  "steuergeraet",
  "steuergerat",
  "interface",
  "signal",
  "status",
  "current",
  "position",
  "rate",
  "level",
]);

const evaSemanticAliases: Record<string, string[]> = {
  abgas: ["exhaust", "emission"],
  antrieb: ["drive", "drivetrain", "powertrain", "motor", "engine"],
  batterie: ["battery", "power", "energie", "energy"],
  bremse: ["brake", "braking"],
  brake: ["bremse"],
  boost: ["motor", "engine", "turbo", "ladung"],
  climate: ["klima", "hvac"],
  coolant: ["kuehlung", "cooling", "thermal", "motor"],
  energie: ["energy", "power", "batterie", "battery"],
  engine: ["motor", "antrieb", "drive", "powertrain", "throttle", "turbo", "oil"],
  exhaust: ["abgas", "emission"],
  hvac: ["klima", "climate"],
  klima: ["climate", "hvac"],
  lenkung: ["steering"],
  licht: ["light", "lamp"],
  light: ["licht", "lamp"],
  ladedruck: ["boost", "turbo", "motor", "engine"],
  motor: ["engine", "antrieb", "drive", "powertrain", "throttle", "turbo", "oil"],
  oil: ["oel", "motor", "engine"],
  oel: ["oil", "motor", "engine"],
  rad: ["wheel"],
  reifen: ["tire", "tyre"],
  steering: ["lenkung"],
  throttle: ["drossel", "motor", "engine"],
  turbo: ["boost", "ladung", "motor", "engine"],
  tire: ["reifen"],
  wischer: ["wiper"],
  wiper: ["wischer"],
};

const evaSemanticDomains: Array<{ key: string; terms: string[] }> = [
  { key: "motor", terms: ["motor", "engine", "antrieb", "drive", "drivetrain", "powertrain", "throttle", "drossel", "turbo", "boost", "ladung", "ladedruck", "oil", "oel"] },
  { key: "abgas", terms: ["abgas", "exhaust", "emission"] },
  { key: "energie", terms: ["energie", "energy", "batterie", "battery", "power", "bordnetz", "alternator"] },
  { key: "klima", terms: ["klima", "climate", "hvac", "thermal", "coolant", "kuehlung", "cooling"] },
  { key: "fahrdynamik", terms: ["bremse", "brake", "lenkung", "steering", "reifen", "tire", "tyre", "rad", "wheel"] },
  { key: "adas", terms: ["adas", "radar", "kamera", "camera", "fahrassist", "assist"] },
  { key: "licht", terms: ["licht", "light", "lamp"] },
  { key: "wischer", terms: ["wischer", "wiper"] },
];

function evaSemanticTokens(node: TopologyNode) {
  const normalized = node.name
    .replace(/([a-zäöüß])([A-ZÄÖÜ])/g, "$1 $2")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ä/g, "ae")
    .replace(/ö/g, "oe")
    .replace(/ü/g, "ue")
    .replace(/ß/g, "ss")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ");
  const tokens = new Set(
    normalized
      .split(/\s+/)
      .map((token) => token.trim())
      .filter((token) => token.length >= 3 && !evaSemanticStopwords.has(token)),
  );
  for (const token of [...tokens]) {
    Object.keys(evaSemanticAliases)
      .filter((key) => token === key || (key.length >= 4 && token.includes(key)))
      .forEach((key) => {
        tokens.add(key);
        evaSemanticAliases[key]?.forEach((alias) => tokens.add(alias));
      });
  }
  return tokens;
}

function evaSemanticAffinityScore(endpoint: TopologyNode, anchor: TopologyNode) {
  const endpointTokens = evaSemanticTokens(endpoint);
  const anchorTokens = evaSemanticTokens(anchor);
  const overlap = [...endpointTokens].filter((token) => anchorTokens.has(token)).length;
  const endpointKey = evaSystemKey(endpoint);
  const anchorKey = evaSystemKey(anchor);
  const compactMatch = endpointKey.length >= 4 && anchorKey.length >= 4 && (
    endpointKey.includes(anchorKey) || anchorKey.includes(endpointKey)
  );
  return overlap * 18 + (compactMatch ? 16 : 0);
}

function topologyClusterProfileFor(topology: NetworkTopology, routingEntries: RoutingEntry[]) {
  return inferTopologyClusterProfileFromText([
    ...topology.nodes.map((node) => `${node.name} ${node.kind}`),
    ...topology.edges.map((edge) => `${edge.name ?? ""} ${edge.sourceInterfaceName ?? ""} ${edge.targetInterfaceName ?? ""}`),
    ...routingEntries.map((route) => `${route.name} ${route.description ?? ""}`),
  ].join(" "));
}

function evaSemanticDomainKey(node: TopologyNode, profile?: string) {
  return topologyClusterForText(node.name, profile).key || evaSystemKey(node);
}

function canonicalEvaProcessors(topology: NetworkTopology, anchors: TopologyNode[], profile: string) {
  const groups = new Map<string, TopologyNode[]>();
  anchors
    .filter((anchor) => anchor.kind === "ecu")
    .forEach((anchor) => {
      const key = topologySystemIdentityForText(anchor.name, profile);
      groups.set(key, [...(groups.get(key) ?? []), anchor]);
    });
  const ownerById = new Map<string, TopologyNode>();
  groups.forEach((processors) => {
    const canonical = [...processors].sort((left, right) =>
      Number(topologySystemIdentityForText(left.name, profile) !== evaSystemKey(left))
        - Number(topologySystemIdentityForText(right.name, profile) !== evaSystemKey(right))
      || nodeDegree(topology, right.id) - nodeDegree(topology, left.id)
      || left.name.length - right.name.length
      || left.name.localeCompare(right.name, "de")
      || left.id.localeCompare(right.id)
    )[0];
    processors.forEach((processor) => ownerById.set(processor.id, canonical));
  });
  anchors.filter((anchor) => anchor.kind === "gateway").forEach((anchor) => ownerById.set(anchor.id, anchor));
  return ownerById;
}

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
  const profile = topologyClusterProfileFor(topology, routingEntries);
  const anchors = stableTopologyOrder(
    topology,
    topology.nodes.filter((node) => node.kind === "ecu" || node.kind === "gateway"),
  );
  const ownerByAnchorId = canonicalEvaProcessors(topology, anchors, profile);
  const canonicalAnchorIds = new Set(anchors.map((anchor) => ownerByAnchorId.get(anchor.id)?.id ?? anchor.id));
  const canonicalAnchors = anchors.filter((anchor) => anchor.kind === "gateway" || canonicalAnchorIds.has(anchor.id));
  const ecuAnchors = canonicalAnchors.filter((node) => node.kind === "ecu");
  const gatewayAnchors = anchors.filter((node) => node.kind === "gateway");
  const groups = new Map(canonicalAnchors.map((anchor) => [anchor.id, { anchor, processors: [], inputs: [], outputs: [] } as EvaGroup]));
  anchors.forEach((anchor) => {
    const owner = ownerByAnchorId.get(anchor.id);
    if (!owner || owner.id === anchor.id || anchor.kind !== "ecu") return;
    groups.get(owner.id)?.processors.push(anchor);
  });
  const adjacency = topologyAdjacency(topology);
  const endpoints = stableTopologyOrder(
    topology,
    topology.nodes.filter((node) => node.kind === "sensor" || node.kind === "actuator"),
  );

  endpoints.forEach((endpoint) => {
    const anchorByReference = (reference?: string) => reference
      ? anchors.find((anchor) => anchor.id === reference || anchor.engineeringId === reference)
      : undefined;
    const declaredOwner = anchorByReference(endpoint.systemOwnerId);
    const adjacentEcus = [...(adjacency.get(endpoint.id) ?? [])]
      .map((id) => anchors.find((anchor) => anchor.id === id))
      .filter((anchor): anchor is TopologyNode => anchor?.kind === "ecu");
    const canonicalAdjacentEcus = [...new Map(adjacentEcus.map((anchor) => {
      const canonical = ownerByAnchorId.get(anchor.id) ?? anchor;
      return [canonical.id, canonical];
    })).values()];
    const trustedDeclaredOwner = declaredOwner && endpoint.systemOwnerSource !== "inferred"
      ? ownerByAnchorId.get(declaredOwner.id) ?? declaredOwner
      : undefined;
    const physicalOwner = canonicalAdjacentEcus.length === 1 ? canonicalAdjacentEcus[0] : undefined;
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
    const endpointClusterKey = evaSemanticDomainKey(endpoint, profile);
    const scoredCandidates = candidates.map((candidate) => {
      const anchorClusterKey = evaSemanticDomainKey(candidate.anchor, profile);
      return {
        ...candidate,
        score:
          evaSemanticAffinityScore(endpoint, candidate.anchor) * 3
          + topologyClusterAffinity(endpointClusterKey, anchorClusterKey, profile)
          + (routedAnchor?.id === candidate.anchor.id ? 32 : 0)
          - Math.min(24, candidate.distance * 4),
      };
    });
    const selected = trustedDeclaredOwner ?? physicalOwner ?? scoredCandidates.sort((left, right) =>
      right.score - left.score ||
      left.distance - right.distance ||
      nodeDegree(topology, right.anchor.id) - nodeDegree(topology, left.anchor.id) ||
      left.anchor.name.localeCompare(right.anchor.name, "de") ||
      left.anchor.id.localeCompare(right.anchor.id),
    )[0]?.anchor;
    if (!selected) return;
    const canonicalSelected = selected.kind === "ecu" ? ownerByAnchorId.get(selected.id) ?? selected : selected;
    const group = groups.get(canonicalSelected.id);
    if (!group) return;
    if (endpoint.kind === "sensor") group.inputs.push(endpoint);
    else group.outputs.push(endpoint);
  });

  return canonicalAnchors.map((anchor) => {
    const group = groups.get(anchor.id)!;
    return {
      ...group,
      processors: stableTopologyOrder(topology, group.processors),
      inputs: stableTopologyOrder(topology, group.inputs),
      outputs: stableTopologyOrder(topology, group.outputs),
    };
  });
}

function nodeRowWidth(nodes: TopologyNode[], gap = EVA_ROW_GAP) {
  return nodes.reduce((total, node) => total + nodeWidth(node), 0) + Math.max(0, nodes.length - 1) * gap;
}

function endpointGridRows(topology: NetworkTopology, nodes: TopologyNode[]) {
  const ordered = stableTopologyOrder(topology, nodes);
  if (ordered.length <= EVA_ENDPOINT_GRID_COLUMNS) return ordered.length ? [ordered] : [];
  const columns = Math.min(EVA_ENDPOINT_GRID_COLUMNS, Math.max(2, Math.ceil(ordered.length / 2)));
  return ordered.reduce<TopologyNode[][]>((rows, node, index) => {
    const rowIndex = Math.floor(index / columns);
    rows[rowIndex] = [...(rows[rowIndex] ?? []), node];
    return rows;
  }, []);
}

function endpointGridWidth(rows: TopologyNode[][]) {
  return Math.max(0, ...rows.map((row) => nodeRowWidth(row, EVA_ENDPOINT_COLUMN_GAP)));
}

function evaGroupWidth(topology: NetworkTopology, group: EvaGroup) {
  const endpointRows = endpointGridRows(topology, [...group.inputs, ...group.outputs]);
  return Math.max(
    nodeRowWidth([group.anchor, ...group.processors]),
    endpointGridWidth(endpointRows),
    EVA_GATEWAY_MIN_WIDTH,
  );
}

function evaGroupHeight(topology: NetworkTopology, group: EvaGroup) {
  const processors = [group.anchor, ...group.processors];
  const endpointRows = endpointGridRows(topology, [...group.inputs, ...group.outputs]);
  const processingHeight = Math.max(NODE_MIN_HEIGHT, ...processors.map((node) => nodeHeight(node)));
  if (endpointRows.length === 0) return processingHeight;
  return processingHeight
    + EVA_PROCESSING_TO_ENDPOINT_GAP
    + endpointRows.reduce((total, row, index) => (
      total + endpointRowHeight(row) + (index > 0 ? EVA_ENDPOINT_ROW_GAP : 0)
    ), 0);
}

function evaGroupFamilies(groups: EvaGroup[], profile: string) {
  const families = new Map<string, { key: string; label: string; groups: EvaGroup[] }>();
  groups.forEach((group) => {
    const clusterKey = evaSemanticDomainKey(group.anchor, profile);
    const family = topologyClusterFamilyForKey(clusterKey, profile);
    const current = families.get(family.key) ?? { ...family, groups: [] };
    current.groups.push(group);
    families.set(family.key, current);
  });
  return [...families.values()]
    .map((family) => ({
      ...family,
      groups: [...family.groups].sort((left, right) =>
        compareTopologyClusterKeys(
          evaSemanticDomainKey(left.anchor, profile),
          evaSemanticDomainKey(right.anchor, profile),
          profile,
        ) || left.anchor.name.localeCompare(right.anchor.name, "de")
      ),
    }))
    .sort((left, right) =>
      compareTopologyClusterKeys(
        evaSemanticDomainKey(left.groups[0].anchor, profile),
        evaSemanticDomainKey(right.groups[0].anchor, profile),
        profile,
      ) || left.label.localeCompare(right.label, "de")
    );
}

type EvaClusterLayout = {
  id: string;
  memberIds: string[];
  label: string;
  count: number;
  inputs: number;
  processors: number;
  outputs: number;
  kind: TopologyNode["kind"];
  left: number;
  top: number;
  width: number;
  height: number;
};

type EvaDomainClusterLayout = {
  id: string;
  memberIds: string[];
  label: string;
  left: number;
  top: number;
  width: number;
  height: number;
  busLabel: string;
};

function evaClusterLayouts(
  topology: NetworkTopology,
  routingEntries: RoutingEntry[],
  groups = buildEvaGroups(topology, routingEntries),
) {
  return groups.flatMap<EvaClusterLayout>((group) => {
    if (group.anchor.kind === "gateway") {
      return [];
    }
    const members = [group.anchor, ...group.processors, ...group.inputs, ...group.outputs];
    const left = Math.min(...members.map((node) => node.x));
    const top = Math.min(...members.map((node) => node.y));
    const right = Math.max(...members.map((node) => node.x + nodeWidth(node)));
    const bottom = Math.max(...members.map((node) => node.y + nodeHeight(node)));
    return [{
      id: group.anchor.id,
      memberIds: members.map((node) => node.id),
      label: group.anchor.name,
      count: members.length,
      inputs: group.inputs.length,
      processors: 1 + group.processors.length,
      outputs: group.outputs.length,
      kind: group.anchor.kind,
      left: Math.max(8, left - EVA_CLUSTER_PADDING),
      top: Math.max(EVA_LABEL_HEIGHT, top - EVA_CLUSTER_PADDING),
      width: right - left + EVA_CLUSTER_PADDING * 2,
      height: bottom - top + EVA_CLUSTER_PADDING * 2,
    }];
  });
}

function evaDomainClusterLayouts(
  topology: NetworkTopology,
  routingEntries: RoutingEntry[],
  systemFrames: EvaClusterLayout[],
) {
  const profile = topologyClusterProfileFor(topology, routingEntries);
  const framesByFamily = new Map<string, { label: string; frames: EvaClusterLayout[] }>();
  systemFrames.forEach((frame) => {
    const anchor = topology.nodes.find((node) => node.id === frame.id);
    if (!anchor) return;
    const clusterKey = evaSemanticDomainKey(anchor, profile);
    const family = topologyClusterFamilyForKey(clusterKey, profile);
    const current = framesByFamily.get(family.key) ?? { label: family.label, frames: [] };
    current.frames.push(frame);
    framesByFamily.set(family.key, current);
  });
  return [...framesByFamily.entries()].flatMap<EvaDomainClusterLayout>(([key, family]) => {
    if (family.frames.length < 2) return [];
    const left = Math.min(...family.frames.map((frame) => frame.left));
    const top = Math.min(...family.frames.map((frame) => frame.top));
    const right = Math.max(...family.frames.map((frame) => frame.left + frame.width));
    const bottom = Math.max(...family.frames.map((frame) => frame.top + frame.height));
    const memberIds = family.frames.flatMap((frame) => frame.memberIds);
    const busCounts = new Map<TopologyEdge["bus"], number>();
    topology.edges.forEach((edge) => {
      if (memberIds.includes(edge.source) || memberIds.includes(edge.target)) {
        busCounts.set(edge.bus, (busCounts.get(edge.bus) ?? 0) + 1);
      }
    });
    const dominantBus = [...busCounts.entries()].sort((left, right) => right[1] - left[1])[0]?.[0];
    const busLabel = dominantBus === "can_fd" ? `${family.label}-CAN` : dominantBus === "automotive_ethernet" ? `${family.label}-Ethernet` : dominantBus === "lin" ? `${family.label}-LIN` : `${family.label}-Netz`;
    return [{
      id: key,
      memberIds,
      label: family.label,
      left: Math.max(4, left - EVA_DOMAIN_CLUSTER_PADDING),
      top: Math.max(36, top - EVA_DOMAIN_CLUSTER_PADDING),
      width: right - left + EVA_DOMAIN_CLUSTER_PADDING * 2,
      height: bottom - top + EVA_DOMAIN_CLUSTER_PADDING * 2,
      busLabel,
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

function topologyCacheSignature(topology: NetworkTopology, routingEntries: RoutingEntry[]) {
  const nodes = topology.nodes
    .map((node) => [
      node.id,
      node.kind,
      node.name,
      node.engineeringId ?? "",
      node.systemOwnerId ?? "",
      ...node.ports.map((port) => `${port.id}:${port.name}:${port.bus}:${port.engineeringId ?? ""}`).sort(),
    ].join(":"))
    .sort()
    .join("|");
  const edges = topology.edges
    .map((edge) => [
      edge.id,
      edge.bus,
      edge.source,
      edge.sourcePort,
      edge.target,
      edge.targetPort,
      edge.direction ?? "",
      edge.relationType ?? "",
      edge.routingEntryId ?? "",
      ...(edge.routingEntryIds ?? []),
    ].join(":"))
    .sort()
    .join("|");
  return `${nodes}::${edges}::${routingGroupSignature(routingEntries)}`;
}

function activeLayoutProjectId() {
  return readActiveProjectId();
}

function compactLayoutKey(signature: string) {
  let first = 0x811c9dc5;
  let second = 0x9e3779b9;
  for (let index = 0; index < signature.length; index += 1) {
    const code = signature.charCodeAt(index);
    first = Math.imul(first ^ code, 0x01000193);
    second = Math.imul(second ^ code, 0x85ebca6b);
  }
  return `${(first >>> 0).toString(16).padStart(8, "0")}${(second >>> 0).toString(16).padStart(8, "0")}`;
}

function networkLayoutCacheKey(topologyKey: string) {
  return `${NETWORK_LAYOUT_CACHE_PREFIX}${activeLayoutProjectId()}:${topologyKey}`;
}

function readNetworkLayoutCache(topologyKey: string) {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(networkLayoutCacheKey(topologyKey));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CachedNetworkLayout;
    return parsed && typeof parsed === "object" && parsed.nodes ? parsed : null;
  } catch {
    return null;
  }
}

function writeNetworkLayoutCache(
  topologyKey: string,
  topology: NetworkTopology,
) {
  if (typeof window === "undefined") return;
  const payload: CachedNetworkLayout = {
    createdAt: new Date().toISOString(),
    nodes: Object.fromEntries(topology.nodes.map((node) => [
      node.id,
      {
        x: node.x,
        y: node.y,
        width: node.width,
        height: node.height,
        ports: Object.fromEntries(node.ports.map((port) => [
          port.id,
          { side: port.side, offset: port.offset ?? 0.5 },
        ])),
      },
    ])),
  };
  try {
    window.localStorage.setItem(networkLayoutCacheKey(topologyKey), JSON.stringify(payload));
  } catch {
    // Layout persistence is an optimization; the editor must remain usable without it.
  }
}

function workflowLayoutNodes(topology: NetworkTopology): WorkflowTopologyLayoutNode[] {
  return topology.nodes.map((node) => ({
    node_id: node.id,
    x: node.x,
    y: node.y,
    width: node.width,
    height: node.height,
    ports: Object.fromEntries(node.ports.map((port) => [
      port.id,
      { side: port.side, offset: port.offset ?? 0.5 },
    ])),
  }));
}

function cachedNetworkLayout(layout: WorkflowTopologyLayout): CachedNetworkLayout {
  return {
    createdAt: layout.nodes.reduce(
      (latest, node) => node.updated_at && node.updated_at > latest ? node.updated_at : latest,
      "",
    ),
    nodes: Object.fromEntries(layout.nodes.map((node) => [node.node_id, {
      x: node.x,
      y: node.y,
      width: node.width ?? undefined,
      height: node.height ?? undefined,
      ports: node.ports,
    }])),
  };
}

function applyNetworkLayoutCache(topology: NetworkTopology, cache: CachedNetworkLayout): NetworkTopology {
  return {
    ...topology,
    nodes: topology.nodes.map((node) => {
      const cached = cache.nodes[node.id];
      if (!cached || !Number.isFinite(cached.x) || !Number.isFinite(cached.y)) return node;
      return {
        ...node,
        x: cached.x,
        y: cached.y,
        width: Number.isFinite(cached.width) ? cached.width : node.width,
        height: Number.isFinite(cached.height) ? cached.height : node.height,
        ports: node.ports.map((port) => {
          const cachedPort = cached.ports?.[port.id];
          if (!cachedPort || !["left", "right", "top", "bottom"].includes(cachedPort.side)) return port;
          return {
            ...port,
            side: cachedPort.side,
            offset: Math.max(0, Math.min(1, Number(cachedPort.offset) || 0.5)),
          };
        }),
      };
    }),
  };
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
    const expectedLeft = CANVAS_MARGIN;
    if (Math.abs(primaryGateway.y - expectedTop) > 28) return true;
    if (Math.abs(primaryGateway.x - expectedLeft) > 28) return true;
    if (topology.nodes.some((node) =>
      node.id !== primaryGateway.id &&
      (node.kind === "ecu" || node.kind === "gateway") &&
      node.y < primaryGateway.y + nodeHeight(primaryGateway) + EVA_GATEWAY_TO_PROCESSING_GAP - 18
    )) return true;
  }
  if (evaGroups.some((group) => {
    const endpoints = [...group.inputs, ...group.outputs];
    const processors = [group.anchor, ...group.processors];
    const expectedHeight = endpointRowHeight(endpoints);
    return group.processors.some((node) =>
      Math.abs(node.y - group.anchor.y) > 0.1
    ) || (endpoints.length > 0 && endpoints.some((node) =>
      node.y < group.anchor.y + nodeHeight(group.anchor) + 48 ||
      Math.abs(nodeWidth(node) - ENDPOINT_NODE_WIDTH) > 0.1 ||
      Math.abs(nodeHeight(node) - expectedHeight) > 0.1,
    )) || (endpoints.length > 0 && endpoints.some((node) =>
      node.y < group.anchor.y + nodeHeight(group.anchor) + EVA_PROCESSING_TO_ENDPOINT_GAP - 36
    )) || nodeRowWidth(processors) > evaGroupWidth(topology, group) + 0.1;
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
  const systemFrames = evaClusterLayouts(topology, routingEntries, evaGroups);
  if (systemFrames.some((frame, index) =>
    systemFrames.slice(index + 1).some((other) => {
      const separated =
        frame.left + frame.width + 48 <= other.left ||
        other.left + other.width + 48 <= frame.left ||
        frame.top + frame.height + 48 <= other.top ||
        other.top + other.height + 48 <= frame.top;
      return !separated;
    })
  )) return true;
  const domainFrames = evaDomainClusterLayouts(topology, routingEntries, systemFrames);
  if (domainFrames.some((frame, index) =>
    domainFrames.slice(index + 1).some((other) => {
      const separated =
        frame.left + frame.width + EVA_DOMAIN_CLUSTER_GAP / 2 <= other.left ||
        other.left + other.width + EVA_DOMAIN_CLUSTER_GAP / 2 <= frame.left ||
        frame.top + frame.height + EVA_DOMAIN_CLUSTER_GAP / 2 <= other.top ||
        other.top + other.height + EVA_DOMAIN_CLUSTER_GAP / 2 <= frame.top;
      return !separated;
    })
  )) return true;
  if (domainFrames.some((domain) => systemFrames.some((frame) => {
    if (domain.memberIds.some((memberId) => frame.memberIds.includes(memberId))) return false;
    const separated =
      frame.left + frame.width + 24 <= domain.left ||
      domain.left + domain.width + 24 <= frame.left ||
      frame.top + frame.height + 24 <= domain.top ||
      domain.top + domain.height + 24 <= frame.top;
    return !separated;
  }))) return true;
  return topology.nodes.some((node, index) =>
    topology.nodes.slice(index + 1).some((other) => {
      const separated =
        node.x + nodeWidth(node) + 40 < other.x ||
        other.x + nodeWidth(other) + 40 < node.x ||
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
  const profile = topologyClusterProfileFor(sizedTopology, routingEntries);
  const primaryGateway = primaryGatewayFor(sizedTopology);
  const groups = buildEvaGroups(sizedTopology, routingEntries);
  const primaryGroup = groups.find((group) => group.anchor.id === primaryGateway?.id);
  const branchGroups = groups.filter((group) => group.anchor.id !== primaryGateway?.id);
  const families = evaGroupFamilies(branchGroups, profile);
  const contentTop = EVA_LABEL_HEIGHT + 24;
  const gatewayHeight = primaryGateway ? nodeHeight(primaryGateway) : 0;
  const processingTop = primaryGateway ? contentTop + gatewayHeight + EVA_GATEWAY_TO_PROCESSING_GAP : contentTop;
  const arranged = new Map<string, TopologyNode>();
  const groupedIds = new Set(groups.flatMap((group) => [
    group.anchor.id,
    ...group.processors.map((node) => node.id),
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
  if (directNodes.length > 0) {
    families.push({
      key: "unassigned",
      label: "Nicht zugeordnet",
      groups: directNodes.map((node) => ({ anchor: node, processors: [], inputs: [], outputs: [] })),
    });
  }
  const minimumSpan = Math.max(1180, surfaceWidth || 0) - CANVAS_MARGIN * 2;
  const estimatedGroupArea = families.flatMap((family) => family.groups).reduce((total, group) => (
    total + evaGroupWidth(sizedTopology, group) * (evaGroupHeight(sizedTopology, group) + EVA_CLUSTER_ROW_GAP)
  ), 0);
  const preferredRowSpan = Math.max(
    minimumSpan,
    Math.min(6800, Math.max(minimumSpan * 5, Math.sqrt(estimatedGroupArea * 5))),
  );
  const familyBlocks = families.map((family) => {
    const groupWidths = family.groups.map((group) => evaGroupWidth(sizedTopology, group));
    const maximumGroupWidth = Math.max(0, ...groupWidths);
    const familyArea = family.groups.reduce((total, group) => (
      total + evaGroupWidth(sizedTopology, group) * evaGroupHeight(sizedTopology, group)
    ), 0);
    const targetWidth = Math.max(
      maximumGroupWidth,
      Math.min(preferredRowSpan * 0.7, Math.sqrt(Math.max(1, familyArea) * 2.2)),
    );
    const rows = family.groups.reduce<Array<{ groups: EvaGroup[]; width: number; height: number }>>((result, group) => {
      const width = evaGroupWidth(sizedTopology, group);
      const height = evaGroupHeight(sizedTopology, group);
      const current = result[result.length - 1];
      const candidateWidth = (current?.width ?? 0) + (current?.groups.length ? EVA_CLUSTER_GAP : 0) + width;
      if (!current || current.groups.length >= EVA_SYSTEMS_PER_FAMILY_ROW || candidateWidth > targetWidth) {
        result.push({ groups: [group], width, height });
      } else {
        current.groups.push(group);
        current.width = candidateWidth;
        current.height = Math.max(current.height, height);
      }
      return result;
    }, []);
    return {
      ...family,
      rows,
      width: Math.max(maximumGroupWidth, ...rows.map((row) => row.width)) + EVA_DOMAIN_CLUSTER_PADDING * 2,
      height: rows.reduce((total, row) => total + row.height, 0)
        + Math.max(0, rows.length - 1) * EVA_CLUSTER_ROW_GAP
        + EVA_DOMAIN_CLUSTER_PADDING * 2,
    };
  });
  const blockRows = familyBlocks.reduce<Array<{ blocks: typeof familyBlocks; width: number; height: number }>>((rows, block) => {
    const current = rows[rows.length - 1];
    const candidateWidth = (current?.width ?? 0) + (current?.blocks.length ? EVA_DOMAIN_CLUSTER_GAP : 0) + block.width;
    if (!current || candidateWidth > preferredRowSpan) {
      rows.push({ blocks: [block], width: block.width, height: block.height });
    } else {
      current.blocks.push(block);
      current.width = candidateWidth;
      current.height = Math.max(current.height, block.height);
    }
    return rows;
  }, []);
  const layoutSpan = Math.max(minimumSpan, ...blockRows.map((row) => row.width));

  const arrangeGroupAt = (group: EvaGroup, left: number, top: number, unitWidth: number) => {
      const centerX = left + unitWidth / 2;
      const processors = stableTopologyOrder(sizedTopology, [group.anchor, ...group.processors]);
      if (group.anchor.kind === "sensor" || group.anchor.kind === "actuator") {
        arranged.set(group.anchor.id, {
          ...group.anchor,
          x: Math.round(centerX - ENDPOINT_NODE_WIDTH / 2),
          y: Math.round(top),
          width: ENDPOINT_NODE_WIDTH,
          height: directEndpointHeight,
        });
      } else {
        const processingHeight = Math.max(NODE_MIN_HEIGHT, ...processors.map((node) => nodeHeight(node)));
        const endpointTop = top + processingHeight + EVA_PROCESSING_TO_ENDPOINT_GAP;
        const processorRowWidth = nodeRowWidth(processors);
        let processorX = centerX - processorRowWidth / 2;
        processors.forEach((processor) => {
          arranged.set(processor.id, { ...processor, x: Math.round(processorX), y: Math.round(top) });
          processorX += nodeWidth(processor) + EVA_ROW_GAP;
        });
        const endpointRows = endpointGridRows(sizedTopology, [...group.inputs, ...group.outputs]);
        const groupEndpointHeight = endpointRowHeight(endpointRows.flat());
        let endpointRowY = endpointTop;
        endpointRows.forEach((endpointRow) => {
          const rowWidth = nodeRowWidth(endpointRow, EVA_ENDPOINT_COLUMN_GAP);
          let endpointX = centerX - rowWidth / 2;
          endpointRow.forEach((node) => {
            arranged.set(node.id, {
              ...node,
              x: Math.round(endpointX),
              y: Math.round(endpointRowY),
              width: ENDPOINT_NODE_WIDTH,
              height: groupEndpointHeight,
            });
            endpointX += nodeWidth(node) + EVA_ENDPOINT_COLUMN_GAP;
          });
          endpointRowY += groupEndpointHeight + EVA_ENDPOINT_ROW_GAP;
        });
      }
  };

  let blockRowTop = processingTop;
  blockRows.forEach((blockRow) => {
    let blockX = CANVAS_MARGIN + Math.max(0, (layoutSpan - blockRow.width) / 2);
    blockRow.blocks.forEach((block) => {
      let internalRowTop = blockRowTop + EVA_DOMAIN_CLUSTER_PADDING;
      block.rows.forEach((row) => {
        let groupX = blockX + EVA_DOMAIN_CLUSTER_PADDING + Math.max(0, (block.width - EVA_DOMAIN_CLUSTER_PADDING * 2 - row.width) / 2);
        row.groups.forEach((group) => {
          const unitWidth = evaGroupWidth(sizedTopology, group);
          arrangeGroupAt(group, groupX, internalRowTop, unitWidth);
          groupX += unitWidth + EVA_CLUSTER_GAP;
        });
        internalRowTop += row.height + EVA_CLUSTER_ROW_GAP;
      });
      blockX += block.width + EVA_DOMAIN_CLUSTER_GAP;
    });
    blockRowTop += blockRow.height + EVA_DOMAIN_CLUSTER_GAP;
  });

  if (primaryGateway) {
    arranged.set(primaryGateway.id, {
      ...primaryGateway,
      x: CANVAS_MARGIN,
      y: contentTop,
      width: primaryGatewayLayoutWidth(sizedTopology, primaryGateway, layoutSpan),
    });
  }

  return viewportAlignedTopology(nameGatewayInterfaces(orderPortsByConnectedNodes({
    ...sizedTopology,
    nodes: sizedTopology.nodes.map((node) => arranged.get(node.id) ?? node),
  })));
}

export function NetworkEditor({
  topology,
  modelHardware,
  routingEntries,
  onChange,
  onRelationshipsChange,
  onLayoutChange,
  onAssignmentChange,
  onFrameDeviceCreate,
  onBusRename,
}: {
  topology: NetworkTopology;
  modelHardware: HardwareNode[];
  routingEntries: RoutingEntry[];
  onChange: (next: NetworkTopology) => void;
  onLayoutChange?: (next: NetworkTopology, reset?: boolean, resetWires?: boolean) => Promise<void>;
  onAssignmentChange?: (request: NetworkAssignmentRequest) => Promise<void>;
  onFrameDeviceCreate?: (request: FrameDeviceRequest) => Promise<void>;
  onBusRename?: (networkId: string, name: string) => Promise<NetworkTopology>;
  onRelationshipsChange?: (next: NetworkTopology, busChange?: BusChangeRequest) => void | boolean | Promise<void | boolean>;
}) {
  const surfaceRef = useRef<HTMLDivElement>(null);
  const panRef = useRef<{ pointerId: number; x: number; y: number; left: number; top: number } | null>(null);
  const [panning, setPanning] = useState(false);
  const [lasso, setLasso] = useState(false);
  useEffect(() => {
    if (!lasso) return;
    const cancel = (event: KeyboardEvent) => { if (event.key === 'Escape') setLasso(false); };
    window.addEventListener('keydown', cancel);
    return () => window.removeEventListener('keydown', cancel);
  }, [lasso]);
  const [assignmentSelection, setAssignmentSelection] = useState<string[]>([]);
  const [createInFrame, setCreateInFrame] = useState<{id: string; label: string} | null>(null);
  useEffect(() => {
    const move = (event: PointerEvent) => {
      const start = panRef.current, surface = surfaceRef.current;
      if (!start || !surface || start.pointerId !== event.pointerId) return;
      event.preventDefault();
      surface.scrollLeft = start.left - (event.clientX - start.x);
      surface.scrollTop = start.top - (event.clientY - start.y);
    };
    const finish = () => { panRef.current = null; setPanning(false); };
    window.addEventListener("pointermove", move, { passive: false });
    window.addEventListener("pointerup", finish);
    window.addEventListener("pointercancel", finish);
    window.addEventListener("blur", finish);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", finish);
      window.removeEventListener("pointercancel", finish);
      window.removeEventListener("blur", finish);
    };
  }, []);
  const [drag, setDrag] = useState<DragState | null>(null);
  const [connectionTarget, setConnectionTarget] = useState<ConnectionEndpoint | null>(null);
  const [connectionHint, setConnectionHint] = useState('');
  const [dragTopology, setDragTopology] = useState<NetworkTopology | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);
  const [selectedBus, setSelectedBus] = useState<string | null>(null);
  const [selectedPort, setSelectedPort] = useState<{nodeId:string; portId:string} | null>(null);
  const [selectedBranch, setSelectedBranch] = useState<{busId:string; portId:string} | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [menu, setMenu] = useState<MenuState | null>(null);
  const portSavePending = useRef(false);
  const [portSaving, setPortSaving] = useState(false);
  const [portMessage, setPortMessage] = useState("");
  const [portError, setPortError] = useState("");
  const deletePending = useRef(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [deleteMessage, setDeleteMessage] = useState("");
  const [addMenu, setAddMenu] = useState<NodeKind | null>(null);
  const [rename, setRename] = useState<{ nodeId: string; name: string } | null>(null);
  const devicePorts = [...new Map(
    (topology.nodes.find(node => node.id === rename?.nodeId)?.ports ?? [])
      .map(port => [port.hardwareInterfaceId || port.id, port]),
  ).values()].sort((a, b) => a.name.localeCompare(b.name, 'de', {numeric: true}) || a.id.localeCompare(b.id));
  const [relationship, setRelationship] = useState<RelationshipDraft | null>(null);
  const [relationshipChoices, setRelationshipChoices] = useState<{busName: string; edgeIds: string[]} | null>(null);
  const [busNameDraft, setBusNameDraft] = useState<{id: string; name: string} | null>(null);
  const [busTransferOpen, setBusTransferOpen] = useState(false);
  const [relationshipSaving, setRelationshipSaving] = useState(false);
  const [relationshipError, setRelationshipError] = useState("");
  const [busPreview, setBusPreview] = useState<BusChangePreview | null>(null);
  const [busPreviewError, setBusPreviewError] = useState("");
  const busChanged = Boolean(relationship?.bus && relationship.bus !== relationship.edge.bus);
  const relationshipModified = Boolean(relationship && (() => {
    const e = relationship.edge;
    const from = topology.nodes.find(n => n.id === e.source), to = topology.nodes.find(n => n.id === e.target);
    return relationship.name !== (e.name || `${from?.name ?? "Quelle"} ↔ ${to?.name ?? "Ziel"}`)
      || relationship.description !== (e.description ?? "") || relationship.direction !== (e.direction ?? "BIDIRECTIONAL")
      || relationship.relationType !== (e.relationType ?? "CONNECTED_TO")
      || relationship.sourceInterfaceName !== relationshipInterfaceName(e.sourceInterfaceName, from, e.sourcePort, e.bus)
      || relationship.targetInterfaceName !== relationshipInterfaceName(e.targetInterfaceName, to, e.targetPort, e.bus);
  })());
  const previewNetworkId = relationship?.edge.physicalNetworkId;
  const previewBus = busChanged ? relationship?.bus : undefined;
  useEffect(() => {
    let cancelled = false;
    setBusPreview(null);
    setBusPreviewError("");
    if (previewBus && previewNetworkId) {
      previewBusChange(previewNetworkId, previewBus).then(result => {
        if (cancelled) return;
        setBusPreview(result);
        const network = result.networks.find(n => n.id === previewNetworkId);
        if (network) setRelationship(current => {
          if (!current || current.bus !== previewBus || current.edge.physicalNetworkId !== previewNetworkId) return current;
          const defaults = new Set([network.previous_name, networkLabel(previewNetworkId, previewBus), networkLabel(previewNetworkId, current.edge.bus)]);
          return {...current, sourceInterfaceName: defaults.has(current.sourceInterfaceName) ? network.name : current.sourceInterfaceName,
            targetInterfaceName: defaults.has(current.targetInterfaceName) ? network.name : current.targetInterfaceName};
        });
      })
        .catch(error => { if (!cancelled) setBusPreviewError(error instanceof Error ? error.message : "Buswechsel konnte nicht geprüft werden."); });
    }
    return () => { cancelled = true; };
  }, [previewBus, previewNetworkId]);
  const [surfaceWidth, setSurfaceWidth] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [wireAlignmentOffsetX, setWireAlignmentOffsetX] = useState(WIRE_ALIGNMENT_DEFAULT_OFFSET);
  const [fullscreen, setFullscreen] = useState(false);
  const [contextOverlay, setContextOverlay] = useState<NetworkContextOverlay | null>(null);
  const [visibleCanvasBounds, setVisibleCanvasBounds] = useState<CanvasViewportBounds | null>(null);
  const [layoutSaving, setLayoutSaving] = useState(false);
  const [layoutError, setLayoutError] = useState("");
  const failedLayoutRef = useRef<NetworkTopology | null>(null);
  const [loadedLayoutKey, setLoadedLayoutKey] = useState("");
  const arrangedStructureRef = useRef("");
  const activeDragRef = useRef<DragState | null>(null);
  const pendingDragTopologyRef = useRef<NetworkTopology | null>(null);
  const dragTopologyRef = useRef<NetworkTopology | null>(null);
  const dragFrameRef = useRef(0);
  const topologyRef = useRef(topology);
  const centralGatewayArchitectureRef = useRef(false);
  const workflowSelectionSignatureRef = useRef("");

  useEffect(() => {
    if (!activeDragRef.current) topologyRef.current = topology;
  }, [topology]);

  useEffect(() => {
    const saved = Number(window.localStorage.getItem(WIRE_ALIGNMENT_OFFSET_STORAGE_KEY));
    if (!Number.isFinite(saved)) return;
    const next = normalizeWireAlignmentOffset(saved);
    setWireAlignmentOffsetX((current) => (current === next ? current : next));
  }, []);

  const displayTopology = dragTopology ?? topology;
  const savedScene = useMemo(() => topology.scene && (topology.scene.crossingVersion === 1 ? topology.scene : withWireCrossings(topology.scene)), [topology.scene]);
  const scene = useMemo(() => savedScene && dragTopology
    ? drag?.mode === 'move-bus' ? dragTopology.scene : previewNetworkScene(savedScene, topology, dragTopology)
    : savedScene, [savedScene, topology, dragTopology, drag?.mode]);

  const flushDragTopology = useCallback(() => {
    if (dragFrameRef.current) {
      window.cancelAnimationFrame(dragFrameRef.current);
      dragFrameRef.current = 0;
    }
    const pending = pendingDragTopologyRef.current ?? dragTopologyRef.current;
    pendingDragTopologyRef.current = null;
    dragTopologyRef.current = null;
    if (pending) {
      topologyRef.current = pending;
      if (topology.scene && onLayoutChange) {
        setLayoutSaving(true);
        setLayoutError("");
        const next = {...pending, scene: activeDragRef.current?.mode === 'move-bus' ? pending.scene : previewNetworkScene(topology.scene, topology, pending)};
        failedLayoutRef.current = next;
        void onLayoutChange(next).then(() => {failedLayoutRef.current = null;}).catch(error => {
          onChange(topology);
          topologyRef.current = topology;
          setLayoutError(error instanceof Error ? error.message : "Layout konnte nicht gespeichert werden.");
        }).finally(() => setLayoutSaving(false));
        onChange(next);
      } else onChange(pending);
    }
  }, [onChange, onLayoutChange, topology]);

  const scheduleDragTopology = useCallback((next: NetworkTopology) => {
    pendingDragTopologyRef.current = next;
    topologyRef.current = next;
    if (dragFrameRef.current) return;
    dragFrameRef.current = window.requestAnimationFrame(() => {
      dragFrameRef.current = 0;
      const pending = pendingDragTopologyRef.current;
      pendingDragTopologyRef.current = null;
      if (pending) {
        topologyRef.current = pending;
        dragTopologyRef.current = pending;
        setDragTopology(pending);
      }
    });
  }, []);

  useEffect(() => {
    return () => {
      if (dragFrameRef.current) window.cancelAnimationFrame(dragFrameRef.current);
    };
  }, []);

  useEffect(() => {
    const node = displayTopology.nodes.find((item) => item.id === selectedNode);
    const edge = displayTopology.edges.find((item) => item.id === selectedEdge);
    const signature = JSON.stringify({
      edge: edge ? { id: edge.id, bus: edge.bus } : null,
      node: node ? { id: node.id, name: node.name, network: node.ports[0]?.bus ?? null } : null,
    });
    if (workflowSelectionSignatureRef.current === signature || (!workflowSelectionSignatureRef.current && !node && !edge)) return;
    workflowSelectionSignatureRef.current = signature;
    void setWorkflowContext({
      selected_object: node ? { id: node.id, type: "NetworkNode", name: node.name } : null,
      selected_network: edge?.bus ?? node?.ports[0]?.bus ?? null,
    }).catch(() => undefined);
  }, [displayTopology.edges, displayTopology.nodes, selectedEdge, selectedNode]);

  const pointFromEvent = useCallback((event: { clientX: number; clientY: number }) => {
    const rect = surfaceRef.current?.getBoundingClientRect();
    const surface = surfaceRef.current;
    return {
      x: (event.clientX - (rect?.left ?? 0) + (surface?.scrollLeft ?? 0)) / zoom,
      y: (event.clientY - (rect?.top ?? 0) + (surface?.scrollTop ?? 0)) / zoom,
    };
  }, [zoom]);

  function beginBusDrag(event: ReactPointerEvent<SVGElement>, bus: SceneBus, branch?: SceneBranch) {
    event.stopPropagation();
    if (event.button !== 0 || !onLayoutChange || lasso || layoutSaving || portSaving || relationshipSaving || deleting) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    const point = pointFromEvent(event);
    const segment = branch?.points.slice(1).map((b, index) => {
      const a = branch.points[index];
      const distance = Math.hypot(point.x - Math.max(Math.min(a.x, b.x), Math.min(Math.max(a.x, b.x), point.x)),
        point.y - Math.max(Math.min(a.y, b.y), Math.min(Math.max(a.y, b.y), point.y)));
      return {horizontal: a.y === b.y && a.x !== b.x, distance};
    }).sort((a, b) => a.distance - b.distance)[0];
    const portId = segment?.horizontal ? branch?.portId : undefined;
    const last = (branch ?? bus.branches[0]).points.at(-1)!;
    const nextDrag: DragState = {mode: 'move-bus', busId: bus.id, portId, startX: point.x, startY: point.y,
      coordinate: portId ? last.y : last.x, baseline: topology};
    setSelectedBus(bus.id);
    setSelectedPort(null);
    setSelectedBranch(branch ? {busId:bus.id, portId:branch.portId} : null);
    if (!branch) {setSelectedNode(null); setSelectedEdge(null);}
    setMenu(null);
    setContextOverlay(null);
    activeDragRef.current = nextDrag;
    setDrag(nextDrag);
  }

  useEffect(() => {
    const surface = surfaceRef.current;
    if (!surface) return;
    const update = () => setSurfaceWidth(surface.clientWidth);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(surface);
    return () => observer.disconnect();
  }, [fullscreen]);

  useEffect(() => {
    if (!fullscreen || typeof document === "undefined") return undefined;
    const previousOverflow = document.body.style.overflow;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !document.querySelector('dialog[open]')) setFullscreen(false);
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [fullscreen]);

  const findPort = useCallback(
    (nodeId: string, portId: string) => {
      const node = displayTopology.nodes.find((n) => n.id === nodeId);
      return node?.ports.find((p) => p.id === portId);
    },
    [displayTopology.nodes],
  );

  useEffect(() => {
    function move(event: PointerEvent) {
      const activeDrag = activeDragRef.current;
      if (!activeDrag) return;
      event.preventDefault();
      const point = pointFromEvent(event);
      const currentTopology = topologyRef.current;
      if (activeDrag.mode === 'wire' || activeDrag.mode === 'move-bus') {
        const target = surfaceRef.current && findConnectionTarget(surfaceRef.current, event.clientX, event.clientY, activeDrag.mode === 'move-bus');
        const source: ConnectionEndpoint = activeDrag.mode === 'wire'
          ? {kind:'port', nodeId:activeDrag.nodeId, portId:activeDrag.portId} : {kind:'bus', busId:activeDrag.busId};
        try {
          if (target) planNetworkConnection(activeDrag.mode === 'move-bus' ? activeDrag.baseline : currentTopology, source, target, 'preview');
          setConnectionTarget(target);
          setConnectionHint(target ? 'Loslassen, um die Verbindung zu definieren.' : 'Auf einen Port oder eine Buslinie desselben Typs ziehen.');
        } catch (error) {
          setConnectionTarget(null);
          setConnectionHint(error instanceof Error ? error.message : 'Kein passender Anschluss.');
        }
      }
      if (activeDrag.mode === 'move-bus') {
        if (Math.hypot(point.x - activeDrag.startX, point.y - activeDrag.startY) * zoom < 5 && !dragTopologyRef.current && !pendingDragTopologyRef.current) return;
        const delta = activeDrag.portId ? point.y - activeDrag.startY : point.x - activeDrag.startX;
        scheduleDragTopology(moveSceneWire(activeDrag.baseline, activeDrag.busId, activeDrag.coordinate + delta, activeDrag.portId));
      } else if (activeDrag.mode === "move-cluster") {
        if (!dragTopologyRef.current && !pendingDragTopologyRef.current &&
            Math.hypot(point.x - activeDrag.startX, point.y - activeDrag.startY) * zoom < 5) return;
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
        scheduleDragTopology({
          ...currentTopology,
          nodes: currentTopology.nodes.map((node) => {
            const start = startPositions.get(node.id);
            return start ? { ...node, x: start.x + deltaX, y: start.y + deltaY } : node;
          }),
        });
      } else if (activeDrag.mode === "move") {
        const node = currentTopology.nodes.find((item) => item.id === activeDrag.nodeId);
        if (!node) return;
        const isPrimaryGateway = centralGatewayArchitectureRef.current && primaryGatewayFor(currentTopology)?.id === activeDrag.nodeId;
        const nextX = isPrimaryGateway
          ? CANVAS_MARGIN
          : Math.max(CANVAS_MARGIN, point.x - activeDrag.offsetX);
        const nextWidth = isPrimaryGateway
          ? primaryGatewayLayoutWidth(currentTopology, node, horizontalLayoutWidth(currentTopology, surfaceWidth) - CANVAS_MARGIN * 2)
          : node.width;
        scheduleDragTopology({
          ...currentTopology,
          nodes: currentTopology.nodes.map((node) =>
            node.id === activeDrag.nodeId
              ? { ...node, x: nextX, y: Math.max(CANVAS_MARGIN, point.y - activeDrag.offsetY), width: nextWidth }
              : node,
          ),
        });
      } else if (activeDrag.mode === "resize") {
        const node = currentTopology.nodes.find((item) => item.id === activeDrag.nodeId);
        if (!node) return;
        const width = Math.max(NODE_MIN_WIDTH, activeDrag.startWidth + point.x - activeDrag.startX);
        const minimumHeight = nodeContentHeight({ ...node, width, height: undefined });
        const height = Math.max(
          minimumHeight,
          activeDrag.startHeight + point.y - activeDrag.startY,
        );
        scheduleDragTopology({
          ...currentTopology,
          nodes: currentTopology.nodes.map((item) =>
            item.id === node.id ? { ...item, width, height } : item,
          ),
        });
      } else if (activeDrag.mode === "move-port") {
        const node = currentTopology.nodes.find((item) => item.id === activeDrag.nodeId);
        if (!node) return;
        const { side, offset } = nearestPortPlacement(node, point);
        scheduleDragTopology({
          ...currentTopology,
          nodes: currentTopology.nodes.map((item) =>
            item.id === node.id
              ? { ...item, ports: item.ports.map((port) => port.id === activeDrag.portId ? { ...port, side, offset } : port) }
              : item,
          ),
        });
      } else {
        const nextDrag = { ...activeDrag, x: point.x, y: point.y };
        activeDragRef.current = nextDrag;
        setDrag(nextDrag);
      }
    }
    function up(event: PointerEvent) {
      const activeDrag = activeDragRef.current;
      if (!activeDrag) return;
      event.preventDefault();
      if (activeDrag.mode === 'wire') {
        const point = pointFromEvent(event);
        if (Math.hypot(point.x - activeDrag.startX, point.y - activeDrag.startY) * zoom < 4) {
          activeDragRef.current = null;
          setDrag(null); setConnectionTarget(null); setConnectionHint('');
          return;
        }
      }
      const drop = surfaceRef.current && findConnectionTarget(surfaceRef.current, event.clientX, event.clientY, activeDrag.mode === 'move-bus');
      const connecting = activeDrag.mode === 'wire' || (activeDrag.mode === 'move-bus' && drop?.kind === 'port');
      if (connecting) {
        // A connection must not persist the provisional line movement as a layout edit.
        if (dragFrameRef.current) window.cancelAnimationFrame(dragFrameRef.current);
        dragFrameRef.current = 0;
        pendingDragTopologyRef.current = null;
        dragTopologyRef.current = null;
        const currentTopology = activeDrag.mode === 'move-bus' ? activeDrag.baseline : topologyRef.current;
        topologyRef.current = currentTopology;
        const source: ConnectionEndpoint = activeDrag.mode === 'move-bus'
          ? {kind:'bus', busId:activeDrag.busId}
          : {kind:'port', nodeId:activeDrag.nodeId, portId:activeDrag.portId};
        try {
          if (!drop) throw new Error('Kein Anschluss gefunden. Bitte auf einem Port oder einer Buslinie desselben Typs loslassen.');
          const plan = planNetworkConnection(currentTopology, source, drop, nextId('edge'));
          setPortError('');
          setPortMessage('');
          setRelationshipError('');
          setRelationship({edge:plan.edge, connection:{source, target:drop}, isNew:true,
            name:`${plan.sourceName} ↔ ${plan.targetName}`, sourceInterfaceName:plan.networkName,
            targetInterfaceName:plan.networkName, relationType:'CONNECTED_VIA', description:'', direction:'BIDIRECTIONAL'});
        } catch (error) {
          setPortError(error instanceof Error ? error.message : 'Die Verbindung ist nicht möglich.');
        }
      } else {
        flushDragTopology();
      }
      if (activeDrag.mode === "move" || activeDrag.mode === "resize" || activeDrag.mode === "move-port") {
        setSelectedNode(activeDrag.nodeId); setSelectedPort(null); setSelectedBranch(null); setSelectedBus(null);
        setSelectedEdge(null);
      } else if (activeDrag.mode === "move-cluster") {
        const currentTopology = topologyRef.current;
        const profile = topologyClusterProfileFor(currentTopology, routingEntries);
        const clusters = evaClusterLayouts(currentTopology, routingEntries);
        const moved = clusters.find((cluster) => cluster.id === activeDrag.clusterId);
        if (moved) {
          const movedCenter = { x: moved.left + moved.width / 2, y: moved.top + moved.height / 2 };
          const nearest = clusters
            .filter((cluster) => cluster.id !== moved.id)
            .map((cluster) => {
              const center = { x: cluster.left + cluster.width / 2, y: cluster.top + cluster.height / 2 };
              return { cluster, distance: Math.abs(center.x - movedCenter.x) + Math.abs(center.y - movedCenter.y) };
            })
            .sort((left, right) => left.distance - right.distance)[0]?.cluster;
          if (nearest) {
            recordTopologyClusterNeighborLesson(
              activeLayoutProjectId(),
              topologyClusterForText(moved.label, profile).key,
              topologyClusterForText(nearest.label, profile).key,
            );
          }
        }
        setSelectedNode(null);
        setSelectedEdge(null);
      }
      activeDragRef.current = null;
      setConnectionTarget(null);
      setConnectionHint('');
      setDrag(null);
      setDragTopology(null);
    }
    function cancel() {
      if (!activeDragRef.current) return;
      if (dragFrameRef.current) window.cancelAnimationFrame(dragFrameRef.current);
      dragFrameRef.current = 0;
      pendingDragTopologyRef.current = null;
      dragTopologyRef.current = null;
      topologyRef.current = topology;
      activeDragRef.current = null;
      setConnectionTarget(null);
      setConnectionHint('');
      setDragTopology(null);
      setDrag(null);
    }
    function escape(event: KeyboardEvent) { if (event.key === 'Escape') cancel(); }
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener('pointercancel', cancel);
    window.addEventListener('blur', cancel);
    window.addEventListener('keydown', escape);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener('pointercancel', cancel);
      window.removeEventListener('blur', cancel);
      window.removeEventListener('keydown', escape);
    };
  }, [drag, flushDragTopology, scheduleDragTopology, onChange, pointFromEvent, routingEntries, surfaceWidth, topology, zoom]);

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
    setSelectedNode(node.id); setSelectedPort(null); setSelectedBranch(null); setSelectedBus(null);
    setAddMenu(null);
  }

  async function addPort(nodeId: string, bus: BusType) {
    if (portSavePending.current) return;
    const position = menu;
    const sourceNode = topology.nodes.find(node => node.id === nodeId);
    if (!sourceNode) return;
    const nodeName = sourceNode.name;
    const placement = unusedPortPlacement(sourceNode, position ?? { side: "right", offset: 0.5 });
    if (!placement) {
      setPortError("Kein freier Platz am Gerät. Bitte die Karte vergrößern oder vorhandene Ports verschieben.");
      return;
    }
    const next = {
      ...topology,
      nodes: topology.nodes.map((node) => {
        if (node.id !== nodeId) return node;
        return {
          ...node,
          ports: [...node.ports, {
            id: nextId("port"),
            name: busProfiles[bus].label,
            bus,
            side: placement.side,
            offset: placement.offset,
          }],
        };
      }),
    };
    portSavePending.current = true;
    setPortSaving(true);
    setPortError("");
    setPortMessage("");
    try {
      // Port creation changes the physical model, not just canvas coordinates.
      // Keep the previous topology until the canonical save has succeeded.
      if (onRelationshipsChange) {
        const saved = await onRelationshipsChange(next);
        if (saved === false) throw new Error("Port konnte nicht gespeichert werden. Bitte den Modellabgleich prüfen und erneut versuchen.");
      } else {
        onChange(next);
      }
      setSelectedNode(nodeId);
      setSelectedEdge(null);
      setMenu(null);
      setPortMessage(`${busProfiles[bus].label}-Port an „${nodeName}“ ${onRelationshipsChange ? "gespeichert" : "angelegt"}. Zum Verbinden auf einen Port oder Bus desselben Typs ziehen.`);
    } catch (error) {
      setPortError(error instanceof Error ? error.message : "Port konnte nicht gespeichert werden.");
    } finally {
      portSavePending.current = false;
      setPortSaving(false);
    }
  }

  const removeSelected = useCallback(async (explicit?: NetworkSelection) => {
    if (deletePending.current || layoutSaving || portSaving || relationshipSaving || activeDragRef.current) return;
    const selection: NetworkSelection | undefined = explicit ?? (selectedPort ? {kind:'port', ...selectedPort}
      : selectedBranch ? {kind:'branch', ...selectedBranch} : selectedEdge ? {kind:'edge', edgeId:selectedEdge}
      : selectedBus ? {kind:'bus', busId:selectedBus} : selectedNode ? {kind:'node', nodeId:selectedNode} : undefined);
    if (!selection) return;
    const next = deleteNetworkSelection(topology, selection);
    if (next.edges.length === topology.edges.length && next.nodes.length === topology.nodes.length &&
        next.nodes.every((n,i)=>n.ports.length===topology.nodes[i].ports.length)) return;
    deletePending.current = true;
    setDeleting(true); setDeleteError(''); setDeleteMessage(''); setPortError(''); setPortMessage(''); setContextOverlay(null);
    try {
      if (onRelationshipsChange) {
        const saved = await onRelationshipsChange(next);
        if (saved === false) throw new Error('Löschung konnte nicht gespeichert werden. Die Auswahl bleibt erhalten.');
      } else onChange(next);
      setSelectedEdge(null); setSelectedNode(null); setSelectedBus(null); setSelectedPort(null); setSelectedBranch(null);
      setMenu(null);
      setDeleteMessage(selection.kind === 'port' ? 'Port und zugehörige Verbindungen gelöscht.'
        : selection.kind === 'bus' ? 'Buslinien gelöscht. Die Ports bleiben als freie Anschlüsse erhalten.'
        : selection.kind === 'node' ? 'Gerät aus der Netzwerktopologie entfernt.' : 'Verbindung aus der Netzwerktopologie gelöscht.');
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : 'Löschung konnte nicht gespeichert werden.');
    } finally { deletePending.current = false; setDeleting(false); }
  }, [layoutSaving, portSaving, relationshipSaving, topology, selectedPort, selectedBranch, selectedBus, selectedEdge, selectedNode, onRelationshipsChange, onChange]);

  useEffect(() => {
    const remove = (event: KeyboardEvent) => {
      if (event.key !== 'Delete' || event.repeat || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey ||
          (!selectedNode && !selectedEdge && !selectedBus && !selectedPort && !selectedBranch)) return;
      const editable = (element: EventTarget | null) => element instanceof Element &&
        Boolean(element.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"]'));
      if (event.composedPath().some(editable) || editable(document.activeElement) ||
          document.querySelector('dialog[open], [role="dialog"][aria-modal="true"], [role="alertdialog"]')) return;
      event.preventDefault();
      event.stopPropagation();
      void removeSelected();
    };
    window.addEventListener('keydown', remove);
    return () => window.removeEventListener('keydown', remove);
  }, [selectedNode, selectedEdge, selectedBus, selectedPort, selectedBranch, removeSelected]);

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
    if (busChanged && (!busPreview || busPreview.bus !== relationship.bus)) return;
    let connectionPlan: ReturnType<typeof planNetworkConnection> | undefined;
    if (relationship.connection) {
      try {
        connectionPlan = planNetworkConnection(topology, relationship.connection.source, relationship.connection.target, relationship.edge.id);
      } catch (error) {
        setRelationshipError(error instanceof Error ? error.message : 'Die Anschlusszuordnung hat sich geändert.');
        return;
      }
    }
    const sourceInterfaceName = relationship.sourceInterfaceName.trim();
    const targetInterfaceName = relationship.targetInterfaceName.trim();
    const edge: TopologyEdge = {
      ...(connectionPlan?.edge ?? relationship.edge),
      name: relationship.name.trim(),
      sourceInterfaceName,
      targetInterfaceName,
      relationType: relationship.relationType,
      description: relationship.description.trim() || undefined,
      direction: relationship.direction,
    };
    const changedEdges = relationship.isNew
      ? [...topology.edges, edge]
      : topology.edges.map((item) => item.id === edge.id ? edge : item);
    const connectionNodes = connectionPlan?.nodes ?? topology.nodes;
    const interfaceNames = new Map<string, string>();
    const renamedPorts = new Set<string>();
    for (const side of ["source", "target"] as const) {
      const node = connectionNodes.find(item => item.id === edge[side]);
      const endpoint = node?.ports.find(port => port.id === edge[`${side}Port`]);
      for (const port of node?.ports ?? []) {
        if (port.id === endpoint?.id || (endpoint?.hardwareInterfaceId && port.hardwareInterfaceId === endpoint.hardwareInterfaceId)) {
          const nextName = side === 'source' ? sourceInterfaceName : targetInterfaceName;
          interfaceNames.set(port.id, nextName);
          if (nextName !== endpoint?.name) renamedPorts.add(port.id);
        }
      }
    }
    const edges = changedEdges.map(item => {
      const next = { ...item };
      for (const side of ["source", "target"] as const) {
        const name = interfaceNames.get(item[`${side}Port`]);
        if (name) next[`${side}InterfaceName`] = name;
      }
      return next;
    });
    const nodes = connectionNodes.map((node) => ({
      ...node,
      ports: node.ports.map((port) => {
        const name = interfaceNames.get(port.id);
        if (name) return { ...port, name, ...(renamedPorts.has(port.id) ? {nameSource: "user" as const} : {}) };
        return port;
      }),
    }));
    const next = normalizePortSides({ ...topology, nodes, edges });
    setRelationshipSaving(true);
    setRelationshipError("");
    if (!busChanged) onChange(next);
    try {
      const persisted = await onRelationshipsChange?.(next, busChanged && busPreview
        ? { network_id: busPreview.network_id, bus: busPreview.bus, plan_token: busPreview.token, edge } : undefined);
      if (persisted === false) throw new Error("Die Engineering-Relation konnte nicht gespeichert werden.");
      setSelectedEdge(edge.id);
      setSelectedNode(null); setSelectedPort(null); setSelectedBranch(null); setSelectedBus(null);
      setRelationship(null);
    } catch (error) {
      onChange(topology);
      setRelationshipError(error instanceof Error ? error.message : "Die Beziehung konnte nicht gespeichert werden.");
    } finally {
      setRelationshipSaving(false);
    }
  }

  function editRelationship(edge: TopologyEdge) {
    if (deleting || layoutSaving || portSaving || relationshipSaving) return;
    setRelationshipChoices(null);
    setContextOverlay(null);
    setMenu(null);
    setBusTransferOpen(false);
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

  function openBusName(busId: string) {
    if (!onBusRename || deleting || layoutSaving || portSaving || relationshipSaving) return;
    const bus = scene?.buses.find(item => item.id === busId);
    if (bus) {setContextOverlay(null); setBusNameDraft({id: bus.id, name: bus.name});}
  }

  function editBusRelationships(busId: string, portId?: string) {
    if (deleting || layoutSaving || portSaving || relationshipSaving) return;
    const bus = scene?.buses.find(item => item.id === busId);
    if (!bus) return;
    const edges = topology.edges.filter(edge => bus.edgeIds.includes(edge.id)
      && (!portId || edge.sourcePort === portId || edge.targetPort === portId));
    if (edges.length === 1) editRelationship(edges[0]);
    else if (edges.length > 1) {
      setContextOverlay(null);
      setMenu(null);
      setRelationshipChoices({busName: bus.name, edgeIds: edges.map(edge => edge.id)});
    }
  }

  function selectRelationshipBus(bus: BusType) {
    if (!relationship) return;
    const id = relationship.edge.physicalNetworkId;
    const previousName = networkLabel(id, relationship.bus ?? relationship.edge.bus);
    const nextName = networkLabel(id, bus);
    setRelationship({ ...relationship, bus,
      sourceInterfaceName: relationship.sourceInterfaceName === previousName ? nextName : relationship.sourceInterfaceName,
      targetInterfaceName: relationship.targetInterfaceName === previousName ? nextName : relationship.targetInterfaceName });
    setRelationshipError("");
  }

  const connectedPortIds = useMemo(() => new Set(
    displayTopology.edges.flatMap((edge) => [edge.sourcePort, edge.targetPort]),
  ), [displayTopology.edges]);
  const portIsConnected = (portId: string) => connectedPortIds.has(portId);
  const selectedRelationship = displayTopology.edges.find((edge) => edge.id === selectedEdge);
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
  const centralGatewayArchitecture = topology.nodes.length >= LARGE_TOPOLOGY_NODE_THRESHOLD && Boolean(primaryGatewayId);
  useEffect(() => {
    centralGatewayArchitectureRef.current = centralGatewayArchitecture;
  }, [centralGatewayArchitecture]);
  const preparedTopology = useMemo(() => {
    if (topology.scene || !centralGatewayArchitecture || !primaryGatewayId) return topology;
    const primaryGateway = topology.nodes.find((node) => node.id === primaryGatewayId);
    if (!primaryGateway) return topology;
    const nextWidth = primaryGatewayManualSpan(topology, surfaceWidth, primaryGatewayId);
    return nameGatewayInterfaces(orderPortsByConnectedNodes({
      ...topology,
      nodes: topology.nodes.map((node) => {
        if (node.id === primaryGatewayId) return { ...node, x: CANVAS_MARGIN, width: nextWidth };
        if (node.kind === "sensor" || node.kind === "actuator") {
          return {
            ...node,
            width: ENDPOINT_NODE_WIDTH,
            height: endpointNameHeight(node.name),
          };
        }
        return node;
      }),
    }));
  }, [centralGatewayArchitecture, primaryGatewayId, surfaceWidth, topology]);
  const effectiveTopology = useMemo(() => {
    if (!dragTopology) return preparedTopology;
    const movingNodes = new Map(dragTopology.nodes.map((node) => [node.id, node]));
    return {
      ...preparedTopology,
      edges: dragTopology.edges,
      nodes: preparedTopology.nodes.map((node) => {
        const moving = movingNodes.get(node.id);
        return moving ? {
          ...node,
          x: moving.x,
          y: moving.y,
          width: moving.width,
          height: moving.height,
          ports: moving.ports,
        } : node;
      }),
    };
  }, [dragTopology, preparedTopology]);
  const structureSignature = useMemo(
    () => `${topologyStructureSignature(topology)}::${routingGroupSignature(routingEntries)}`,
    [routingEntries, topology],
  );
  const cacheSignature = useMemo(
    () => topologyCacheSignature(topology, routingEntries),
    [routingEntries, topology],
  );
  const topologyLayoutKey = useMemo(() => compactLayoutKey(cacheSignature), [cacheSignature]);
  const layoutSignature = useMemo(() => topologyLayoutSignature(effectiveTopology), [effectiveTopology]);
  const preparedEvaGroups = useMemo(
    () => preparedTopology.scene ? preparedTopology.scene.frames.map(frame => {
      const members = new Map(preparedTopology.nodes.map(n=>[n.id,n]));
      return {anchor: members.get(frame.id)!, processors: [], inputs: frame.memberIds.map(id=>members.get(id)!).filter(n=>n?.kind==="sensor"), outputs: frame.memberIds.map(id=>members.get(id)!).filter(n=>n?.kind==="actuator")};
    }) : buildEvaGroups(preparedTopology, routingEntries),
    [preparedTopology, routingEntries],
  );
  const evaGroups = useMemo(() => {
    if (!dragTopology) return preparedEvaGroups;
    const currentNodes = new Map(effectiveTopology.nodes.map((node) => [node.id, node]));
    const current = (node: TopologyNode) => currentNodes.get(node.id) ?? node;
    return preparedEvaGroups.map((group) => ({
      anchor: current(group.anchor),
      processors: group.processors.map(current),
      inputs: group.inputs.map(current),
      outputs: group.outputs.map(current),
    }));
  }, [dragTopology, effectiveTopology.nodes, preparedEvaGroups]);
  const evaStable = useMemo(
    () => Boolean(scene) || Boolean(dragTopology) || (
      effectiveTopology.nodes.length > 0
      && surfaceWidth > 0
      && !hasLayoutProblems(effectiveTopology, surfaceWidth, routingEntries, evaGroups)
    ),
    [scene, dragTopology, effectiveTopology, evaGroups, routingEntries, surfaceWidth],
  );
  const evaClusters = useMemo(
    () => scene?.frames ?? evaClusterLayouts(effectiveTopology, routingEntries, evaGroups),
    [scene, effectiveTopology, evaGroups, routingEntries],
  );
  const evaDomainClusters = useMemo(
    () => scene?.clusters ?? evaDomainClusterLayouts(effectiveTopology, routingEntries, evaClusters),
    [scene, effectiveTopology, evaClusters, routingEntries],
  );
  const wireClusters = useMemo<WireClusterLayout[]>(
    () => [...evaClusters, ...evaDomainClusters],
    [evaClusters, evaDomainClusters],
  );
  const nodesById = useMemo(() => new Map(effectiveTopology.nodes.map((node) => [node.id, node])), [effectiveTopology.nodes]);
  const searchEntries = useMemo(() => networkSearchEntries(effectiveTopology), [effectiveTopology]);
  const systemFrameByNodeId = useMemo(() => {
    const frames = new Map<string, string>();
    evaGroups.forEach((group) => {
      [group.anchor, ...group.processors, ...group.inputs, ...group.outputs].forEach((node) => {
        frames.set(node.id, group.anchor.name);
      });
    });
    return frames;
  }, [evaGroups]);
  const edgesByPortId = useMemo(() => {
    const ports = new Map<string, TopologyEdge[]>();
    effectiveTopology.edges.forEach((edge) => {
      ports.set(edge.sourcePort, [...(ports.get(edge.sourcePort) ?? []), edge]);
      ports.set(edge.targetPort, [...(ports.get(edge.targetPort) ?? []), edge]);
    });
    return ports;
  }, [effectiveTopology.edges]);
  function overlayPosition(clientX: number, clientY: number) {
    if (typeof window === "undefined") return { x: clientX + 14, y: clientY + 14 };
    return {
      x: Math.max(12, Math.min(clientX + 14, window.innerWidth - 360)),
      y: Math.max(12, Math.min(clientY + 14, window.innerHeight - 260)),
    };
  }

  function showPortOverlay(node: TopologyNode, port: TopologyPort, clientX: number, clientY: number) {
    const connectedEdges = edgesByPortId.get(port.id) ?? [];
    const interfaces = uniqueLabels([
      port.name,
      ...connectedEdges.map((edge) =>
        edge.sourcePort === port.id
          ? relationshipInterfaceName(edge.sourceInterfaceName, node, edge.sourcePort, edge.bus)
          : relationshipInterfaceName(edge.targetInterfaceName, node, edge.targetPort, edge.bus),
      ),
    ]);
    const routes = uniqueLabels(connectedEdges.flatMap((edge) => [
      ...(edge.routingEntryIds ?? []),
      edge.routingEntryId,
      ...Object.values(edge.routingMetadata ?? {}).map((metadata) => metadata.name || metadata.routeCode),
    ]));
    const position = overlayPosition(clientX, clientY);
    setContextOverlay({
      ...position,
      accent: busProfiles[port.bus].color,
      title: `${networkLabel(port.name, port.bus)} Port`,
      subtitle: node.name,
      rows: [
        { label: "Bus", value: busProfiles[port.bus].label },
        { label: "Systemrahmen", value: systemFrameByNodeId.get(node.id) ?? node.name },
        { label: "Interface", value: interfaces.join(" / ") || "Nicht benannt" },
        { label: "Verbindungen", value: connectedEdges.length ? `${connectedEdges.length}` : "Keine" },
      ],
      chips: routes.slice(0, 4),
    });
  }

  function showEdgeOverlay(edge: TopologyEdge, clientX: number, clientY: number) {
    const from = nodesById.get(edge.source);
    const to = nodesById.get(edge.target);
    const sourceInterface = relationshipInterfaceName(edge.sourceInterfaceName, from, edge.sourcePort, edge.bus);
    const targetInterface = relationshipInterfaceName(edge.targetInterfaceName, to, edge.targetPort, edge.bus);
    const frames = uniqueLabels([
      from ? systemFrameByNodeId.get(from.id) ?? from.name : undefined,
      to ? systemFrameByNodeId.get(to.id) ?? to.name : undefined,
    ]);
    const routeLabels = uniqueLabels([
      ...(edge.routingEntryIds ?? []),
      edge.routingEntryId,
      ...Object.values(edge.routingMetadata ?? {}).map((metadata) => metadata.name || metadata.routeCode),
    ]);
    const position = overlayPosition(clientX, clientY);
    setContextOverlay({
      ...position,
      accent: busProfiles[edge.bus].color,
      title: edge.name || `${from?.name ?? edge.source} ↔ ${to?.name ?? edge.target}`,
      subtitle: "Verbindung",
      rows: [
        { label: "Bus", value: busProfiles[edge.bus].label },
        { label: "Systemrahmen", value: frames.join(" → ") || "Nicht zugeordnet" },
        { label: "Interfaces", value: `${sourceInterface} → ${targetInterface}` },
        { label: "Relation", value: `${edge.relationType ?? "CONNECTED_TO"} · ${edge.direction ?? "BIDIRECTIONAL"}` },
      ],
      chips: routeLabels.slice(0, 4),
    });
  }

  const arrangeCurrentTopology = useCallback(() => {
    const next = arrangeTopology(topology, surfaceWidth, routingEntries);
    arrangedStructureRef.current = `${topologyStructureSignature(next)}::${routingGroupSignature(routingEntries)}`;
    // Layout has its own persisted artifact below. Never save an automatic
    // arrangement as a relationship change: that would resynchronize the
    // engineering model, invalidate Capacity/Preflight/Simulation and can loop
    // while a large EVA topology is still settling.
    onChange(next);
  }, [onChange, routingEntries, surfaceWidth, topology]);

  const applyAutoLayout = useCallback(() => {
    arrangeCurrentTopology();
  }, [arrangeCurrentTopology]);

  useEffect(() => {
    if (topology.scene || surfaceWidth <= 0 || topology.nodes.length < 2) return undefined;
    let canceled = false;
    const restore = async () => {
      let cached: CachedNetworkLayout | null = null;
      try {
        const stored = await getWorkflowTopologyLayout(topologyLayoutKey, NETWORK_LAYOUT_VERSION);
        if (stored.nodes.length > 0) cached = cachedNetworkLayout(stored);
      } catch {
        cached = readNetworkLayoutCache(topologyLayoutKey);
      }
      if (!cached) cached = readNetworkLayoutCache(topologyLayoutKey);
      if (canceled) return;
      if (cached) {
        const current = topologyRef.current;
        const restored = applyNetworkLayoutCache(current, cached);
        arrangedStructureRef.current = structureSignature;
        if (topologyLayoutSignature(restored) !== topologyLayoutSignature(current)) {
          onChange(restored);
        }
      }
      setLoadedLayoutKey(topologyLayoutKey);
    };
    void restore();
    return () => {
      canceled = true;
    };
  }, [onChange, structureSignature, surfaceWidth, topology.nodes.length, topologyLayoutKey]);

  useEffect(() => {
    if (topology.scene || loadedLayoutKey !== topologyLayoutKey) return;
    if (drag || surfaceWidth <= 0 || topology.nodes.length < 2) return;
    if (arrangedStructureRef.current === structureSignature) return;
    arrangedStructureRef.current = structureSignature;
    if (!evaStable) arrangeCurrentTopology();
  }, [arrangeCurrentTopology, drag, evaStable, loadedLayoutKey, structureSignature, surfaceWidth, topology.nodes.length, topologyLayoutKey]);

  useEffect(() => {
    if (topology.scene || loadedLayoutKey !== topologyLayoutKey || drag) return undefined;
    if (surfaceWidth <= 0 || topology.nodes.length === 0) return undefined;
    const timeout = window.setTimeout(() => {
      const nodes = workflowLayoutNodes(effectiveTopology);
      writeNetworkLayoutCache(topologyLayoutKey, effectiveTopology);
      void saveWorkflowTopologyLayout(topologyLayoutKey, NETWORK_LAYOUT_VERSION, nodes).catch(() => undefined);
    }, 300);
    return () => window.clearTimeout(timeout);
  }, [drag, effectiveTopology, layoutSignature, loadedLayoutKey, surfaceWidth, topology.nodes.length, topologyLayoutKey]);

  const surfaceHeight = Math.max(
    scene?.height ?? 620,
    ...effectiveTopology.nodes.map((node) => node.y + nodeHeight(node) + CANVAS_EXTRA_SPACE),
  );
  const layoutGuideWidth = scene?.width ?? horizontalLayoutWidth(effectiveTopology, surfaceWidth);
  const canvasWidth = Math.max(
    surfaceWidth + CANVAS_EXTRA_SPACE,
    layoutGuideWidth + CANVAS_EXTRA_SPACE,
    ...effectiveTopology.nodes.map((node) => node.x + nodeWidth(node) + CANVAS_EXTRA_SPACE),
  );
  const layoutStatus = scene ? {
    className: "stable", label: layoutSaving ? "Ansicht wird gespeichert …" : "Gespeicherte Busansicht",
    semantics: "persisted-physical-buses", title: "Gemeinsame physische Busse aus dem gespeicherten Projektstand",
  } : centralGatewayArchitecture
    ? {
        className: "target",
        label: "Zielbild · Fixiert",
        semantics: "displayed-target-state",
        title: "Dargestellter Zielzustand: Positionen, Gruppierung und Gateway-Bus dienen als Referenz fuer weitere Arbeit.",
      }
    : evaStable
      ? {
          className: "stable",
          label: "EVA-Anordnung",
          semantics: "auto-eva-layout",
          title: "Automatische Anordnung anhand bestehender Verbindungsgruppen",
        }
      : {
          className: "pending",
          label: "EVA-Anordnung",
          semantics: "layout-updating",
          title: "Automatische Anordnung wird aktualisiert",
        };

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

  const commitWireAlignmentOffset = useCallback((value: number) => {
    const next = normalizeWireAlignmentOffset(value);
    setWireAlignmentOffsetX(next);
    window.localStorage.setItem(WIRE_ALIGNMENT_OFFSET_STORAGE_KEY, String(next));
  }, []);

  const changeWireAlignmentOffset = useCallback((delta: number) => {
    setWireAlignmentOffsetX((current) => {
      const next = normalizeWireAlignmentOffset(current + delta);
      window.localStorage.setItem(WIRE_ALIGNMENT_OFFSET_STORAGE_KEY, String(next));
      return next;
    });
  }, []);

  const resetWireAlignmentOffset = useCallback(() => {
    commitWireAlignmentOffset(0);
  }, [commitWireAlignmentOffset]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const editingText =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.tagName === "SELECT" ||
        target?.isContentEditable;
      if (editingText || !event.altKey) return;
      if (event.key === "ArrowRight") {
        event.preventDefault();
        changeWireAlignmentOffset(WIRE_ALIGNMENT_STEP);
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        changeWireAlignmentOffset(-WIRE_ALIGNMENT_STEP);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [changeWireAlignmentOffset]);

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

  function focusSearchResult(result: NetworkSearchEntry) {
    const surface = surfaceRef.current;
    if (!surface) return;
    const node = result.kind === 'node' ? nodesById.get(result.id) : undefined;
    const bus = result.kind === 'bus' ? scene?.buses.find(bus => bus.id === result.id) : undefined;
    const edge = result.kind === 'edge' ? effectiveTopology.edges.find(edge => edge.id === result.id) : undefined;
    const from = edge && nodesById.get(edge.source), to = edge && nodesById.get(edge.target);
    // The bus label is a useful anchor even when its full trunk spans many screens.
    const point = node ? { x: node.x + nodeWidth(node) / 2, y: node.y + nodeHeight(node) / 2 }
      : bus ? bus.label : from && to ? { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 } : null;
    if (!point) return;
    setSelectedNode(node?.id ?? null); setSelectedBus(bus?.id ?? null); setSelectedEdge(edge?.id ?? null);
    setSelectedPort(null); setSelectedBranch(null); setMenu(null); setAddMenu(null); setContextOverlay(null);
    setLasso(false); setAssignmentSelection([]);
    let rect = surface.getBoundingClientRect();
    if (Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0) < 140) {
      surface.previousElementSibling?.scrollIntoView({ block: 'start', behavior: 'instant' });
      rect = surface.getBoundingClientRect();
    }
    // In normal mode only part of the tall canvas may be on screen. Center there.
    const visibleTop = Math.max(0, -rect.top);
    const visibleBottom = Math.min(surface.clientHeight, window.innerHeight - rect.top);
    surface.scrollTo({
      left: Math.max(0, point.x * zoom - surface.clientWidth / 2),
      top: Math.max(0, point.y * zoom - (visibleTop + visibleBottom) / 2),
      behavior: 'instant',
    });
  }

  function toggleFullscreen() {
    setFullscreen((current) => {
      const next = !current;
      if (next) {
        requestAnimationFrame(() => requestAnimationFrame(fitCanvas));
      }
      return next;
    });
  }

  const largeTopology = effectiveTopology.nodes.length >= LARGE_TOPOLOGY_NODE_THRESHOLD;
  useEffect(() => {
    if (!largeTopology) {
      setVisibleCanvasBounds(null);
      return undefined;
    }
    const surface = surfaceRef.current;
    if (!surface) return undefined;

    let frame = 0;
    const updateBounds = () => {
      if (frame) window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => {
        const safeZoom = Math.max(MIN_ZOOM, zoom);
        const next = {
          left: Math.max(0, surface.scrollLeft / safeZoom - LARGE_TOPOLOGY_VIEWPORT_OVERSCAN),
          top: Math.max(0, surface.scrollTop / safeZoom - LARGE_TOPOLOGY_VIEWPORT_OVERSCAN),
          right: (surface.scrollLeft + surface.clientWidth) / safeZoom + LARGE_TOPOLOGY_VIEWPORT_OVERSCAN,
          bottom: (surface.scrollTop + surface.clientHeight) / safeZoom + LARGE_TOPOLOGY_VIEWPORT_OVERSCAN,
        };
        setVisibleCanvasBounds((current) => {
          if (
            current
            && Math.abs(current.left - next.left) < 1
            && Math.abs(current.top - next.top) < 1
            && Math.abs(current.right - next.right) < 1
            && Math.abs(current.bottom - next.bottom) < 1
          ) return current;
          return next;
        });
      });
    };

    updateBounds();
    surface.addEventListener("scroll", updateBounds, { passive: true });
    const resizeObserver = new ResizeObserver(updateBounds);
    resizeObserver.observe(surface);
    return () => {
      if (frame) window.cancelAnimationFrame(frame);
      surface.removeEventListener("scroll", updateBounds);
      resizeObserver.disconnect();
    };
  }, [canvasWidth, fullscreen, largeTopology, surfaceHeight, surfaceWidth, zoom]);

  const renderedEvaClusters = useMemo(() => {
    if (!largeTopology || !visibleCanvasBounds) return evaClusters;
    const activeClusterId = drag?.mode === "move-cluster" ? drag.clusterId : null;
    return evaClusters.filter((cluster) => (
      cluster.id === activeClusterId || canvasRectangleIsVisible(cluster, visibleCanvasBounds)
    ));
  }, [drag, evaClusters, largeTopology, visibleCanvasBounds]);
  const renderedEvaDomainClusters = useMemo(() => {
    if (!largeTopology || !visibleCanvasBounds) return evaDomainClusters;
    return evaDomainClusters.filter((cluster) => canvasRectangleIsVisible(cluster, visibleCanvasBounds));
  }, [evaDomainClusters, largeTopology, visibleCanvasBounds]);
  const domainBusJunctions = useMemo(() => new Map(evaDomainClusters.map((domain) => {
    const members = new Set(domain.memberIds);
    const systems = evaClusters
      .filter((cluster) => cluster.memberIds.some((nodeId) => members.has(nodeId)))
      .map((cluster) => ({
        id: cluster.id,
        label: cluster.label,
        left: Math.max(14, Math.min(domain.width - 14, cluster.left + cluster.width / 2 - domain.left)),
      }));
    const gateway = Boolean(primaryGatewayId && effectiveTopology.edges.some((edge) => (
      (edge.source === primaryGatewayId && members.has(edge.target))
      || (edge.target === primaryGatewayId && members.has(edge.source))
    )));
    return [domain.id, { systems, gateway }] as const;
  })), [effectiveTopology.edges, evaClusters, evaDomainClusters, primaryGatewayId]);

  const renderedNodes = useMemo(() => {
    if (!largeTopology) return effectiveTopology.nodes;
    const primary = primaryGatewayId
      ? effectiveTopology.nodes.find((node) => node.id === primaryGatewayId)
      : undefined;
    if (!visibleCanvasBounds) {
      const ordered = primary
        ? [primary, ...effectiveTopology.nodes.filter((node) => node.id !== primary.id)]
        : effectiveTopology.nodes;
      return ordered.slice(0, LARGE_TOPOLOGY_RENDER_BATCH);
    }

    const forcedNodeIds = new Set([selectedNode].filter(Boolean) as string[]);
    if (drag?.mode === "move-cluster") {
      drag.members.forEach((member) => forcedNodeIds.add(member.id));
    } else if (drag && "nodeId" in drag) {
      forcedNodeIds.add(drag.nodeId);
    }
    return effectiveTopology.nodes.filter((node) => forcedNodeIds.has(node.id) || (
      node.x + nodeWidth(node) >= visibleCanvasBounds.left
      && node.x <= visibleCanvasBounds.right
      && node.y + nodeHeight(node) >= visibleCanvasBounds.top
      && node.y <= visibleCanvasBounds.bottom
    ));
  }, [drag, effectiveTopology.nodes, largeTopology, primaryGatewayId, selectedNode, visibleCanvasBounds]);
  const visibleRenderedEdges = useMemo(() => {
    if (scene) return [];
    return effectiveTopology.edges.flatMap((edge) => {
      const from = nodesById.get(edge.source);
      const to = nodesById.get(edge.target);
      const fromPort = from?.ports.find((port) => port.id === edge.sourcePort);
      const toPort = to?.ports.find((port) => port.id === edge.targetPort);
      if (!from || !to || !fromPort || !toPort) return [];
      return [{ edge, path: routedEdgePath(effectiveTopology, edge, from, fromPort, to, toPort, wireClusters) }];
    });
  }, [scene, effectiveTopology, nodesById, wireClusters]);

  const editor = (
    <div className={`net-editor ${scene ? "persisted-scene" : ""} ${largeTopology ? "large-topology" : ""} ${fullscreen ? "fullscreen" : ""}`}>
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
        <NetworkEditorSearch entries={searchEntries} query={searchQuery} onQueryChange={setSearchQuery} onSelect={focusSearchResult} />
        <div className="net-toolbar-actions">
          {scene && onLayoutChange && <button type="button" className="net-add" disabled={layoutSaving || deleting || portSaving || relationshipSaving || Boolean(drag)}
            title="Buslinien und verbundene Anschlusspositionen automatisch führen. Gerätepositionen beibehalten."
            onClick={() => {setLayoutSaving(true); setLayoutError(''); failedLayoutRef.current = null;
              void onLayoutChange(topology, false, true).catch(error => setLayoutError(error instanceof Error ? error.message : 'Linienführung fehlgeschlagen.')).finally(() => setLayoutSaving(false));}}>Linien automatisch</button>}
          {scene && onAssignmentChange && <button type="button" className="net-add" aria-pressed={lasso} onClick={()=>{setLasso(!lasso);setAssignmentSelection([]);setLayoutError('');}} title="Rechteck um Geräte oder Systemrahmen ziehen">{lasso?'Markieren beenden':'Lasso · Zuordnen'}</button>}
          {selectedNode && onAssignmentChange && <button type="button" className="net-add" onClick={()=>setAssignmentSelection([selectedNode])}>Gerät zuordnen</button>}
          <div aria-label="Zoom" className="net-zoom-controls" role="group">
            <button aria-label="Verkleinern" disabled={zoom <= MIN_ZOOM} onClick={() => changeZoom(zoom - ZOOM_STEP)} title="Verkleinern" type="button">−</button>
            <button aria-label="Zoom auf 100 Prozent zurücksetzen" className="net-zoom-value" onClick={() => changeZoom(1)} title="Zoom zurücksetzen" type="button">{Math.round(zoom * 100)} %</button>
            <button aria-label="Vergrößern" disabled={zoom >= MAX_ZOOM} onClick={() => changeZoom(zoom + ZOOM_STEP)} title="Vergrößern" type="button">+</button>
            <button className="net-zoom-fit" onClick={fitCanvas} title="Gesamtes Netzwerk einpassen" type="button">Einpassen</button>
          </div>
          <button
            aria-pressed={fullscreen}
            className="net-add net-fullscreen-toggle"
            onClick={toggleFullscreen}
            title={fullscreen ? "Vollbild schließen (Esc)" : "Netzwerk-Editor im Vollbild öffnen"}
            type="button"
          >
            {fullscreen ? "Vollbild schließen" : "Vollbild"}
          </button>
          <span
            className={`net-eva-status ${layoutStatus.className}`}
            data-layout-semantics={layoutStatus.semantics}
            title={layoutStatus.title}
          >
            <i aria-hidden="true" />
            {layoutStatus.label}
          </span>
          <button className="net-add" type="button" onClick={() => queueEngineeringAgentTask(
            'Prüfe die räumliche Architektur und Gruppierung des aktuellen Projekts anhand der kanonischen Einbauorte, Funktionszuordnungen und tatsächlichen Kommunikationswege. Erstelle bei belegtem Verbesserungsbedarf einen editierbaren Architekturvorschlag. Bestehende Funktionspartner und bestätigte Raumidentitäten erhalten; fehlende Angaben gezielt klären. Eine reine Änderung der Darstellung nicht als Architekturänderung ausgeben.'
          )}>KI-Architekturprüfung</button>
          {onBusRename && scene && <button className="net-add" type="button"
            disabled={(!selectedBus && !selectedBranch && !selectedRelationship?.physicalNetworkId) || deleting || layoutSaving || portSaving || relationshipSaving}
            onClick={() => {const id = selectedBranch?.busId ?? selectedBus ?? selectedRelationship?.physicalNetworkId; if (id) openBusName(id);}}>Bus umbenennen</button>}
          <button className="net-add" type="button"
            disabled={(!selectedBus && !selectedBranch && !selectedEdge) || deleting || layoutSaving || portSaving || relationshipSaving}
            onClick={() => {
              if (selectedBranch) editBusRelationships(selectedBranch.busId, selectedBranch.portId);
              else if (selectedBus) editBusRelationships(selectedBus);
              else {
                const edge = topology.edges.find(item => item.id === selectedEdge);
                if (edge) editRelationship(edge);
              }
            }}>Verbindung bearbeiten</button>
          <button
            className="net-add danger"
            disabled={(!selectedNode && !selectedEdge && !selectedBus && !selectedPort && !selectedBranch) || deleting || layoutSaving || portSaving || relationshipSaving}
            onClick={() => void removeSelected()}
            title="Auswahl löschen (Entf)"
            type="button"
          >
            {deleting ? 'Wird gelöscht …' : 'Auswahl löschen'}
          </button>
          {!scene && !centralGatewayArchitecture && (
            <button
              className="net-add net-eva-action"
              disabled={effectiveTopology.nodes.length < 2}
              onClick={applyAutoLayout}
              title="Zusammenhängende Geräte nach EVA sortieren und gruppieren"
              type="button"
            >
              EVA gruppieren
            </button>
          )}
        </div>
      </div>

      <div
        className={`net-surface${panning ? " is-panning" : ""}`}
        onContextMenu={(event) => event.preventDefault()}
        onPointerDown={(event) => {
          if (event.button !== 0 || activeDragRef.current || (event.target as Element).closest("button, input, select, textarea, a, .net-node")) return;
          event.preventDefault();
          event.currentTarget.setPointerCapture(event.pointerId);
          panRef.current = {pointerId:event.pointerId, x:event.clientX, y:event.clientY, left:event.currentTarget.scrollLeft, top:event.currentTarget.scrollTop};
          setPanning(true);
          setSelectedNode(null);
          setSelectedEdge(null); setSelectedPort(null); setSelectedBranch(null); setSelectedBus(null);
          setMenu(null);
          setAddMenu(null);
          setContextOverlay(null);
        }}
        ref={surfaceRef}
      >
        <div
          className="net-canvas-viewport"
          style={{ height: Math.max(960, surfaceHeight * zoom), width: Math.max(surfaceWidth, canvasWidth * zoom) }}
        >
          <div className="net-canvas" style={{ height: surfaceHeight, transform: `scale(${zoom})`, width: canvasWidth }}>
          {lasso && <NetworkLasso topology={effectiveTopology} zoom={zoom} onSelect={ids=>{setLasso(false);if(ids.length)setAssignmentSelection(ids);else setLayoutError('Keine Geräte markiert. Bitte einen Bereich um Geräte oder Systemrahmen ziehen.');}}/>}
          <div className="net-domain-clusters">
            {renderedEvaDomainClusters.map((cluster) => (
              <div
                className="net-domain-cluster"
                key={cluster.id}
                style={{
                  height: cluster.height,
                  left: cluster.left,
                  top: cluster.top,
                  width: cluster.width,
                }}
              >
                <span>{cluster.label}</span>
                {!scene && <div
                  aria-label={`${cluster.busLabel} mit ${domainBusJunctions.get(cluster.id)?.systems.length ?? 0} Systemknoten`}
                  className="net-domain-bus"
                  role="img"
                >
                  <b>{cluster.busLabel}</b>
                  {(domainBusJunctions.get(cluster.id)?.systems ?? []).map((junction) => (
                    <i
                      className="net-domain-bus-junction"
                      key={junction.id}
                      style={{ left: junction.left }}
                      title={`${junction.label} ist mit ${cluster.busLabel} verbunden`}
                    />
                  ))}
                  {domainBusJunctions.get(cluster.id)?.gateway && (
                    <i
                      className="net-domain-bus-junction gateway"
                      title={`${cluster.busLabel} ist mit dem zentralen Gateway verbunden`}
                    />
                  )}
                </div>}
              </div>
            ))}
          </div>
          <div className="net-eva-clusters">
            {renderedEvaClusters.map((cluster) => (
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
                  aria-label={`Systemrahmen ${cluster.label} verschieben`}
                  className="net-eva-cluster-handle"
                  onDoubleClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    if (!onFrameDeviceCreate || cluster.kind !== 'ecu' || layoutSaving || portSaving || relationshipSaving) return;
                    setMenu(null);
                    setAddMenu(null);
                    setContextOverlay(null);
                    setCreateInFrame({id: cluster.id, label: cluster.label});
                  }}
                  onKeyDown={(event) => {
                    if ((event.key === 'Enter' || event.key === ' ') && onFrameDeviceCreate && cluster.kind === 'ecu' && !layoutSaving && !portSaving && !relationshipSaving) {
                      event.preventDefault();
                      setMenu(null);
                      setCreateInFrame({id: cluster.id, label: cluster.label});
                    }
                  }}
                  onPointerDown={(event) => {
                    if (event.button !== 0 || layoutSaving || portSaving || relationshipSaving) return;
                    event.preventDefault();
                    event.stopPropagation();
                    event.currentTarget.setPointerCapture(event.pointerId);
                    const members = displayTopology.nodes
                      .filter((node) => cluster.memberIds.includes(node.id))
                      .map((node) => ({ id: node.id, x: node.x, y: node.y }));
                    if (members.length === 0) return;
                    const point = pointFromEvent(event);
                    setSelectedNode(null);
                    setSelectedEdge(null);
                    setMenu(null);
                    setAddMenu(null);
                    const nextDrag = {
                      mode: "move-cluster" as const,
                      clusterId: cluster.id,
                      startX: point.x,
                      startY: point.y,
                      members,
                    };
                    activeDragRef.current = nextDrag;
                    setDrag(nextDrag);
                  }}
                  title={`Systemrahmen ${cluster.label}: ziehen zum Verschieben; Doppelklick zum Hinzufügen von ECU, Sensor oder Aktor.`}
                  type="button"
                >
                  <small className="net-system-frame-label">Systemrahmen</small>
                  <strong>{cluster.label}</strong>
                  <span>{cluster.inputs} E</span>
                  <span>{cluster.processors} V</span>
                  <span>{cluster.outputs} A</span>
                </button>
              </div>
            ))}
          </div>
          <svg
            aria-hidden="true"
            className="net-wires"
            preserveAspectRatio="none"
            viewBox={`0 0 ${canvasWidth} ${surfaceHeight}`}
          >
          <g
            className="net-wire-layer"
            data-wire-step={WIRE_ALIGNMENT_STEP.toFixed(1)}
            data-wire-offset-x="0.0"
          >
            {scene?.buses.filter(bus => !visibleCanvasBounds || canvasRectangleIsVisible(bus.bounds, visibleCanvasBounds)).map(bus => (
              <g key={bus.id} className={`net-physical-bus ${selectedBus === bus.id ? 'selected' : ''} ${connectionTarget?.kind === 'bus' && connectionTarget.busId === bus.id ? 'connection-target' : ''}`} data-physical-network-id={bus.id} data-bus-type={bus.technology} onDoubleClick={event => {event.stopPropagation(); editBusRelationships(bus.id);}}>
                <title>{bus.name} · {busProfiles[bus.technology]?.label ?? bus.technology} · {bus.participantCount} Teilnehmer</title>
                <path className="net-wire-hit net-bus-trunk-hit" d={bus.path} onPointerDown={event => beginBusDrag(event, bus)} />
                <path className="net-bus-trunk" d={bus.displayPath ?? bus.path} stroke={busProfiles[bus.technology]?.color ?? "#9fea4e"} />
                <text className="net-bus-label" onDoubleClick={onBusRename ? event => {event.stopPropagation(); openBusName(bus.id);} : undefined} onPointerDown={event => beginBusDrag(event, bus)} textAnchor="end" x={bus.label.x} y={bus.label.y} transform={`rotate(-90 ${bus.label.x} ${bus.label.y})`}>{bus.labelText ?? (bus.local ? `${busProfiles[bus.technology]?.label ?? bus.technology} ${bus.name.match(/(?: |\_)(\d+(?:\.\d+)?)$/)?.[1] ?? bus.id.match(/-S(\d+)$/)?.[1] ?? ""}` : networkLabel(bus.name))}</text>
                {bus.branches.map(branch => {
                  const edge = edgesByPortId.get(branch.portId)?.find(e => bus.edgeIds.includes(e.id));
                  return <g key={`${branch.nodeId}:${branch.portId}`} data-connection-id={edge?.id} data-branch-node-id={branch.nodeId} onPointerDown={event=>{beginBusDrag(event,bus,branch);if(edge && !deleting){setSelectedEdge(edge.id);setSelectedNode(null);}}} onDoubleClick={event=>{event.stopPropagation(); editBusRelationships(bus.id, branch.portId);}}
                    onPointerEnter={event=>{if(activeDragRef.current)return;const node=nodesById.get(branch.nodeId); const port=node?.ports.find(p=>p.id===branch.portId); if(node && port) showPortOverlay(node,port,event.clientX,event.clientY);}}
                    onPointerLeave={()=>setContextOverlay(null)}>
                    <path className="net-wire-hit net-bus-branch-hit" d={branchPath(branch.points)} />
                    <path className={`net-bus-branch ${selectedBranch ? selectedBranch.busId === bus.id && selectedBranch.portId === branch.portId ? 'selected' : '' : edge && selectedEdge === edge.id ? 'selected' : ''}`} d={branch.displayPath ?? branchPath(branch.points)} stroke={busProfiles[bus.technology]?.color ?? "#9fea4e"} />
                  </g>;
                })}
                {busJunctions(bus.branches).map((point,index)=><circle key={index} className="net-bus-junction" cx={point.x} cy={point.y} r="4" fill={busProfiles[bus.technology]?.color ?? "#9fea4e"} />)}
              </g>
            ))}
            {visibleRenderedEdges.map(({ edge, path }) => {
              return (
                <g
                  key={edge.id}
                  onDoubleClick={(event) => {
                    event.stopPropagation();
                    editRelationship(edge);
                  }}
                  onPointerEnter={(event) => showEdgeOverlay(edge, event.clientX, event.clientY)}
                  onPointerLeave={() => setContextOverlay(null)}
                  onPointerDown={(event) => {
                    event.stopPropagation();
                    setContextOverlay(null);
                    if (selectedEdge === edge.id) {
                      editRelationship(edge);
                      return;
                    }
                    setSelectedEdge(edge.id); setSelectedPort(null); setSelectedBranch(null); setSelectedBus(null);
                    setSelectedNode(null);
                    setMenu(null);
                  }}
                >
                  {!largeTopology && <path className="net-wire-hit" d={path} />}
                  <path
                    className={`net-wire ${selectedEdge === edge.id ? "selected" : ""}`}
                    d={path}
                    stroke={busProfiles[edge.bus].color}
                  />
                </g>
              );
            })}
            <g className="net-wire-bridges" aria-hidden="true">
              {scene?.wireBridges?.map((bridge,index) => {
                const bus = scene.buses.find(bus=>bus.id===bridge.busId);
                return <g key={`${bridge.busId}:${index}`} data-bridge-bus-id={bridge.busId}>
                  <path className="net-wire-bridge-mask" d={bridge.path}/>
                  <path className="net-wire-bridge" d={bridge.path} stroke={busProfiles[bus?.technology ?? 'lin'].color}/>
                </g>;
              })}
            </g>
            {drag?.mode === "wire" &&
              (() => {
                const from = effectiveTopology.nodes.find((node) => node.id === drag.nodeId);
                const fromPort = from?.ports.find((p) => p.id === drag.portId);
                if (!from || !fromPort) return null;
                return (
                  <path
                    className="net-wire pending"
                    d={pendingEdgePath(effectiveTopology, from, fromPort, { x: drag.x, y: drag.y })}
                    stroke={busProfiles[drag.bus].color}
                  />
                );
              })()}
          </g>
          </svg>

          {renderedNodes.map((node) => {
          const height = nodeHeight(node);
          const visiblePorts = node.ports;
          return (
            <div
              className={`net-node ${node.kind} eva-${evaRole(node)} ${node.id === primaryGatewayId ? "eva-hub" : ""} ${selectedNode === node.id || assignmentSelection.includes(node.id) ? "selected" : ""}`}
              data-node-id={node.id}
              key={node.id}
              onContextMenu={(event) => {
                event.preventDefault();
                event.stopPropagation();
                setSelectedNode(node.id); setSelectedPort(null); setSelectedBranch(null); setSelectedBus(null);
                setSelectedEdge(null);
                const point = pointFromEvent(event);
                const { side, offset } = nearestPortPlacement(node, point);
                setMenu({ nodeId: node.id, x: point.x, y: point.y, side, offset });
              }}
              onDoubleClick={() => openRenameNode(node.id)}
              onPointerDown={(event) => {
                if (event.button !== 0 || layoutSaving || portSaving || deleting) return;
                event.preventDefault();
                event.stopPropagation();
                event.currentTarget.setPointerCapture(event.pointerId);
                setSelectedPort(null); setSelectedBranch(null); setSelectedBus(null);
                setMenu(null);
                const point = pointFromEvent(event);
                const nextDrag = { mode: "move" as const, nodeId: node.id, offsetX: point.x - node.x, offsetY: point.y - node.y };
                activeDragRef.current = nextDrag;
                setDrag(nextDrag);
              }}
              style={{
                left: node.x,
                top: node.y,
                width: nodeWidth(node),
                height,
                ["--node-height" as string]: `${height}px`,
              }}
            >
              <span className="net-node-kind">
                {kindLabels[node.kind]}{node.id === primaryGatewayId && !scene ? " · EVA-Zentrum" : ""}
              </span>
              {node.engineeringId && (
                <span
                  aria-label="Mit Engineering-Modell verknüpft"
                  className="net-node-model-link"
                  title="Mit Engineering-Modell verknüpft"
                />
              )}
              <strong className="net-node-name">{node.name}</strong>
              {scene && <span className="net-node-bus-types">{[...new Set(node.ports.map(p=>busProfiles[p.bus]?.label ?? p.bus))].join(" · ")}</span>}
              {node.ports.length === 0 && <span className="net-node-empty">Rechtsklick → Port anlegen</span>}
              {visiblePorts.map((port) => {
                const portSide = port.side;
                const compatible =
                  connectionTarget?.kind === 'port' && connectionTarget.portId === port.id;
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
                    aria-label={`${networkLabel(port.name, port.bus)}-Port ${sideLabel[portSide]}`}
                    aria-pressed={selectedPort?.portId === port.id}
                    className={`net-port ${portSide} ${selectedPort?.portId === port.id ? "selected" : ""} ${compatible ? "compatible" : ""} ${portIsConnected(port.id) ? "linked" : ""} ${drag?.mode === "move-port" && drag.portId === port.id ? "dragging" : ""}`}
                    data-node-id={node.id}
                    data-port-bus={port.bus}
                    data-port-id={port.id}
                    key={port.id}
                    onDoubleClick={event => event.stopPropagation()}
                    onBlur={() => setContextOverlay(null)}
                    onContextMenu={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      setSelectedPort({nodeId:node.id,portId:port.id}); setSelectedBranch(null); setSelectedNode(null); setSelectedEdge(null); setSelectedBus(null);
                      void removeSelected({kind:'port',nodeId:node.id,portId:port.id});
                    }}
                    onFocus={(event) => {
                      const rect = event.currentTarget.getBoundingClientRect();
                      showPortOverlay(node, port, rect.right, rect.top);
                    }}
                    onPointerEnter={(event) => {if (!activeDragRef.current) showPortOverlay(node, port, event.clientX, event.clientY);}}
                    onPointerLeave={() => setContextOverlay(null)}
                    onPointerDown={(event) => {
                      if (event.button !== 0 || layoutSaving || portSaving || relationshipSaving || deleting) return;
                      event.preventDefault();
                      event.stopPropagation();
                      event.currentTarget.setPointerCapture(event.pointerId);
                      setMenu(null);
                      setContextOverlay(null);
                      const point = pointFromEvent(event);
                      setSelectedPort({nodeId:node.id,portId:port.id}); setSelectedBranch(null); setSelectedNode(null); setSelectedEdge(null); setSelectedBus(null);
                      const nextDrag = event.shiftKey
                        ? { mode: "move-port" as const, nodeId: node.id, portId: port.id }
                        : { mode: "wire" as const, nodeId: node.id, portId: port.id, bus: port.bus, x: point.x, y: point.y, startX: point.x, startY: point.y };
                      activeDragRef.current = nextDrag;
                      setDrag(nextDrag);
                    }}
                    style={{
                      ...portStyle,
                      ["--bus" as string]: busProfiles[port.bus].color,
                    }}
                    title={`${networkLabel(port.name, port.bus)} · Klicken und Entf zum Löschen · Ziehen zum Verbinden · Shift + Ziehen zum Verschieben · Rechtsklick zum Entfernen`}
                    type="button"
                  />
                );
              })}
              <button
                aria-label={`${node.name} Größe ändern`}
                className="net-node-resize"
                onPointerDown={(event) => {
                  if (event.button !== 0 || layoutSaving) return;
                  event.preventDefault();
                  event.stopPropagation();
                  const point = pointFromEvent(event);
                  setMenu(null);
                  const nextDrag = {
                    mode: "resize" as const,
                    nodeId: node.id,
                    startX: point.x,
                    startY: point.y,
                    startWidth: nodeWidth(node),
                    startHeight: nodeHeight(node),
                  };
                  activeDragRef.current = nextDrag;
                  setDrag(nextDrag);
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
                {portSaving && <p role="status">Port wird gespeichert …</p>}
                {portError && <p role="alert">{portError}</p>}
                {busOrder.map((bus) => (
                  <button
                    className="net-menu-item"
                    key={bus}
                    disabled={portSaving || layoutSaving || relationshipSaving}
                    onClick={() => void addPort(node.id, bus)}
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

      {portSaving && <p className="net-hint" role="status">Port wird im Modell gespeichert …</p>}
      {portMessage && <p className="net-hint" role="status">{portMessage}</p>}
      {connectionHint && <p className="net-hint net-connection-hint" role="status">{connectionHint}</p>}
      {portError && !menu && <p className="net-hint" role="alert">{portError}</p>}
      {deleting && <p className="net-hint" role="status">Auswahl wird gelöscht …</p>}
      {deleteMessage && <p className="net-hint" role="status">{deleteMessage}</p>}
      {deleteError && <p className="net-hint" role="alert">{deleteError}</p>}
      {contextOverlay && (
        <aside
          className="net-context-overlay"
          style={{
            left: contextOverlay.x,
            top: contextOverlay.y,
            ["--bus" as string]: contextOverlay.accent,
          }}
        >
          <header>
            <span>{contextOverlay.subtitle}</span>
            <strong>{contextOverlay.title}</strong>
          </header>
          <dl>
            {contextOverlay.rows.map((row) => (
              <div key={row.label}>
                <dt>{row.label}</dt>
                <dd>{row.value}</dd>
              </div>
            ))}
          </dl>
          {contextOverlay.chips.length > 0 && (
            <div className="net-context-chips">
              {contextOverlay.chips.map((chip) => <span key={chip}>{chip}</span>)}
            </div>
          )}
        </aside>
      )}

      {layoutError && <p role="alert" className="net-scene-error">{layoutError} {failedLayoutRef.current && <button type="button" disabled={layoutSaving} onClick={()=>{if(onLayoutChange && failedLayoutRef.current) {setLayoutSaving(true); void onLayoutChange(failedLayoutRef.current).then(()=>{setLayoutError(""); failedLayoutRef.current = null;}).catch(error=>setLayoutError(error.message)).finally(()=>setLayoutSaving(false));}}}>Speichern erneut versuchen</button>}</p>}
      {scene?.routingWarnings?.map(message => <p key={message} className="net-scene-error" role="status">{message}</p>)}
      {scene && <p className="net-hint"><strong>Linien ziehen:</strong> senkrechte Buslinie seitlich, waagerechten Abzweig nach oben oder unten. Doppelklick auf Linien öffnet die Verbindung, auf Beschriftungen den Busnamen. Escape bricht das Verschieben ab. „Linien automatisch“ ordnet Leitungen und Anschlüsse neu.</p>}
      <p className="net-hint">
        <strong>Lasso · Zuordnen</strong>: Bereich mit gedrückter linker Maustaste markieren, Ziel wählen und bestätigen. Escape beendet das Markieren.{' '}
        Freie Zeichenfläche mit linker Maustaste ziehen zum Navigieren · Karte ziehen zum Verschieben · Doppelklick auf Gerät zum Umbenennen · Doppelklick auf Verbindung zum Bearbeiten · <strong>Port zu einem passenden Port oder Bus ziehen</strong> zum Verdrahten · Buslinie auf einen freien Port ziehen zum Anschließen, sonst zum Verschieben · Shift + Port ziehen zum Versetzen · Rechtsklick auf einen Block legt einen Port an der Klickposition an · Port oder Linie anklicken und Entf drücken zum Löschen · Rechtsklick auf einen Port entfernt ihn.
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
            className="net-rename-dialog net-device-dialog"
            role="dialog"
          >
            <header>
              <div>
                <p className="eyebrow">Netzwerk-Gerät</p>
                <h2 id="net-rename-title">Gerät und Ports</h2>
              </div>
              <button aria-label="Dialog schließen" onClick={() => setRename(null)} type="button">×</button>
            </header>
            <div className="net-device-fields">
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
            <section className="net-device-ports" aria-labelledby="net-device-ports-title">
              <h3 id="net-device-ports-title">Ports <span>{devicePorts.length}</span></h3>
              {devicePorts.length ? (
                <table className="net-device-port-table" aria-labelledby="net-device-ports-title">
                  <thead><tr><th scope="col">Name</th><th scope="col">Technik</th></tr></thead>
                  <tbody>{devicePorts.map(port => (
                    <tr key={port.hardwareInterfaceId || port.id}>
                      <td>{port.name || 'Unbenannter Port'}</td>
                      <td><span className="net-device-port-technology"><i aria-hidden="true" style={{backgroundColor: busProfiles[port.bus].color}} />{busProfiles[port.bus].label}</span></td>
                    </tr>
                  ))}</tbody>
                </table>
              ) : <p className="muted">Für dieses Gerät sind noch keine Ports angelegt.</p>}
            </section>
            </div>
            <footer>
              <button className="button secondary" onClick={() => setRename(null)} type="button">Abbrechen</button>
              <button className="button primary" disabled={!rename.name.trim()} onClick={saveRenamedNode} type="button">Speichern</button>
            </footer>
          </section>
        </div>
      )}
      {assignmentSelection.length>0 && onAssignmentChange && <NetworkAssignmentDialog topology={topology} nodeIds={assignmentSelection} onClose={()=>setAssignmentSelection([])} onApply={onAssignmentChange}/>}
      {createInFrame && onFrameDeviceCreate && <NetworkFrameDeviceDialog frame={createInFrame} onClose={() => setCreateInFrame(null)} onCreate={onFrameDeviceCreate} />}
      {busNameDraft && onBusRename && <NetworkBusNameDialog name={busNameDraft.name}
        onClose={() => setBusNameDraft(null)} onSave={async name => {
          const saved = await onBusRename(busNameDraft.id, name);
          setRelationship(current => {
            if (!current || current.isNew) return current;
            const edge = saved.edges.find(item => item.id === current.edge.id);
            if (!edge) return current;
            const from = saved.nodes.find(node => node.id === edge.source);
            const to = saved.nodes.find(node => node.id === edge.target);
            return {...current, edge,
              sourceInterfaceName: relationshipInterfaceName(edge.sourceInterfaceName, from, edge.sourcePort, edge.bus),
              targetInterfaceName: relationshipInterfaceName(edge.targetInterfaceName, to, edge.targetPort, edge.bus)};
          });
        }} />}
      {relationshipChoices && (
        <div className="net-rename-backdrop" role="presentation" onPointerDown={event => {
          if (event.target === event.currentTarget) setRelationshipChoices(null);
        }}>
          <section className="net-rename-dialog net-relationship-dialog" role="dialog" aria-modal="true"
            aria-labelledby="net-connection-choices-title" onPointerDown={event => event.stopPropagation()}
            onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); setRelationshipChoices(null); } }}>
            <header>
              <div><p className="eyebrow">{relationshipChoices.busName}</p><h2 id="net-connection-choices-title">Verbindung auswählen</h2></div>
              <button autoFocus type="button" aria-label="Dialog schließen" onClick={() => setRelationshipChoices(null)}>×</button>
            </header>
            <p className="net-connection-choice-hint">Dieser Leitungsabschnitt gehört zu mehreren Verbindungen. Welche möchtest du bearbeiten?</p>
            <div className="net-connection-choices">
              {topology.edges.filter(edge => relationshipChoices.edgeIds.includes(edge.id)).map(edge => ({edge,
                endpoints: `${topology.nodes.find(node => node.id === edge.source)?.name ?? edge.source} ↔ ${topology.nodes.find(node => node.id === edge.target)?.name ?? edge.target}`,
              })).sort((a, b) => a.endpoints.localeCompare(b.endpoints, 'de', {numeric: true}) || a.edge.id.localeCompare(b.edge.id))
                .map(({edge, endpoints}) => <button key={edge.id} type="button" onClick={() => editRelationship(edge)}>
                  <strong>{endpoints}</strong><span>{edge.name || 'Verbindung bearbeiten'}</span>
                  <small>{edge.sourceInterfaceName} · {edge.targetInterfaceName}</small>
                </button>)}
            </div>
            <footer><button className="button secondary" type="button" onClick={() => setRelationshipChoices(null)}>Abbrechen</button></footer>
          </section>
        </div>
      )}
      {relationship && (
        <div className="net-rename-backdrop" onPointerDown={(event) => !relationshipSaving && event.target === event.currentTarget && setRelationship(null)} role="presentation">
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
              <div><span>Quelle</span><strong>{topology.nodes.find((node) => node.id === relationship.edge.source)?.name ?? relationship.edge.source}</strong><small>{topology.nodes.find((node) => node.id === relationship.edge.source)?.ports.find((port) => port.id === relationship.edge.sourcePort)?.name ?? ""}</small></div>
              <span aria-hidden="true">→</span>
              <div><span>Ziel</span><strong>{topology.nodes.find((node) => node.id === relationship.edge.target)?.name ?? relationship.edge.target}</strong><small>{topology.nodes.find((node) => node.id === relationship.edge.target)?.ports.find((port) => port.id === relationship.edge.targetPort)?.name ?? ""}</small></div>
            </div>
            <div className="net-relationship-fields">
              <label className="full-width"><span>Name</span><input autoFocus onChange={(event) => setRelationship({ ...relationship, name: event.target.value })} value={relationship.name} /></label>
              <label><span>Beziehungstyp</span><select onChange={(event) => setRelationship({ ...relationship, relationType: event.target.value as RelationshipDraft["relationType"] })} value={relationship.relationType}><option value="CONNECTED_TO">Physisch verbunden · CONNECTED_TO</option><option value="COMMUNICATES_WITH">Kommuniziert mit · COMMUNICATES_WITH</option><option value="CONNECTED_VIA">Über Bus verbunden · CONNECTED_VIA</option></select></label>
              <label><span>Richtung</span><select onChange={(event) => setRelationship({ ...relationship, direction: event.target.value as RelationshipDraft["direction"] })} value={relationship.direction}><option value="BIDIRECTIONAL">Bidirektional</option><option value="SOURCE_TO_TARGET">Quelle → Ziel</option><option value="TARGET_TO_SOURCE">Ziel → Quelle</option></select></label>
              <label><span>Quell-Interface</span><input onChange={(event) => setRelationship({ ...relationship, sourceInterfaceName: event.target.value })} value={relationship.sourceInterfaceName} /></label>
              <label><span>Ziel-Interface</span><input onChange={(event) => setRelationship({ ...relationship, targetInterfaceName: event.target.value })} value={relationship.targetInterfaceName} /></label>
              <label><span>Bustyp</span><select disabled={relationshipSaving || relationship.isNew || !relationship.edge.physicalNetworkId} onChange={(event) => selectRelationshipBus(event.target.value as BusType)} value={relationship.bus ?? relationship.edge.bus}>{busOrder.map(bus => <option key={bus} value={bus}>{busProfiles[bus].label}</option>)}</select></label>
              {relationship.connection && <div className="full-width"><span>Zielbus</span><strong>{relationship.edge.physicalNetworkName}</strong></div>}
              {onAssignmentChange && topology.scene && relationship.edge.physicalNetworkId && !relationship.isNew && <div className="net-transfer-entry"><span>Physischer Bus</span><strong>{topology.scene.buses.find(b => b.id === relationship.edge.physicalNetworkId)?.name ?? relationship.edge.physicalNetworkId}</strong>{onBusRename && <button className="button secondary" type="button" disabled={relationshipSaving || busChanged || relationshipModified} onClick={() => openBusName(relationship.edge.physicalNetworkId!)}>Bus umbenennen</button>}<button className="button secondary" type="button" disabled={relationshipSaving || busChanged || relationshipModified} onClick={() => setBusTransferOpen(true)}>Bus umhängen …</button>{(busChanged || relationshipModified) && <small>Änderungen an der Beziehung zuerst übernehmen.</small>}</div>}
              {!relationship.edge.physicalNetworkId && <p className="full-width muted">Verbindung zuerst speichern, um den physischen Bustyp zu ändern.</p>}
              {busChanged && <div className="full-width notice" role="status">{busPreviewError || (busPreview && busPreview.bus === relationship.bus ? <><strong>Buswechsel auf {busProfiles[relationship.bus!].label}</strong><p>{busPreview.networks.map(n => n.name).join(" · ")}</p><p>{busPreview.devices} Geräte · {busPreview.messages} Nachrichten · {busPreview.routes} Routen. Gemeinsam genutzte Nachrichten werden auf allen zugehörigen Bussen umgestellt. Betroffene Routen benötigen danach eine erneute Freigabe.</p></> : "Betroffene Busse und Nachrichten werden geprüft …")}</div>}
              <label className="full-width"><span>Beschreibung</span><textarea onChange={(event) => setRelationship({ ...relationship, description: event.target.value })} placeholder="Technischer Zweck, Randbedingungen oder Verantwortlichkeit" rows={3} value={relationship.description} /></label>
            </div>
            {relationshipError && <div className="notice error net-relationship-error" role="alert">{relationshipError}</div>}
            <footer>
              <button className="button secondary" disabled={relationshipSaving} onClick={() => setRelationship(null)} type="button">Abbrechen</button>
              <button className="button primary" disabled={relationshipSaving || (busChanged && (!busPreview || busPreview.bus !== relationship.bus || Boolean(busPreviewError))) || !relationship.name.trim() || !relationship.sourceInterfaceName.trim() || !relationship.targetInterfaceName.trim()} onClick={() => void saveRelationship()} type="button">{relationshipSaving ? "Wird gespeichert …" : "Beziehung übernehmen"}</button>
            </footer>
          </section>
        </div>
      )}
      {relationship && busTransferOpen && onAssignmentChange && <NetworkBusTransferDialog topology={topology} edge={relationship.edge}
        onClose={() => setBusTransferOpen(false)} onApply={async request => {
          await onAssignmentChange(request);
          setBusTransferOpen(false); setRelationship(null); setSelectedEdge(null);
        }} />}
    </div>
  );

  return fullscreen && typeof document !== "undefined"
    ? createPortal(editor, document.body)
    : editor;
}
