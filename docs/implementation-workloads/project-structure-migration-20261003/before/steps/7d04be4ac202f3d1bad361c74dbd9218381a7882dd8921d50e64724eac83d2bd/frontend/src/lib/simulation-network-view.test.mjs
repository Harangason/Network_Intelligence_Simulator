import assert from "node:assert/strict";
import test from "node:test";

import {
  formatParticipants,
  runtimeNetworkPresentation,
  runtimeRoutePresentation,
} from "./simulation-network-view.ts";
import { DEFAULT_USER_SETTINGS } from "./user-settings.ts";

const topology = {
  nodes: [
    { id: "tx-node", engineeringId: "tx-id", name: "GearSelectorPosition" },
    { id: "rx-node", engineeringId: "rx-id", name: "Motorsteuerung" },
  ],
  edges: [],
};
const frames = [{
  route_id: "route-1",
  route_name: "route-1",
  network: "network-1",
  sender: "tx-id",
  receivers: ["rx-id"],
}];

test("legacy runtime IDs resolve to readable TX and RX names", () => {
  const network = runtimeNetworkPresentation({
    network_id: "network-1",
    technology: "can_fd",
  }, frames, topology);
  const route = runtimeRoutePresentation({
    route_id: "route-1",
    route_name: "route-1",
    network_id: "network-1",
  }, frames, topology);

  assert.equal(network.name, "Motorsteuerung · CAN FD");
  assert.deepEqual(network.senders, ["GearSelectorPosition"]);
  assert.deepEqual(network.receivers, ["Motorsteuerung"]);
  assert.equal(route.name, "GearSelectorPosition → Motorsteuerung");
  assert.equal(route.sender, "GearSelectorPosition");
  assert.deepEqual(route.receivers, ["Motorsteuerung"]);
});

test("new runtime names take precedence and long participant lists stay compact", () => {
  const presentation = runtimeNetworkPresentation({
    network_id: "network-1",
    network_name: "Antriebs-CAN",
    technology: "can_fd",
    senders: ["Sensor A"],
    receivers: ["ECU A"],
  }, [], topology);

  assert.equal(presentation.name, "Antriebs-CAN");
  assert.equal(formatParticipants(["A", "B", "C", "D"]), "A, B, C +1");
  assert.equal(DEFAULT_USER_SETTINGS.collapseWorkflowHeroes, true);
});

test("canonical topology route metadata supplies the semantic bus name", () => {
  const network = runtimeNetworkPresentation({
    network_id: "network-1",
    network_name: "network-1",
    technology: "can_fd",
  }, frames, {
    ...topology,
    edges: [{
      id: "edge-1",
      source: "tx-node",
      sourcePort: "tx-port",
      target: "rx-node",
      targetPort: "rx-port",
      bus: "can_fd",
      routingMetadata: {
        route: { routeId: "route-uuid", routeCode: "1", name: "GearSelectorPosition → Motorsteuerung", source: "tx-id", target: "rx-id", approvalState: "APPROVED" },
      },
    }],
  });

  assert.equal(network.name, "Antriebsstrang-CAN");
});

test("logical addresses are shown together with readable TX and RX names", () => {
  const presentation = runtimeRoutePresentation({
    route_id: "route-addressed",
    route_name: "route-addressed",
    network_id: "network-1",
  }, [{
    route_id: "route-addressed",
    route_name: "route-addressed",
    network: "network-1",
    sender: "tx-id",
    receivers: ["rx-id"],
    source_name: "Sensor",
    source_logical_address: "0x0012",
    destination_names: ["ECU"],
    destination_logical_addresses: ["0x0023"],
  }], topology);

  assert.equal(presentation.sender, "0x0012 · Sensor");
  assert.deepEqual(presentation.receivers, ["0x0023 · ECU"]);
  assert.equal(presentation.name, "0x0012 · Sensor → 0x0023 · ECU");
});
