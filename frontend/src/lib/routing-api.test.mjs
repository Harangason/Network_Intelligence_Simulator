import assert from "node:assert/strict";
import test from "node:test";

import {
  assertRoutingItemLimit,
  isRoutingTimeoutError,
  routingRequestSignal,
} from "./routing-guards.ts";

test("routing reads receive a bounded signal", () => {
  const signal = routingRequestSignal(undefined, 15_000);
  assert.ok(signal instanceof AbortSignal);
});

test("routing recognizes browser timeout failures", () => {
  assert.equal(isRoutingTimeoutError(new DOMException("timed out", "TimeoutError")), true);
  assert.equal(isRoutingTimeoutError(new Error("backend failed")), false);
});

test("routing pagination stops at its safety limit", () => {
  assert.doesNotThrow(() => assertRoutingItemLimit(99_999));
  assert.throws(
    () => assertRoutingItemLimit(100_000),
    /Sicherheitslimit von 100000 Einträgen/,
  );
});
