import test from "node:test";
import assert from "node:assert/strict";
import { storageRequest } from "./trace-storage-api.ts";

test("storage settings use the explicit project and confirmed writes", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async (url, init) => {
      assert.equal(url, "/api/storage/settings");
      assert.equal(init.headers["X-Project-ID"], "isolated");
      assert.equal(init.headers["X-NetworkIS-Storage"], "confirmed");
      assert.equal(init.method, "PUT");
      assert.deepEqual(JSON.parse(init.body), { path: "D:\\Meine Traces" });
      assert.equal(init.cache, "no-store");
      return Response.json({ path: "D:\\Meine Traces" });
    };
    assert.deepEqual(await storageRequest("isolated", "settings", "PUT", { path: "D:\\Meine Traces" }), { path: "D:\\Meine Traces" });
  } finally { globalThis.fetch = original; }
});

test("failed storage requests never pretend a setting was saved", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => Response.json({ error: "Nicht beschreibbar" }, { status: 503 });
    await assert.rejects(storageRequest("p", "settings", "PUT", { path: "/missing" }), /Nicht beschreibbar/);
    globalThis.fetch = async () => new Response("gateway unavailable", { status: 502 });
    await assert.rejects(storageRequest("p", "settings"), /HTTP 502/);
    globalThis.fetch = async () => { throw new TypeError("Failed to fetch"); };
    await assert.rejects(storageRequest("p", "settings"), /Failed to fetch/);
  } finally { globalThis.fetch = original; }
});
