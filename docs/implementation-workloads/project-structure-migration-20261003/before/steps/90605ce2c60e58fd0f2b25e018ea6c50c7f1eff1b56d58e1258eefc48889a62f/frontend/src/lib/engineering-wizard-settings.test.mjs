import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_ENGINEERING_WIZARD_SETTINGS,
  defaultWizardTechnologyIds,
  normalizeEngineeringWizardSettings,
  unscopedWizardBusTechnologies,
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
    bus_participant_limits: DEFAULT_ENGINEERING_WIZARD_SETTINGS.bus_participant_limits,
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

  assert.equal(settings.model_type, "custom");
  assert.deepEqual(settings.scope_ids, DEFAULT_ENGINEERING_WIZARD_SETTINGS.scope_ids);
  assert.deepEqual(settings.process_ids, DEFAULT_ENGINEERING_WIZARD_SETTINGS.process_ids);
  assert.equal(WIZARD_SCOPE_GROUP.options.length, 9);
  assert.equal(WIZARD_PROCESS_GROUP.options.length, 3);
});

test("wizard pages combine the task intake with the first project step", () => {
  assert.deepEqual(
    wizardQuestionnaireSteps("full").map((step) => step.id),
    ["project", "technologies", "architecture", "equipment"],
  );
  assert.deepEqual(
    wizardQuestionnaireSteps("can").map((step) => step.id),
    ["project", "technologies", "architecture", "parameters", "equipment"],
  );
});

const technology = (id, implementation_status = "IMPLEMENTED") => ({ id, implementation_status });

test("generic and custom projects do not invent transport technologies", () => {
  const technologies = [
    technology("custom_binary"),
    technology("custom_protocol"),
    technology("custom_tcp"),
    technology("custom_text"),
  ];
  assert.deepEqual(defaultWizardTechnologyIds({ id: "custom", label: "Custom", technologies }), []);
  assert.deepEqual(defaultWizardTechnologyIds({ id: "generic_networking", label: "Generic", technologies }), []);
  assert.deepEqual(defaultWizardTechnologyIds({ id: "generic", label: "Generic", technologies }), []);
});

test("industry does not select transport technologies without explicit bus evidence", () => {
  const technologies = [
    technology("lin"),
    technology("someip", "NOT_SUPPORTED"),
    technology("can_fd"),
    technology("automotive_ethernet"),
  ];
  assert.deepEqual(defaultWizardTechnologyIds({ id: "automotive", label: "Automotive", technologies }), []);
});

test("technical device domain also leaves transport selection open without bus evidence", () => {
  const technologies = [
    technology("i2c"),
    technology("spi"),
    technology("uart"),
    technology("planned", "PLANNED"),
    technology("gpio"),
    technology("pwm"),
  ];
  assert.deepEqual(defaultWizardTechnologyIds({ id: "embedded_systems", label: "Embedded", technologies }), []);
});

test("unqualified technology step lists available data-link buses across industries without selecting them", () => {
  const domains = [
    { id: "automotive", technologies: [
      { id: "can", kind: "network", layer: "DATA_LINK", implementation_status: "IMPLEMENTED" },
      { id: "can_xl", kind: "network", layer: "DATA_LINK", implementation_status: "EXPERIMENTAL" },
      { id: "ip", kind: "protocol", layer: "NETWORK", implementation_status: "IMPLEMENTED" },
    ] },
    { id: "embedded_systems", technologies: [
      { id: "i2c", kind: "network", layer: "DATA_LINK", implementation_status: "PARTIAL" },
      { id: "gpio", kind: "network", layer: "PHYSICAL", implementation_status: "IMPLEMENTED" },
      { id: "can", kind: "network", layer: "DATA_LINK", implementation_status: "IMPLEMENTED" },
      { id: "future_bus", kind: "network", layer: "DATA_LINK", implementation_status: "PLANNED" },
    ] },
  ];

  assert.deepEqual(unscopedWizardBusTechnologies(domains).map(({ id }) => id), ["can", "can_xl", "i2c"]);
  assert.deepEqual(defaultWizardTechnologyIds(domains[1]), []);
});
