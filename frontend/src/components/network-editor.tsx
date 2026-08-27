"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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
import type { HardwareNode } from "@/lib/types";
import { setWorkflowContext } from "@/lib/workflow-api";

const NODE_DEFAULT_WIDTH = 168;
const NODE_MIN_WIDTH = 140;
const NODE_MIN_HEIGHT = 84;
const PORT_OFFSET = 12;
const PORT_SAFE_INSET = 18;
const MENU_WIDTH = 210;
const MENU_EDGE_GAP = 8;
const CANVAS_MARGIN = 36;
const COLUMN_GAP = 250;
const RIGHT_COLUMN_SAFE_GAP = 140;
const CANVAS_EXTRA_SPACE = 320;

const kindLabels: Record<NodeKind, string> = {
  ecu: "ECU",
  gateway: "Gateway",
  sensor: "Sensor",
  actuator: "Aktor",
};

const busOrder: BusType[] = ["can_fd", "lin", "automotive_ethernet", "flexray"];

type DragState =
  | { mode: "move"; nodeId: string; offsetX: number; offsetY: number }
  | { mode: "resize"; nodeId: string; startX: number; startY: number; startWidth: number; startHeight: number }
  | { mode: "move-port"; nodeId: string; portId: string }
  | { mode: "wire"; nodeId: string; portId: string; bus: BusType; x: number; y: number };

type MenuState = { nodeId: string; x: number; y: number; side: PortSide; offset: number };

let counter = 0;
const nextId = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${(counter++).toString(36)}`;

function nodeWidth(node: TopologyNode) {
  return Math.max(NODE_MIN_WIDTH, node.width ?? NODE_DEFAULT_WIDTH);
}

function nodeContentHeight(node: TopologyNode) {
  const charactersPerLine = Math.max(10, Math.floor((nodeWidth(node) - 32) / 8));
  const nameLines = Math.max(1, Math.ceil(node.name.length / charactersPerLine));
  const contentHeight = node.ports.length === 0 ? 86 : 66;
  return Math.max(
    NODE_MIN_HEIGHT,
    contentHeight + (nameLines - 1) * 18 + Math.ceil(node.ports.length / 2) * 12,
  );
}

function nodeHeight(node: TopologyNode) {
  return Math.max(nodeContentHeight(node), node.height ?? NODE_MIN_HEIGHT);
}

function portTop(node: TopologyNode, port: TopologyPort) {
  const height = nodeHeight(node);
  return PORT_SAFE_INSET + Math.max(0, Math.min(1, port.offset ?? 0.5)) * (height - PORT_SAFE_INSET * 2);
}

function connectedPortSide(topology: NetworkTopology, node: TopologyNode, port: TopologyPort): PortSide {
  const nodeCenter = node.x + nodeWidth(node) / 2;
  const connectedCenters = topology.edges.flatMap((edge) => {
    const usesSource = edge.source === node.id && edge.sourcePort === port.id;
    const usesTarget = edge.target === node.id && edge.targetPort === port.id;
    if (!usesSource && !usesTarget) return [];
    const otherId = usesSource ? edge.target : edge.source;
    const other = topology.nodes.find((item) => item.id === otherId);
    return other ? [other.x + nodeWidth(other) / 2] : [];
  });
  if (!connectedCenters.length) return port.side;
  const averageOtherCenter = connectedCenters.reduce((sum, value) => sum + value, 0) / connectedCenters.length;
  return averageOtherCenter < nodeCenter ? "left" : "right";
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

function portPosition(topology: NetworkTopology, node: TopologyNode, port: TopologyPort) {
  const side = connectedPortSide(topology, node, port);
  return {
    side,
    x: side === "left" ? node.x : node.x + nodeWidth(node),
    y: node.y + portTop(node, port),
  };
}

function edgeLaneOffset(topology: NetworkTopology, edge: TopologyEdge, from: TopologyNode, to: TopologyNode) {
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
    .sort((left, right) => left.id.localeCompare(right.id));
  const index = peers.findIndex((candidate) => candidate.id === edge.id);
  const centeredIndex = index < 0 ? 0 : index - (peers.length - 1) / 2;
  const direction = from.y <= to.y ? 1 : -1;
  return direction * Math.max(-28, Math.min(28, centeredIndex * 14));
}

function routedEdgePath(topology: NetworkTopology, edge: TopologyEdge, from: TopologyNode, fromPort: TopologyPort, to: TopologyNode, toPort: TopologyPort) {
  const start = portPosition(topology, from, fromPort);
  const end = portPosition(topology, to, toPort);
  const startDirection = start.side === "right" ? 1 : -1;
  const endDirection = end.side === "right" ? 1 : -1;
  const routeOffset = 72;
  const laneOffset = edgeLaneOffset(topology, edge, from, to);
  const laneX = start.side === end.side
    ? start.side === "right"
      ? Math.max(from.x + nodeWidth(from), to.x + nodeWidth(to)) + routeOffset + Math.abs(laneOffset)
      : Math.min(from.x, to.x) - routeOffset - Math.abs(laneOffset)
    : (start.x + end.x) / 2 + laneOffset;
  const startLaneY = start.y + laneOffset;
  const endLaneY = end.y - laneOffset;
  const startStubX = start.x + startDirection * 28;
  const endStubX = end.x + endDirection * 28;
  return [
    `M ${start.x} ${start.y}`,
    `L ${startStubX} ${start.y}`,
    `L ${startStubX} ${startLaneY}`,
    `L ${laneX} ${startLaneY}`,
    `L ${laneX} ${endLaneY}`,
    `L ${endStubX} ${endLaneY}`,
    `L ${endStubX} ${end.y}`,
    `L ${end.x} ${end.y}`,
  ].join(" ");
}

function pendingEdgePath(topology: NetworkTopology, from: TopologyNode, fromPort: TopologyPort, to: { x: number; y: number }) {
  const start = portPosition(topology, from, fromPort);
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

function hasLayoutProblems(topology: NetworkTopology, surfaceWidth: number) {
  const rightLimit = Math.max(720, surfaceWidth) - CANVAS_MARGIN;
  if (topology.nodes.some((node) => node.x < 0 || node.y < 0 || node.x + nodeWidth(node) > rightLimit)) return true;
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

function arrangeTopology(topology: NetworkTopology, surfaceWidth: number): NetworkTopology {
  const width = Math.max(1180, surfaceWidth);
  const gateways = topology.nodes
    .filter((node) => node.kind === "gateway")
    .sort((a, b) => nodeDegree(topology, b.id) - nodeDegree(topology, a.id));
  const primaryGateway = gateways[0];
  const sensorX = CANVAS_MARGIN + 22;
  const leftX = sensorX + 220;
  const centerX = Math.max(leftX + COLUMN_GAP, Math.round(width / 2 - NODE_DEFAULT_WIDTH / 2));
  const rightX = Math.max(centerX + COLUMN_GAP, width - NODE_DEFAULT_WIDTH - RIGHT_COLUMN_SAFE_GAP);
  const sensorNodes: TopologyNode[] = [];
  const leftNodes: TopologyNode[] = [];
  const rightNodes: TopologyNode[] = [];
  const centerNodes = gateways;

  topology.nodes
    .filter((node) => node.kind !== "gateway")
    .forEach((node) => {
      if (node.kind === "sensor") {
        sensorNodes.push(node);
        return;
      }
      const toGateway = primaryGateway
        ? topology.edges.filter((edge) =>
            (edge.source === node.id && edge.target === primaryGateway.id) ||
            (edge.target === node.id && edge.source === primaryGateway.id),
          ).length
        : 0;
      if (node.kind === "actuator" || !toGateway) rightNodes.push(node);
      else leftNodes.push(node);
    });

  const rowY = (index: number, total: number) => 56 + index * 128 + Math.max(0, 2 - total) * 34;
  const moveNode = (node: TopologyNode, x: number, y: number): TopologyNode => {
    const nextCenter = x + nodeWidth(node) / 2;
    return {
      ...node,
      x,
      y,
      ports: node.ports.map((port) => ({
        ...port,
        side: nextCenter < centerX + NODE_DEFAULT_WIDTH / 2 ? "right" : "left",
      })),
    };
  };

  const arranged = new Map<string, TopologyNode>();
  sensorNodes.forEach((node, index) => arranged.set(node.id, moveNode(node, sensorX, rowY(index, sensorNodes.length))));
  leftNodes.forEach((node, index) => arranged.set(node.id, moveNode(node, leftX, rowY(index, leftNodes.length))));
  centerNodes.forEach((node, index) => arranged.set(node.id, moveNode(node, centerX, rowY(index, centerNodes.length))));
  rightNodes.forEach((node, index) => arranged.set(node.id, moveNode(node, rightX, rowY(index, rightNodes.length))));

  return normalizePortSides({
    ...topology,
    nodes: topology.nodes.map((node) => arranged.get(node.id) ?? node),
  });
}

export function NetworkEditor({
  topology,
  modelHardware,
  onChange,
  onRelationshipsChange,
}: {
  topology: NetworkTopology;
  modelHardware: HardwareNode[];
  onChange: (next: NetworkTopology) => void;
  onRelationshipsChange?: (next: NetworkTopology) => void;
}) {
  const surfaceRef = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<DragState | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);
  const [menu, setMenu] = useState<MenuState | null>(null);
  const [addMenu, setAddMenu] = useState<NodeKind | null>(null);
  const [rename, setRename] = useState<{ nodeId: string; name: string } | null>(null);
  const [surfaceWidth, setSurfaceWidth] = useState(1100);
  const [autoArranged, setAutoArranged] = useState(false);

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
      x: event.clientX - (rect?.left ?? 0) + (surface?.scrollLeft ?? 0),
      y: event.clientY - (rect?.top ?? 0) + (surface?.scrollTop ?? 0),
    };
  }, []);

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
      if (activeDrag.mode === "move") {
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
        const height = nodeHeight(node);
        const side: PortSide = point.x < node.x + nodeWidth(node) / 2 ? "left" : "right";
        const offset = Math.max(0, Math.min(1, (point.y - node.y - PORT_SAFE_INSET) / (height - PORT_SAFE_INSET * 2)));
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
            commitRelationships(normalizePortSides({
              ...topology,
              edges: [
                ...topology.edges,
                {
                  id: nextId("edge"),
                  source: activeDrag.nodeId,
                  sourcePort: activeDrag.portId,
                  target: targetNodeId,
                  targetPort: targetPortId,
                  bus: activeDrag.bus,
                },
              ],
            }));
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

  const portIsConnected = (portId: string) =>
    topology.edges.some((edge) => edge.sourcePort === portId || edge.targetPort === portId);
  const applyAutoLayout = useCallback(() => {
    const next = arrangeTopology(topology, surfaceWidth);
    commitRelationships(next);
    setAutoArranged(true);
  }, [commitRelationships, surfaceWidth, topology]);

  useEffect(() => {
    if (autoArranged || drag || surfaceWidth <= 0 || topology.nodes.length < 6) return;
    if (hasLayoutProblems(topology, surfaceWidth)) applyAutoLayout();
  }, [applyAutoLayout, autoArranged, drag, surfaceWidth, topology]);

  const surfaceHeight = Math.max(
    620,
    ...topology.nodes.map((node) => node.y + nodeHeight(node) + CANVAS_EXTRA_SPACE),
  );
  const canvasWidth = Math.max(
    surfaceWidth + CANVAS_EXTRA_SPACE,
    ...topology.nodes.map((node) => node.x + nodeWidth(node) + CANVAS_EXTRA_SPACE),
  );

  return (
    <div className="net-editor">
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
        <button
          className="net-add danger"
          disabled={!selectedNode && !selectedEdge}
          onClick={removeSelected}
          type="button"
        >
          Auswahl löschen
        </button>
        <button
          className="net-add"
          disabled={topology.nodes.length < 2}
          onClick={applyAutoLayout}
          type="button"
        >
          Ansicht aufräumen
        </button>
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
        <div className="net-canvas" style={{ height: surfaceHeight, width: canvasWidth }}>
          <svg aria-hidden="true" className="net-wires">
          {topology.edges.map((edge) => {
            const from = topology.nodes.find((node) => node.id === edge.source);
            const to = topology.nodes.find((node) => node.id === edge.target);
            const fromPort = from?.ports.find((p) => p.id === edge.sourcePort);
            const toPort = to?.ports.find((p) => p.id === edge.targetPort);
            if (!from || !to || !fromPort || !toPort) return null;
            return (
              <path
                className={`net-wire ${selectedEdge === edge.id ? "selected" : ""}`}
                d={routedEdgePath(topology, edge, from, fromPort, to, toPort)}
                key={edge.id}
                onPointerDown={(event) => {
                  event.stopPropagation();
                  setSelectedEdge(edge.id);
                  setSelectedNode(null);
                  setMenu(null);
                }}
                stroke={busProfiles[edge.bus].color}
              />
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
          return (
            <div
              className={`net-node ${node.kind} ${selectedNode === node.id ? "selected" : ""}`}
              data-node-id={node.id}
              key={node.id}
              onContextMenu={(event) => {
                event.preventDefault();
                event.stopPropagation();
                setSelectedNode(node.id);
                setSelectedEdge(null);
                const point = pointFromEvent(event);
                const height = nodeHeight(node);
                const side: PortSide = point.x < node.x + nodeWidth(node) / 2 ? "left" : "right";
                const offset = Math.max(0, Math.min(1, (point.y - node.y - PORT_SAFE_INSET) / (height - PORT_SAFE_INSET * 2)));
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
              <span className="net-node-kind">{kindLabels[node.kind]}</span>
              {node.engineeringId && (
                <span
                  aria-label="Mit Engineering-Modell verknüpft"
                  className="net-node-model-link"
                  title="Mit Engineering-Modell verknüpft"
                />
              )}
              <strong className="net-node-name">{node.name}</strong>
              {node.ports.length === 0 && <span className="net-node-empty">Rechtsklick → Port anlegen</span>}
              {node.ports.map((port) => {
                const portSide = connectedPortSide(topology, node, port);
                const compatible =
                  drag?.mode === "wire" && drag.bus === port.bus && drag.nodeId !== node.id && !portIsConnected(port.id);
                return (
                  <button
                    aria-label={`${port.name}-Port ${portSide === "left" ? "links" : "rechts"}`}
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
                      [portSide === "left" ? "left" : "right"]: -PORT_OFFSET,
                      top: portTop(node, port),
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

      <p className="net-hint">
        Karte ziehen zum Verschieben · Doppelklick zum Umbenennen · <strong>Port zu einem gleichfarbigen Port ziehen</strong> zum Verdrahten · Shift + Port ziehen zum Versetzen · Rechtsklick auf einen Block legt einen Port an der Klickposition an · Rechtsklick auf einen Port entfernt ihn.
      </p>
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
    </div>
  );
}
