import assert from "node:assert/strict";
import test from "node:test";
import {
  assessCommunication,
  communicationPage,
  groupCommunicationRoutes,
  relevantReceiverIds,
  routeMessageIds,
  selectCommunicationRoute,
} from "./routing-communication.ts";

function route(overrides = {}) {
  return {
    id: "route-1",
    source: { node_id: "motor" },
    destinations: [{ node_id: "abgas" }],
    payload: { message_id: "m1", message_ids: ["m1", "m2"], signal_ids: [] },
    route: { gateways: [], hops: [], transformations: [], priority: "NORMAL" },
    validation: { valid: true },
    status: "APPROVED",
    approval_state: "APPROVED",
    ...overrides,
  };
}

test("bewertet direkte, Gateway- und fehlende TX/RX-Beziehungen getrennt", () => {
  assert.equal(assessCommunication(route(), "abgas").state, "received");
  assert.equal(assessCommunication(route({ route: { gateways: ["gw"], hops: [], transformations: [], priority: "NORMAL" } }), "abgas").state, "via_gateway");
  assert.equal(assessCommunication(route({ route: { gateways: ["gw"], hops: [], transformations: [], priority: "NORMAL" } }), "gw").state, "ends_at_gateway");
  assert.equal(assessCommunication(route(), "cockpit").state, "not_routed");
});

test("markiert eine ungültige vorhandene Route als blockiert", () => {
  const result = assessCommunication(route({ validation: { valid: false, errors: [{ code: "NETWORK", message: "Netzsegment fehlt" }] } }), "abgas");
  assert.equal(result.state, "blocked");
  assert.equal(result.detail, "Netzsegment fehlt");
  assert.equal(result.repairable, true);
});

test("dedupliziert Nachrichten und priorisiert modellierte Empfänger", () => {
  assert.deepEqual(routeMessageIds(route()), ["m1", "m2"]);
  assert.deepEqual(relevantReceiverIds([route(), route({ id: "route-2", destinations: [{ node_id: "cockpit" }] })], "motor"), ["abgas", "cockpit"]);
});

test("vermischt eine direkte LIN-Beziehung nicht mit Gateway-Routen derselben Botschaft", () => {
  const gatewayRoute = route({
    id: "route-hmi",
    source: { node_id: "motor", network_id: "powertrain-can", protocol: "CAN_FD" },
    destinations: [{ node_id: "infotainment", network_id: "infotainment-ethernet", protocol: "ETHERNET" }],
    payload: { message_id: "exhaust-control", message_ids: ["exhaust-control"], signal_ids: [] },
    route: {
      gateways: [{ node_id: "system-gateway", name: "System" }],
      hops: [{ node_id: "motor" }, { node_id: "system-gateway" }, { node_id: "infotainment" }],
      transformations: [],
      priority: "NORMAL",
    },
  });
  const directLinRoute = route({
    id: "route-lin-output",
    source: { node_id: "motor", network_id: "motor-io-lin", protocol: "LIN" },
    destinations: [{ node_id: "abgas-output", network_id: "motor-io-lin", protocol: "LIN" }],
    payload: { message_id: "exhaust-control", message_ids: ["exhaust-control"], signal_ids: [] },
    route: {
      gateways: [],
      hops: [{ node_id: "motor" }, { node_id: "abgas-output" }],
      transformations: [],
      priority: "NORMAL",
    },
  });

  const groups = groupCommunicationRoutes([gatewayRoute, directLinRoute]);
  assert.equal(groups.length, 1);
  const selection = selectCommunicationRoute(groups[0].routes, "abgas-output");
  assert.ok(selection);
  assert.equal(selection?.route.id, "route-lin-output");
  assert.equal(selection?.route.source.network_id, selection?.route.destinations[0].network_id);
  assert.equal(selection?.route.source.protocol, "LIN");
  assert.equal(selection?.route.destinations[0].protocol, "LIN");
  assert.equal(selection?.assessment.state, "received");
  assert.deepEqual(selection?.route.route.gateways, []);
  assert.deepEqual(selection?.route.route.hops.map((hop) => hop.node_id), ["motor", "abgas-output"]);
});

test("begrenzt jede Seite auf 25 Zeilen", () => {
  const result = communicationPage(Array.from({ length: 61 }, (_, index) => index), 3);
  assert.equal(result.currentPage, 3);
  assert.equal(result.totalPages, 3);
  assert.deepEqual(result.items, Array.from({ length: 11 }, (_, index) => index + 50));
});
