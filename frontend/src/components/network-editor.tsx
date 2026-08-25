"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  busProfiles,
  engineeringHardwareKind,
  initialTopology,
  type BusType,
  type NetworkTopology,
  type NodeKind,
  type PortSide,
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

function portPosition(node: TopologyNode, port: TopologyPort) {
  return {
    x: port.side === "left" ? node.x : node.x + nodeWidth(node),
    y: node.y + portTop(node, port),
  };
}

function edgePath(from: { x: number; y: number }, to: { x: number; y: number }) {
  const dx = Math.abs(to.x - from.x) * 0.5 + 24;
  return `M ${from.x} ${from.y} C ${from.x + dx} ${from.y}, ${to.x - dx} ${to.y}, ${to.x} ${to.y}`;
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
    return { x: event.clientX - (rect?.left ?? 0), y: event.clientY - (rect?.top ?? 0) };
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
        onChange({
          ...topology,
          nodes: topology.nodes.map((node) =>
            node.id === activeDrag.nodeId
              ? { ...node, x: Math.max(0, point.x - activeDrag.offsetX), y: Math.max(0, point.y - activeDrag.offsetY) }
              : node,
          ),
        });
      } else if (activeDrag.mode === "resize") {
        const node = topology.nodes.find((item) => item.id === activeDrag.nodeId);
        if (!node) return;
        const maxWidth = Math.max(
          NODE_MIN_WIDTH,
          (surfaceRef.current?.clientWidth ?? 1200) - node.x - MENU_EDGE_GAP,
        );
        const width = Math.min(
          maxWidth,
          Math.max(NODE_MIN_WIDTH, activeDrag.startWidth + point.x - activeDrag.startX),
        );
        const minimumHeight = nodeContentHeight({ ...node, width, height: undefined });
        const height = Math.max(
          minimumHeight,
          activeDrag.startHeight + point.y - activeDrag.startY,
        );
        onChange({
          ...topology,
          nodes: topology.nodes.map((item) =>
            item.id === node.id ? { ...item, width, height } : item,
          ),
        });
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
            commitRelationships({
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
    const extraIndex = Math.max(0, topology.nodes.length - initialTopology.nodes.length);
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

  function renameNode(id: string) {
    const current = topology.nodes.find((node) => node.id === id);
    const name = window.prompt("Gerätename", current?.name ?? "");
    if (name && name.trim()) {
      onChange({ ...topology, nodes: topology.nodes.map((node) => (node.id === id ? { ...node, name: name.trim() } : node)) });
    }
  }

  const portIsConnected = (portId: string) =>
    topology.edges.some((edge) => edge.sourcePort === portId || edge.targetPort === portId);
  const surfaceHeight = Math.max(
    480,
    ...topology.nodes.map((node) => node.y + nodeHeight(node) + 60),
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
        style={{ height: surfaceHeight }}
      >
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
                d={edgePath(portPosition(from, fromPort), portPosition(to, toPort))}
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
                  d={edgePath(portPosition(from, fromPort), { x: drag.x, y: drag.y })}
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
              onDoubleClick={() => renameNode(node.id)}
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
                const compatible =
                  drag?.mode === "wire" && drag.bus === port.bus && drag.nodeId !== node.id && !portIsConnected(port.id);
                return (
                  <button
                    aria-label={`${port.name}-Port ${port.side === "left" ? "links" : "rechts"}`}
                    className={`net-port ${port.side} ${compatible ? "compatible" : ""} ${portIsConnected(port.id) ? "linked" : ""} ${drag?.mode === "move-port" && drag.portId === port.id ? "dragging" : ""}`}
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
                      [port.side === "left" ? "left" : "right"]: -PORT_OFFSET,
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
                      (surfaceRef.current?.clientWidth ?? MENU_WIDTH + MENU_EDGE_GAP * 2) - MENU_WIDTH - MENU_EDGE_GAP,
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

      <p className="net-hint">
        Karte ziehen zum Verschieben · Doppelklick zum Umbenennen · <strong>Port zu einem gleichfarbigen Port ziehen</strong> zum Verdrahten · Shift + Port ziehen zum Versetzen · Rechtsklick auf einen Block legt einen Port an der Klickposition an · Rechtsklick auf einen Port entfernt ihn.
      </p>
    </div>
  );
}

export { initialTopology };
