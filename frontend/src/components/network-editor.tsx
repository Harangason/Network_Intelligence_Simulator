"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  busProfiles,
  initialTopology,
  type BusType,
  type NetworkTopology,
  type NodeKind,
  type TopologyNode,
} from "@/lib/topology";

const NODE_WIDTH = 168;
const NODE_HEIGHT = 84;
const PORT_OFFSET = 12;

const kindLabels: Record<NodeKind, string> = {
  ecu: "ECU",
  gateway: "Gateway",
  sensor: "Sensor",
  actuator: "Aktor",
};

const busOrder: BusType[] = ["can_fd", "lin", "automotive_ethernet", "flexray"];

type DragState =
  | { mode: "move"; nodeId: string; offsetX: number; offsetY: number }
  | { mode: "wire"; source: string; x: number; y: number };

let counter = 0;
const nextId = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${(counter++).toString(36)}`;

function anchor(node: TopologyNode) {
  return { x: node.x + NODE_WIDTH / 2, y: node.y + NODE_HEIGHT / 2 };
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
  const [activeBus, setActiveBus] = useState<BusType>("can_fd");

  const pointFromEvent = useCallback((event: { clientX: number; clientY: number }) => {
    const rect = surfaceRef.current?.getBoundingClientRect();
    return { x: event.clientX - (rect?.left ?? 0), y: event.clientY - (rect?.top ?? 0) };
  }, []);

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
      } else {
        setDrag({ ...activeDrag, x: point.x, y: point.y });
      }
    }
    function up(event: PointerEvent) {
      if (activeDrag.mode === "wire") {
        const target = (event.target as HTMLElement).closest("[data-node-id]");
        const targetId = target?.getAttribute("data-node-id");
        if (targetId && targetId !== activeDrag.source) {
          const exists = topology.edges.some(
            (edge) =>
              (edge.source === activeDrag.source && edge.target === targetId) ||
              (edge.source === targetId && edge.target === activeDrag.source),
          );
          if (!exists) {
            onChange({
              ...topology,
              edges: [...topology.edges, { id: nextId("edge"), source: activeDrag.source, target: targetId, bus: activeBus }],
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
  }, [drag, topology, onChange, activeBus, pointFromEvent]);

  function addNode(kind: NodeKind) {
    const node: TopologyNode = {
      id: nextId(kind),
      name: `${kindLabels[kind]} ${topology.nodes.filter((item) => item.kind === kind).length + 1}`,
      kind,
      x: 60 + topology.nodes.length * 24,
      y: 60 + topology.nodes.length * 18,
    };
    onChange({ ...topology, nodes: [...topology.nodes, node] });
    setSelectedNode(node.id);
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

  function setEdgeBus(id: string, bus: BusType) {
    onChange({ ...topology, edges: topology.edges.map((edge) => (edge.id === id ? { ...edge, bus } : edge)) });
  }

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
        <div className="net-bus-picker" role="group" aria-label="Standard-Bus für neue Verbindungen">
          {busOrder.map((bus) => (
            <button
              aria-pressed={activeBus === bus}
              className={`net-bus ${activeBus === bus ? "active" : ""}`}
              key={bus}
              onClick={() => setActiveBus(bus)}
              style={{ ["--bus" as string]: busProfiles[bus].color }}
              type="button"
            >
              <span className="net-bus-dot" /> {busProfiles[bus].label}
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
        onPointerDown={() => {
          setSelectedNode(null);
          setSelectedEdge(null);
        }}
        ref={surfaceRef}
      >
        <svg aria-hidden="true" className="net-wires">
          {topology.edges.map((edge) => {
            const from = topology.nodes.find((node) => node.id === edge.source);
            const to = topology.nodes.find((node) => node.id === edge.target);
            if (!from || !to) return null;
            return (
              <path
                className={`net-wire ${selectedEdge === edge.id ? "selected" : ""}`}
                d={edgePath(anchor(from), anchor(to))}
                key={edge.id}
                onPointerDown={(event) => {
                  event.stopPropagation();
                  setSelectedEdge(edge.id);
                  setSelectedNode(null);
                }}
                stroke={busProfiles[edge.bus].color}
              />
            );
          })}
          {drag?.mode === "wire" &&
            (() => {
              const from = topology.nodes.find((node) => node.id === drag.source);
              if (!from) return null;
              return (
                <path
                  className="net-wire pending"
                  d={edgePath(anchor(from), { x: drag.x, y: drag.y })}
                  stroke={busProfiles[activeBus].color}
                />
              );
            })()}
        </svg>

        {topology.nodes.map((node) => (
          <div
            className={`net-node ${node.kind} ${selectedNode === node.id ? "selected" : ""}`}
            data-node-id={node.id}
            key={node.id}
            onDoubleClick={() => renameNode(node.id)}
            onPointerDown={(event) => {
              event.stopPropagation();
              setSelectedNode(node.id);
              setSelectedEdge(null);
              const point = pointFromEvent(event);
              setDrag({ mode: "move", nodeId: node.id, offsetX: point.x - node.x, offsetY: point.y - node.y });
            }}
            style={{ left: node.x, top: node.y, width: NODE_WIDTH, height: NODE_HEIGHT }}
          >
            <span className="net-node-kind">{kindLabels[node.kind]}</span>
            <strong className="net-node-name">{node.name}</strong>
            <button
              aria-label={`Verbindung von ${node.name} ziehen`}
              className="net-port"
              onPointerDown={(event) => {
                event.stopPropagation();
                const point = pointFromEvent(event);
                setDrag({ mode: "wire", source: node.id, x: point.x, y: point.y });
              }}
              style={{ right: -PORT_OFFSET }}
              type="button"
            />
            <span className="net-port-in" style={{ left: -PORT_OFFSET }} />
          </div>
        ))}
      </div>

      {selectedEdge &&
        (() => {
          const edge = topology.edges.find((item) => item.id === selectedEdge);
          if (!edge) return null;
          return (
            <div className="net-inspector">
              <span>Verbindung · Bus-Typ</span>
              <div className="net-bus-picker">
                {busOrder.map((bus) => (
                  <button
                    aria-pressed={edge.bus === bus}
                    className={`net-bus ${edge.bus === bus ? "active" : ""}`}
                    key={bus}
                    onClick={() => setEdgeBus(edge.id, bus)}
                    style={{ ["--bus" as string]: busProfiles[bus].color }}
                    type="button"
                  >
                    <span className="net-bus-dot" /> {busProfiles[bus].label}
                  </button>
                ))}
              </div>
            </div>
          );
        })()}

      <p className="net-hint">
        Karte ziehen zum Verschieben · Doppelklick zum Umbenennen · vom rechten Punkt zu einem Gerät ziehen, um zu verdrahten.
      </p>
    </div>
  );
}

export { initialTopology };
