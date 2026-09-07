import assert from "node:assert/strict";
import test from "node:test";

import { normalizePhysicalTopology, topologyToConfig } from "./topology.ts";

test("shared hardware interface remains one multi-participant bus port", () => {
  const topology = normalizePhysicalTopology({
    nodes: [
      {
        id: "gateway",
        name: "Gateway",
        kind: "gateway",
        x: 0,
        y: 0,
        ports: [
          { id: "drive--connection-1", name: "Antriebs-CAN", bus: "can_fd", side: "bottom", offset: 0.4, hardwareInterfaceId: "drive-can" },
          { id: "drive--connection-2", name: "Antriebs-CAN", bus: "can_fd", side: "bottom", offset: 0.6, hardwareInterfaceId: "drive-can" },
        ],
      },
      { id: "motor", name: "Motorsteuerung", kind: "ecu", x: 0, y: 200, ports: [{ id: "motor-can", name: "CAN", bus: "can_fd", side: "top", offset: 0.5, hardwareInterfaceId: "motor-can" }] },
      { id: "fuel", name: "Kraftstoffsystem", kind: "ecu", x: 220, y: 200, ports: [{ id: "fuel-can", name: "CAN", bus: "can_fd", side: "top", offset: 0.5, hardwareInterfaceId: "fuel-can" }] },
    ],
    edges: [
      { id: "gateway-motor", source: "gateway", sourcePort: "drive--connection-1", target: "motor", targetPort: "motor-can", bus: "can_fd" },
      { id: "gateway-fuel", source: "gateway", sourcePort: "drive--connection-2", target: "fuel", targetPort: "fuel-can", bus: "can_fd" },
    ],
  });

  assert.deepEqual(topology.nodes[0].ports.map((port) => port.id), ["drive"]);
  assert.equal(topology.edges.length, 2);
  assert.deepEqual(new Set(topology.edges.map((edge) => edge.sourcePort)), new Set(["drive"]));
});

test("semantic system buses keep powertrain together and chassis separate", () => {
  const node = (id, name) => ({ id, name, kind: "ecu", x: 0, y: 0, ports: [{ id: `${id}-can`, name: "CAN", bus: "can_fd", side: "right", offset: 0.5 }] });
  const topology = {
    nodes: [node("motor", "Motorsteuerung"), node("exhaust", "Abgasnachbehandlung"), node("brake", "Bremsensteuerung"), node("wheel", "Raddrehzahl")],
    edges: [
      { id: "powertrain", source: "motor", sourcePort: "motor-can", target: "exhaust", targetPort: "exhaust-can", bus: "can_fd" },
      { id: "chassis", source: "brake", sourcePort: "brake-can", target: "wheel", targetPort: "wheel-can", bus: "can_fd" },
    ],
  };
  const config = topologyToConfig(topology).config;
  assert.equal(config.networks.length, 2);
  assert.equal(config.communications[0].network, "antriebsstrang-can-fd-bus");
  assert.notEqual(config.communications[0].network, config.communications[1].network);
  assert.equal(config.networks.find((network) => network.id === "antriebsstrang-can-fd-bus")?.name, "Antriebsstrang-CAN");
});
