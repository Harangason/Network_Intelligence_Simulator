import assert from "node:assert/strict";
import test from "node:test";

import { normalizePhysicalTopology } from "./topology.ts";

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
