import assert from "node:assert/strict";
import test from "node:test";

import { busProfile, busProfiles, normalizePhysicalTopology, topologyToConfig } from "./topology.ts";

test("wizard-local technologies have complete network-editor profiles", () => {
  for (const technology of ["i2c", "spi", "uart", "modbus_rtu", "modbus_tcp", "gpio", "pwm", "adc", "dac"]) {
    assert.equal(typeof busProfiles[technology]?.color, "string", technology);
    assert.ok(busProfiles[technology].label, technology);
    assert.ok(busProfiles[technology].payload > 0, technology);
  }
});

test("catalog and unknown technologies always receive a renderable profile", () => {
  assert.deepEqual(
    [busProfile("profinet").label, busProfile("io_link").label],
    ["PROFINET", "IO-Link"],
  );
  const unknown = busProfile("future_fieldbus");
  assert.equal(unknown.label, "Future Fieldbus");
  assert.match(unknown.color, /^hsl\(/);
  assert.equal(unknown.bitrate, null); // An unknown technology has no defensible default rate.
  for (const direct of ["gpio", "pwm", "adc", "dac"]) {
    assert.equal(busProfile(direct).bitrate, null);
  }
  assert.deepEqual(busProfile("future_fieldbus"), unknown);
});

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

test("normalization persists one powertrain bus and splits a shared gateway interface by domain", () => {
  const gatewayPort = { id: "gateway-can", name: "CAN", bus: "can_fd", side: "bottom", offset: 0.5, hardwareInterfaceId: "gateway-interface" };
  const ecu = (id, name) => ({ id, name, kind: "ecu", x: 0, y: 0, ports: [{ id: `${id}-can`, name: "CAN", bus: "can_fd", side: "top", offset: 0.5 }] });
  const topology = normalizePhysicalTopology({
    nodes: [
      { id: "gateway", name: "System", kind: "gateway", x: 0, y: 0, ports: [gatewayPort] },
      ecu("motor", "Motorsteuerung"),
      ecu("fuel", "Kraftstoffsystem"),
      ecu("brake", "Bremsensteuerung"),
    ],
    edges: [
      { id: "motor-gateway", source: "motor", sourcePort: "motor-can", target: "gateway", targetPort: "gateway-can", bus: "can_fd" },
      { id: "fuel-motor", source: "fuel", sourcePort: "fuel-can", target: "motor", targetPort: "motor-can", bus: "can_fd" },
      { id: "brake-gateway", source: "brake", sourcePort: "brake-can", target: "gateway", targetPort: "gateway-can", bus: "can_fd" },
    ],
  });

  assert.equal(topology.edges.find((edge) => edge.id === "motor-gateway")?.physicalNetworkId, "antriebsstrang-can-fd-bus");
  assert.equal(topology.edges.find((edge) => edge.id === "fuel-motor")?.physicalNetworkId, "antriebsstrang-can-fd-bus");
  assert.notEqual(
    topology.edges.find((edge) => edge.id === "motor-gateway")?.physicalNetworkId,
    topology.edges.find((edge) => edge.id === "brake-gateway")?.physicalNetworkId,
  );
  const gateway = topology.nodes.find((node) => node.id === "gateway");
  assert.equal(gateway.ports.length, 2);
  assert.deepEqual(new Set(gateway.ports.map((port) => port.physicalNetworkName)), new Set(["Antriebsstrang-CAN", "Fahrwerk / Fahrdynamik-CAN"]));
});

test("normalization replaces old generic network placeholders with the owning ECU domain", () => {
  const topology = normalizePhysicalTopology({
    nodes: [
      { id: "speed", name: "Drehzahl", kind: "sensor", x: 0, y: 0, ports: [{ id: "speed-can", name: "Systemgruppe-CAN", bus: "can_fd", side: "right", offset: 0.5, physicalNetworkId: "systemgruppe-can-fd-bus" }] },
      { id: "motor", name: "Motorsteuerung", kind: "ecu", x: 200, y: 0, ports: [{ id: "motor-can", name: "Systemgruppe-CAN", bus: "can_fd", side: "left", offset: 0.5, physicalNetworkId: "systemgruppe-can-fd-bus" }] },
    ],
    edges: [{ id: "speed-motor", source: "speed", sourcePort: "speed-can", target: "motor", targetPort: "motor-can", bus: "can_fd", physicalNetworkId: "systemgruppe-can-fd-bus", physicalNetworkName: "Systemgruppe-CAN" }],
  });

  assert.equal(topology.edges[0].physicalNetworkId, "antriebsstrang-can-fd-bus");
  assert.equal(topology.edges[0].physicalNetworkName, "Antriebsstrang-CAN");
  assert.deepEqual(new Set(topology.nodes.flatMap((node) => node.ports.map((port) => port.physicalNetworkId))), new Set(["antriebsstrang-can-fd-bus"]));
});
