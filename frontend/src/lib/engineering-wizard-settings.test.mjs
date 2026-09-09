import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_ENGINEERING_WIZARD_SETTINGS,
  normalizeEngineeringWizardSettings,
  wizardQuestionnaireSteps,
  WIZARD_PROCESS_GROUP,
  WIZARD_SCOPE_GROUP,
} from "./engineering-wizard-settings.ts";

test("wizard settings keep only supported ids and normalize the project metadata", () => {
  const settings = normalizeEngineeringWizardSettings({
    project_name: "  NIS Restbussimulation  ",
    model_type: "automotive",
    scope_ids: ["routing", "routing", "unknown", "simulation"],
    process_ids: ["review_gate", "unknown"],
  });

  assert.deepEqual(settings, {
    project_name: "NIS Restbussimulation",
    model_type: "automotive",
    scope_ids: ["routing", "simulation"],
    process_ids: ["review_gate", "approve_after_allow"],
  });
});

test("one-click approval and apply remains mandatory", () => {
  const settings = normalizeEngineeringWizardSettings({
    process_ids: ["defaults"],
  });

  assert.deepEqual(settings.process_ids, ["defaults", "approve_after_allow"]);
});

test("legacy projects retain their workflow industry as the model-type fallback", () => {
  const settings = normalizeEngineeringWizardSettings(undefined, "rail");

  assert.equal(settings.model_type, "rail");
});

test("empty or invalid wizard settings fall back to complete safe defaults", () => {
  const settings = normalizeEngineeringWizardSettings({
    model_type: "not valid!",
    scope_ids: [],
    process_ids: ["unknown"],
  });

  assert.equal(settings.model_type, "automotive");
  assert.deepEqual(settings.scope_ids, DEFAULT_ENGINEERING_WIZARD_SETTINGS.scope_ids);
  assert.deepEqual(settings.process_ids, DEFAULT_ENGINEERING_WIZARD_SETTINGS.process_ids);
  assert.equal(WIZARD_SCOPE_GROUP.options.length, 9);
  assert.equal(WIZARD_PROCESS_GROUP.options.length, 3);
});

test("wizard pages start with project name and omit settings-owned choices", () => {
  assert.deepEqual(
    wizardQuestionnaireSteps("full").map((step) => step.id),
    ["project", "technologies", "architecture", "task", "equipment"],
  );
  assert.deepEqual(
    wizardQuestionnaireSteps("can").map((step) => step.id),
    ["project", "technologies", "architecture", "parameters", "task", "equipment"],
  );
});
