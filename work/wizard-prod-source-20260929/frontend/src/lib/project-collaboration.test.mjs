import test from "node:test";
import assert from "node:assert/strict";
import { compactProjectId, expandBrowserProjectId, withProjectParam } from "./user-settings.ts";

test("shared links preserve custom and generated project identities", () => {
  for (const id of ["default", "network-project-demo", "network-project-2026-09-06", "network-project-20260906120000123-abcd", "custom"]) {
    assert.equal(expandBrowserProjectId(compactProjectId(id)), id);
    const link = new URL(withProjectParam("/studio?mode=network#editor", id), "http://localhost");
    assert.equal(expandBrowserProjectId(link.searchParams.get("project")), id);
    assert.equal(link.searchParams.get("mode"), "network");
    assert.equal(link.hash, "#editor");
  }
});

test("parallel workflow reads stay scoped to their original project", async () => {
  const oldWindow = globalThis.window;
  const oldFetch = globalThis.fetch;
  const pending = [];
  globalThis.window = {
    location: { search: "?project=alpha" },
    localStorage: { getItem: () => null },
  };
  globalThis.fetch = (url, init) => new Promise((resolve) => pending.push({ url, init, resolve }));
  try {
    const { getWorkflowSummary } = await import("./workflow-api.ts");
    const first = getWorkflowSummary();
    assert.equal(getWorkflowSummary(), first);
    window.location.search = "?project=beta";
    const second = getWorkflowSummary();
    assert.notEqual(first, second);
    assert.deepEqual(pending.map(p => p.init.headers["X-Project-ID"]), ["alpha", "beta"]);
    pending[1].resolve(new Response(JSON.stringify({ project_id: "beta" })));
    pending[0].resolve(new Response(JSON.stringify({ project_id: "alpha" })));
    assert.equal((await first).project_id, "alpha");
    assert.equal((await second).project_id, "beta");
  } finally {
    globalThis.window = oldWindow;
    globalThis.fetch = oldFetch;
  }
});

test("editor saves send the loaded baseline token and preserve conflict status", async () => {
  const oldWindow = globalThis.window;
  const oldFetch = globalThis.fetch;
  globalThis.window = { location: { search: "?project=demo" }, localStorage: { getItem: () => null }, dispatchEvent() {} };
  const requests = [];
  globalThis.fetch = async (url, init) => {
    requests.push(JSON.parse(init.body));
    return new Response(JSON.stringify({ error: "Changed elsewhere" }), { status: 409 });
  };
  try {
    const { saveWorkflowParameters, saveWorkflowTopology } = await import("./workflow-api.ts");
    await assert.rejects(saveWorkflowParameters({ bitrate: 500000 }, "loaded-parameters"), { status: 409 });
    await assert.rejects(saveWorkflowTopology({ nodes: [], edges: [] }, "loaded-topology"), { status: 409 });
    assert.equal(requests[0].expected_token, "loaded-parameters");
    assert.equal(requests[1].expected_token, "loaded-topology");
  } finally {
    globalThis.window = oldWindow;
    globalThis.fetch = oldFetch;
  }
});
