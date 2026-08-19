"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  busProfiles,
  initialTopology,
  type BusType,
  type NetworkTopology,
  type NodeKind,
  type PortSide,
  type TopologyNode,
  type TopologyPort,
} from "@/lib/topology";

const NODE_WIDTH = 168;
const NODE_MIN_HEIGHT = 84;
const PORT_OFFSET = 12;
const PORT_SAFE_INSET = 18;

const kindLabels: Record<NodeKind, string> = {
  ecu: "ECU",
  gateway: "Gateway",
  sensor: "Sensor",
  actuator: "Aktor",
};

const busOrder: BusType[] = ["can_fd", "lin", "automotive_ethernet", "flexray"];

type DragState =
  | { mode: "move"; nodeId: string; offsetX: number; offsetY: number }
  | { mode: "move-port"; nodeId: string; portId: string }
  | { mode: "wire"; nodeId: string; portId: string; bus: BusType; x: number; y: number };

type MenuState = { nodeId: string; x: number; y: number; side: PortSide; offset: number };

let counter = 0;
const nextId = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${(counter++).toString(36)}`;

function nodeHeight(node: TopologyNode) {
  return Math.max(NODE_MIN_HEIGHT, 70 + Math.ceil(node.ports.length / 2) * 12);
}

function portTop(node: TopologyNode, port: TopologyPort) {
  const height = nodeHeight(node);
  return PORT_SAFE_INSET + Math.max(0, Math.min(1, port.offset ?? 0.5)) * (height - PORT_SAFE_INSET * 2);
}

function portPosition(node: TopologyNode, port: TopologyPort) {
  return {
    x: port.side === "left" ? node.x : node.x + NODE_WIDTH,
    y: node.y + portTop(node, port),
  };
}

function edgePath(from: { x: number; y: number }, to: { x: number; y: number }) {
  const dx = Math.abs(to.x - from.x) * 0.5 + 24;
  return `M ${from.x} ${from.y} C ${from.x + dx} ${from.y}, ${to.x - dx} ${to.y}, ${to.x} ${to.y}`;
}

export function NetworkEditor({
  topology,
  onChange,
}: {
  topology: NetworkTopology;
  onChange: (next: NetworkTopology) => void;
}) {
  const surfaceRef = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<DragState | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);
  const [menu, setMenu] = useState<MenuState | null>(null);

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
      } else if (activeDrag.mode === "move-port") {
        const node = topology.nodes.find((item) => item.id === activeDrag.nodeId);
        if (!node) return;
        const height = nodeHeight(node);
        const side: PortSide = point.x < node.x + NODE_WIDTH / 2 ? "left" : "right";
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
            onChange({
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
  }, [drag, topology, onChange, pointFromEvent]);

  useEffect(() => {
    if (!menu) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setMenu(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menu]);

  function addNode(kind: NodeKind) {
    const node: TopologyNode = {
      id: nextId(kind),
      name: `${kindLabels[kind]} ${topology.nodes.filter((item) => item.kind === kind).length + 1}`,
      kind,
      x: 60 + topology.nodes.length * 24,
      y: 60 + topology.nodes.length * 18,
      ports: [],
    };
    onChange({ ...topology, nodes: [...topology.nodes, node] });
    setSelectedNode(node.id);
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
    onChange({
      nodes: topology.nodes.map((node) =>
        node.id === nodeId ? { ...node, ports: node.ports.filter((p) => p.id !== portId) } : node,
      ),
      edges: topology.edges.filter((edge) => edge.sourcePort !== portId && edge.targetPort !== portId),
    });
  }

  function removeSelected() {
    if (selectedEdge) {
      onChange({ ...topology, edges: topology.edges.filter((edge) => edge.id !== selectedEdge) });
      setSelectedEdge(null);
      return;
    }
    if (selectedNode) {
      onChange({
        nodes: topology.nodes.filter((node) => node.id !== selectedNode),
        edges: topology.edges.filter((edge) => edge.source !== selectedNode && edge.target !== selectedNode),
      });
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

  return (
    <div className="net-editor">
      <div className="net-toolbar">
        <div className="net-palette" role="group" aria-label="Geräte hinzufügen">
          {(Object.keys(kindLabels) as NodeKind[]).map((kind) => (
            <button className="net-add" key={kind} onClick={() => addNode(kind)} type="button">
              + {kindLabels[kind]}
            </button>
          ))}
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
        }}
        ref={surfaceRef}
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
                const side: PortSide = point.x < node.x + NODE_WIDTH / 2 ? "left" : "right";
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
              style={{ left: node.x, top: node.y, width: NODE_WIDTH, height }}
            >
              <span className="net-node-kind">{kindLabels[node.kind]}</span>
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
                        event.shiftKey
                          ? { mode: "move-port", nodeId: node.id, portId: port.id }
                          : { mode: "wire", nodeId: node.id, portId: port.id, bus: port.bus, x: point.x, y: point.y },
                      );
                    }}
                    style={{
                      [port.side === "left" ? "left" : "right"]: -PORT_OFFSET,
                      top: portTop(node, port),
                      ["--bus" as string]: busProfiles[port.bus].color,
                    }}
                    title={`${port.name} · zu einem gleichfarbigen Port ziehen zum Verbinden · Shift + Ziehen zum Verschieben · Rechtsklick zum Entfernen`}
                    type="button"
                  />
                );
              })}
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
                style={{ left: Math.min(menu.x, 999), top: menu.y }}
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
