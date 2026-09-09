import assert from "node:assert/strict";
import test from "node:test";
import {
  assessCommunication,
  communicationPage,
  relevantReceiverIds,
  routeMessageIds,
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

test("begrenzt jede Seite auf 25 Zeilen", () => {
  const result = communicationPage(Array.from({ length: 61 }, (_, index) => index), 3);
  assert.equal(result.currentPage, 3);
  assert.equal(result.totalPages, 3);
  assert.deepEqual(result.items, Array.from({ length: 11 }, (_, index) => index + 50));
});
