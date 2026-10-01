import assert from "node:assert/strict";
import test from "node:test";
import { isUnexpectedProjectRevisionChange, projectRevisionRefreshMode } from "./project-sync.ts";

test("server revisions from an active wizard do not look external", () => {
  assert.equal(isUnexpectedProjectRevisionChange({
    baseline: "revision-1",
    revision: "revision-2",
    localWriteUnchanged: true,
    wizardSessionActive: true,
  }), false);
});

test("an unrelated revision remains visible outside a wizard session", () => {
  assert.equal(isUnexpectedProjectRevisionChange({
    baseline: "revision-1",
    revision: "revision-2",
    localWriteUnchanged: true,
    wizardSessionActive: false,
  }), true);
});

test("initial baselines, unchanged revisions and local writes stay quiet", () => {
  assert.equal(isUnexpectedProjectRevisionChange({ baseline: "", revision: "revision-1", localWriteUnchanged: true, wizardSessionActive: false }), false);
  assert.equal(isUnexpectedProjectRevisionChange({ baseline: "revision-1", revision: "revision-1", localWriteUnchanged: true, wizardSessionActive: false }), false);
  assert.equal(isUnexpectedProjectRevisionChange({ baseline: "revision-1", revision: "revision-2", localWriteUnchanged: false, wizardSessionActive: false }), false);
});

test("simulation revisions refresh in place so live values survive", () => {
  assert.equal(projectRevisionRefreshMode("/studio/simulation"), "in-place");
  assert.equal(projectRevisionRefreshMode("/studio/engineering"), "reload");
});
