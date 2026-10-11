import assert from "node:assert/strict";
import test from "node:test";

import { createNetworkProjectId } from "./project-ids.ts";

test("project ids use native randomUUID when available", () => {
  const projectId = createNetworkProjectId({ randomUUID: () => "12345678-90ab-cdef-1234-567890abcdef" });

  assert.match(projectId, /^network-project-\d{14,17}-12345678$/);
});

test("project ids fall back to getRandomValues when randomUUID is unavailable", () => {
  const projectId = createNetworkProjectId({
    getRandomValues: (array) => {
      array.set([0xab, 0xcd, 0xef, 0x01, 0x23, 0x45, 0x67, 0x89]);
      return array;
    },
  });

  assert.match(projectId, /^network-project-\d{14,17}-abcdef01$/);
});

