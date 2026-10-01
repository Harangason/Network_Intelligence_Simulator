"use client";

import { PointerEvent, useEffect, useMemo, useState } from "react";

type BusKind = "can_fd" | "can" | "automotive_ethernet" | "lin";
type Bus = { id: string; label: string; technology: BusKind; x: number; y: number };
type Port = { id: string; label: string; technology: BusKind; network?: string };
type Ecu = { id: string; label: string; x: number; y: number; ports: Port[] };

type Props = { onConfigChange: (config: Record<string, unknown>) => void };

const busMeta: Record<BusKind, { label: string; color: string; bitrate: number }> = {
  can_fd: { label: "CAN FD", color: "#8ad94a", bitrate: 2_000_000 },
  can: { label: "CAN", color: "#f0b45b", bitrate: 500_000 },
  automotive_ethernet: { label: "ETH", color: "#5db7ff", bitrate: 1_000_000_000 },
  lin: { label: "LIN", color: "#c38cff", bitrate: 19_200 },
};

const defaultBuses: Bus[] = [
  { id: "powertrain_canfd", label: "Powertrain CAN FD", technology: "can_fd", x: 350, y: 92 },
  { id: "backbone_eth", label: "Ethernet Backbone", technology: "automotive_ethernet", x: 350, y: 210 },
  { id: "body_can", label: "Body CAN", technology: "can", x: 350, y: 328 },
  { id: "comfort_lin", label: "Comfort LIN", technology: "lin", x: 350, y: 446 },
];

const defaultEcus: Ecu[] = [
  { id: "drive_ecu", label: "Antriebs-ECU", x: 55, y: 88, ports: [{ id: "drive_canfd", label: "CAN FD 1", technology: "can_fd", network: "powertrain_canfd" }, { id: "drive_eth", label: "ETH 0", technology: "automotive_ethernet", network: "backbone_eth" }] },
  { id: "gateway", label: "Zentral-Gateway", x: 640, y: 155, ports: [{ id: "gateway_canfd", label: "CAN FD 1", technology: "can_fd", network: "powertrain_canfd" }, { id: "gateway_eth", label: "ETH 0", technology: "automotive_ethernet", network: "backbone_eth" }, { id: "gateway_can", label: "CAN 1", technology: "can", network: "body_can" }, { id: "gateway_lin", label: "LIN 1", technology: "lin", network: "comfort_lin" }] },
  { id: "body_ecu", label: "Karosserie-ECU", x: 55, y: 360, ports: [{ id: "body_can", label: "CAN 1", technology: "can", network: "body_can" }, { id: "body_lin", label: "LIN Master", technology: "lin", network: "comfort_lin" }] },
];

function buildConfig(ecus: Ecu[], buses: Bus[]) {
  const interfaces = ecus.flatMap((ecu) => ecu.ports.filter((port) => port.network).map((port) => ({ ecu, port })));
  const communications = buses.flatMap((bus) => {
    const members = interfaces.filter((item) => item.port.network === bus.id);
    if (members.length < 2) return [];
    const [sender, ...receivers] = members;
    return [{ id: `${bus.id}_traffic`, sender_interface: sender.port.id, receivers: receivers.map((item) => item.port.id), cycle_ms: bus.technology === "lin" ? 20 : 50, payload_bytes: bus.technology === "can_fd" ? 32 : bus.technology === "automotive_ethernet" ? 256 : 8 }];
  });
  return {
    schema: "communication-simulator.simulation-config.v1", name: "visual_multi_bus_network", duration_s: 1, seed: 42,
    formats: ["universal-jsonl", "universal-csv", "asc", "pcapng"],
    networks: buses.map((bus) => ({ id: bus.id, technology: bus.technology, bitrate: busMeta[bus.technology].bitrate })),
    hardware: ecus.map((ecu) => ({ id: ecu.id, type: "ecu", ports: ecu.ports.map((port) => ({ id: `${ecu.id}_${port.id}`, physical_type: port.technology, network_interfaces: [{ id: port.id, technology: port.technology, network: port.network }] })) })),
    communications,
  };
}

export function NetworkTopologyEditor({ onConfigChange }: Props) {
  const [ecus, setEcus] = useState(defaultEcus);
  const [buses, setBuses] = useState(defaultBuses);
  const [selectedBus, setSelectedBus] = useState("powertrain_canfd");
  const [selectedPort, setSelectedPort] = useState<string | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);
  const config = useMemo(() => buildConfig(ecus, buses), [ecus, buses]);

  useEffect(() => {
    onConfigChange(config);
  }, [config, onConfigChange]);

  function connect(portId: string) {
    const bus = buses.find((item) => item.id === selectedBus);
    if (!bus) return;
    setEcus((current) => current.map((ecu) => ({ ...ecu, ports: ecu.ports.map((port) => port.id === portId ? { ...port, network: port.technology === bus.technology ? bus.id : port.network } : port) })));
  }

  function addEcu() {
    const number = ecus.length + 1;
    setEcus((current) => [...current, { id: `ecu_${number}`, label: `ECU ${number}`, x: 60 + (number % 2) * 570, y: 510, ports: [{ id: `ecu_${number}_can`, label: "CAN FD 1", technology: "can_fd" }] }]);
  }

  function addBus() {
    const number = buses.length + 1;
    const id = `canfd_bus_${number}`;
    setBuses((current) => [...current, { id, label: `CAN FD Segment ${number}`, technology: "can_fd", x: 350, y: 560 + number * 18 }]);
    setSelectedBus(id);
  }

  function moveEcu(event: PointerEvent<SVGSVGElement>) {
    if (!dragging) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = Math.max(20, Math.min(730, event.clientX - bounds.left - 100));
    const y = Math.max(30, Math.min(570, event.clientY - bounds.top - 35));
    setEcus((current) => current.map((ecu) => ecu.id === dragging ? { ...ecu, x, y } : ecu));
  }

  return <section className="topology-editor">
    <div className="topology-toolbar">
      <div><strong>Verdrahtungsplan</strong><span>Port wählen, dann ein passendes Bus-Segment anklicken.</span></div>
      <div className="topology-actions"><button className="button secondary" type="button" onClick={addEcu}>+ ECU</button><button className="button secondary" type="button" onClick={addBus}>+ Bus</button></div>
    </div>
    <div className="topology-layout">
      <div className="topology-canvas">
        <svg viewBox="0 0 850 660" role="img" aria-label="Verdrahtbarer Netzwerkplan" onPointerMove={moveEcu} onPointerUp={() => setDragging(null)}>
          <defs><pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="#334151" /></pattern></defs>
          <rect width="850" height="660" fill="url(#grid)" />
          {ecus.flatMap((ecu) => ecu.ports.filter((port) => port.network).map((port) => {
            const bus = buses.find((item) => item.id === port.network); if (!bus) return null;
            return <line key={`${ecu.id}-${port.id}`} x1={ecu.x + 200} y1={ecu.y + 42 + ecu.ports.indexOf(port) * 25} x2={bus.x} y2={bus.y + 26} stroke={busMeta[port.technology].color} strokeWidth="2" opacity=".75" />;
          }))}
          {buses.map((bus) => <g key={bus.id} className="bus-node" onClick={() => setSelectedBus(bus.id)}>
            <rect x={bus.x} y={bus.y} width="185" height="52" rx="9" fill="#111922" stroke={selectedBus === bus.id ? busMeta[bus.technology].color : "#344150"} strokeWidth={selectedBus === bus.id ? 2 : 1} />
            <circle cx={bus.x + 18} cy={bus.y + 26} r="6" fill={busMeta[bus.technology].color} /><text x={bus.x + 33} y={bus.y + 23} fill="#eef4f8" fontSize="12" fontWeight="700">{bus.label}</text><text x={bus.x + 33} y={bus.y + 39} fill="#8f9baa" fontSize="10">{busMeta[bus.technology].label} · {busMeta[bus.technology].bitrate.toLocaleString("de-DE")} bit/s</text>
          </g>)}
          {ecus.map((ecu) => <g key={ecu.id} className="ecu-node">
            <rect x={ecu.x} y={ecu.y} width="200" height={55 + ecu.ports.length * 25} rx="10" fill="#121820" stroke="#526170" />
            <rect x={ecu.x} y={ecu.y} width="200" height="36" rx="10" fill="#19232d" onPointerDown={() => setDragging(ecu.id)} /><text x={ecu.x + 16} y={ecu.y + 23} fill="#eef4f8" fontSize="12" fontWeight="700">▣  {ecu.label}</text>
            {ecu.ports.map((port, index) => <g key={port.id} onClick={() => { setSelectedPort(port.id); connect(port.id); }}>
              <circle cx={ecu.x + 200} cy={ecu.y + 42 + index * 25} r="5" fill={busMeta[port.technology].color} /><text x={ecu.x + 16} y={ecu.y + 46 + index * 25} fill={selectedPort === port.id ? "#ffffff" : "#aeb8c3"} fontSize="11">{port.label} <tspan fill="#718092">{busMeta[port.technology].label}</tspan></text>
            </g>)}
          </g>)}
        </svg>
      </div>
      <aside className="topology-inspector"><p className="eyebrow">Bus-Segment</p><h3>{buses.find((bus) => bus.id === selectedBus)?.label}</h3><p>Ausgewählt: <span className="mono">{busMeta[buses.find((bus) => bus.id === selectedBus)?.technology ?? "can_fd"].label}</span></p><p className="muted">Klicke auf einen farblich passenden ECU-Port, um ihn mit diesem Segment zu verbinden. ECU-Köpfe lassen sich verschieben.</p><div className="topology-stat"><strong>{ecus.reduce((count, ecu) => count + ecu.ports.filter((port) => port.network === selectedBus).length, 0)}</strong><span>verbundene Ports</span></div></aside>
    </div>
  </section>;
}
